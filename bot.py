import os
import logging
import re
import secrets
import json
import uuid
import telegram
import datetime
import django


from typing import Optional
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from redis import Redis

load_dotenv()
django.setup()

from archive.models import Chat, Log, LogKind  # noqa


# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
redis = Redis(host='redis', port=6379, db=0)
DEFAULT_FACE = 100
BUFFER_TIME = 20
TOKEN = os.environ['BOT_TOKEN']

logger = logging.getLogger(__name__)


help_file = open('./help.md')
start_file = open('./start.md')
HELP_TEXT = help_file.read()
START_TEXT = start_file.read()
help_file.close()
start_file.close()


def start(_, update):
    """Send a message when the command /start is issued."""
    message = update.message
    assert isinstance(message, telegram.Message)
    if message.chat.type != 'supergroup':
        message.reply_text(START_TEXT, parse_mode='Markdown')
        return
    chat = get_chat(message.chat)
    if not chat.recording:
        chat.recording = True
        chat.save()
    message.chat.send_message('已重新开始记录，若需告一段落请使用 /save')


def save(_, update):
    message = update.message
    assert isinstance(message, telegram.Message)
    if message.chat.type != 'supergroup':
        return
    chat = get_chat(message.chat)
    chat.recording = False
    chat.save_date = datetime.datetime.now()
    chat.save()
    message.chat.send_message('告一段落，在 /start 前我不会再记录')


def bot_help(_, update):
    """Send a message when the command /help is issued."""
    update.message.reply_text(HELP_TEXT, parse_mode='Markdown')


def eval_dice(counter, face) -> str:
    if counter > 0x100:
        return 'too much dice'
    elif face > 0x1000:
        return 'too much dice face'
    result = [secrets.randbelow(face) + 1 for _ in range(counter)]
    result_repr = '[...]'
    if len(result) < 0x10:
        result_repr = repr(result)
    return '{}={}'.format(result_repr, sum(result))


def save_username(chat_id, user_id, username: str):
    redis.set('chat:{}:username:{}:id'.format(chat_id, username), user_id)


def set_name(_, update: telegram.Update, args):
    message = update.message
    assert isinstance(message, telegram.Message)
    if len(args) == 0:
        message.reply_text('请在 /name 后写下你的角色名')
        return
    user = message.from_user
    assert isinstance(user, telegram.User)
    name = ' '.join(args)
    redis.set('chat:{}:user:{}:name'.format(message.chat_id, user.id), name.strip().encode())
    message.chat.send_message('{} 已被设为 {}'.format(user.full_name, name))
    message.delete()


def get_name(message: telegram.Message) -> Optional[str]:
    user_id = message.from_user.id
    name = redis.get('chat:{}:user:{}:name'.format(message.chat_id, user_id))
    if name:
        return name.decode()
    else:
        return None


def set_dice_face(_, update, args):
    message = update.message
    assert isinstance(message, telegram.Message)
    if len(args) != 1:
        message.reply_text(
            '需要（且仅需要）指定骰子的默认面数，'
            '目前为 <b>{}</b>'.format(get_default_dice_face(chat_id=message.chat_id)),
            parse_mode='HTML'
        )
    try:
        face = int(args[0])
    except ValueError:
        message.reply_text('面数只能是数字')
        return
    redis.set('chat:{}:face'.format(message.chat_id), face)


def get_default_dice_face(chat_id) -> int:
    try:
        return int(redis.get('chat:{}:face'.format(chat_id)))
    except (ValueError, TypeError):
        return DEFAULT_FACE


DICE_REGEX = re.compile(r'\b(\d*)d(\d*)([+\-*]?)(\d*)\b')


def roll_text(chat_id, text):
    def repl(match):
        counter = match.group(1)
        face = match.group(2)
        if counter == '':
            counter = 1
        if face == '':
            face = get_default_dice_face(chat_id)
        counter = int(counter)
        face = int(face)
        return '<code>{}d{}={}</code>'.format(
            counter, face,
            eval_dice(counter, face)
        )
    return DICE_REGEX.sub(repl, text)


def look_hide_roll(bot: telegram.Bot, update):
    query = update.callback_query
    assert isinstance(query, telegram.CallbackQuery)
    result = redis.get('roll:{}'.format(query.data))
    if result:
        data = json.loads(result)
        if is_gm(bot, data['chat_id'], query.from_user.id):
            text = data['text'].replace('<code>', '').replace('</code>', '')
        else:
            text = '你不是 GM，不能看哟'
    else:
        text = '找不到这条暗骰记录'
    query.answer(
        show_alert=True,
        text=text,
        cache_time=10000,
    )


def handle_roll(bot, message: telegram.Message, name: str, text: str, hide=False):
    result_text = roll_text(message.chat_id, text)
    kind = LogKind.ROLL.value
    if hide:
        roll_id = str(uuid.uuid4())
        redis.set('roll:{}'.format(roll_id), json.dumps({
            'text': result_text,
            'chat_id': message.chat_id,
        }))
        keyboard = [[InlineKeyboardButton("GM 查看", callback_data=roll_id)]]

        reply_markup = InlineKeyboardMarkup(keyboard)
        sent = message.chat.send_message(
            '<b>{}</b> 投了一个隐形骰子'.format(name),
            reply_markup=reply_markup,
            parse_mode='HTML'
        )
        kind = LogKind.HIDE_DICE.value
    else:
        sent = message.chat.send_message(
            '{} 🎲 {}'.format(name, result_text),
            parse_mode='HTML'
        )
    user = message.from_user
    assert isinstance(user, telegram.User)
    chat = get_chat(message.chat)
    if chat.recording:
        Log.objects.create(
            user_id=user.id,
            message_id=sent.message_id,
            chat=chat,
            content=result_text,
            user_fullname=user.full_name,
            character_name=name,
            gm=is_gm(bot, message.chat_id, user.id),
            kind=kind,
            created=message.date,
        )


ME_REGEX = re.compile(r'^[.。]me\b|\s[.。]me\s?')
USERNAME_REGEX = re.compile(r'@([a-zA-Z0-9_]{5,})')


def is_author(message_id, user_id):
    return bool(Log.objects.filter(message_id=message_id, user_id=user_id).first())


def handle_say(bot: telegram.Bot, chat, message: telegram.Message, name: str, text: str, edit_log=None):
    def name_resolve(match):
        username = match.group(1)
        origin = '@{}'.format(username)
        user_id = redis.get('chat:{}:username:{}:id'.format(message.chat_id, username))
        if not user_id:
            return origin
        name_result = redis.get('chat:{}:user:{}:name'.format(message.chat_id, int(user_id)))
        if not name_result:
            return origin
        return '<b>{}</b>'.format(name_result.decode())

    text = USERNAME_REGEX.sub(name_resolve, text)

    kind = LogKind.NORMAL.value
    if ME_REGEX.search(text):
        if ME_REGEX.sub('', text).strip() == '':
            message.delete()
            return
        send_text = ME_REGEX.sub('<b>{}</b>'.format(name), text)
        content = send_text
        kind = LogKind.ME.value
    elif text.strip() == '':
        message.delete()
        return
    else:
        send_text = '<b>{}</b>: {}'.format(name, text)
        content = text

    if edit_log is None:
        reply_to_message_id = None
        reply_log = None
        if message.reply_to_message:
            target = message.reply_to_message
            assert isinstance(target, telegram.Message)
            reply_to_message_id = target.message_id
            reply_log = Log.objects.filter(chat=chat, message_id=reply_to_message_id).first()
        sent = message.chat.send_message(
            send_text,
            reply_to_message_id=reply_to_message_id,
            parse_mode='HTML'
        )
        if chat.recording:
            Log.objects.create(
                message_id=sent.message_id,
                chat=chat,
                user_id=message.from_user.id,
                user_fullname=message.from_user.full_name,
                kind=kind,
                reply=reply_log,
                character_name=name,
                content=content,
                gm=is_gm(bot, message.chat.id, message.from_user.id),
                created=message.date,
            )
    else:
        assert isinstance(edit_log, Log)
        edit_log.content = content
        edit_log.kind = kind
        edit_log.save()
        bot.edit_message_text(send_text, message.chat_id, edit_log.message_id, parse_mode='HTML')
    message.delete()


def handle_delete(bot, message: telegram.Message):
    target = message.reply_to_message
    if not isinstance(target, telegram.Message):
        message.delete()
        return

    user_id = message.from_user.id
    log = Log.objects.filter(message_id=target.message_id).first()
    if log and (log.user_id == user_id or is_gm(bot, message.chat_id, user_id)):
        log.deleted = True
        log.save()
        target.delete()
    message.delete()


def handle_edit(bot, chat, message: telegram.Message, text: str):
    target = message.reply_to_message
    if not isinstance(target, telegram.Message):
        message.delete()
        return

    user_id = message.from_user.id
    log = Log.objects.filter(message_id=target.message_id).first()
    if log and log.user_id == user_id:
        handle_say(bot, chat, message, log.character_name, text, edit_log=log)

    message.delete()


def is_gm(bot: telegram.Bot, chat_id: int, user_id: int) -> bool:
    result = redis.get('chat:{}:admins')
    if not result:
        for member in bot.get_chat_administrators(chat_id):
            if member.user.id == user_id:
                return True
        return False
    else:
        admins = json.loads(result)
        return user_id in admins


def refresh(bot, update):
    if isinstance(update.message, telegram.Message):
        message = update.message
        admins = json.dumps([member.user.id for member in bot.get_chat_administrators(message.chat_id)])
        redis.set('chat:{}:admins'.format(message.chat_id), admins)
        user = message.from_user
        if isinstance(user, telegram.User):
            if user.username:
                redis.set('chat:{}:username:{}:id'.format(message.chat_id, user.username), user.id)


def handle_message(bot, update):
    message = update.message
    assert isinstance(message, telegram.Message)
    text = message.text
    assert isinstance(text, str)
    message_match = re.match(r'^[.。](\w*)\s*', text)
    if not message_match:
        return
    elif message.chat.type != 'supergroup':
        message.reply_text('只能在超级群中使用我哦')
        return

    command = message_match.group(1)
    chat = get_chat(message.chat)
    name = get_name(message)
    if not name:
        message.reply_text('请先使用 `/name [你的角色名]` 设置角色名')
        return
    rest = text[message_match.end():]

    if command == 'r' or command == 'roll':
        handle_roll(bot, message, name, rest)
    elif command == 'me':
        handle_say(bot, chat, message, name, text)
    elif command == '':
        handle_say(bot, chat, message, name, rest)
    elif command == 'del' or command == 'deleted':
        handle_delete(bot, message)
    elif command == 'edit':
        handle_edit(bot, chat, message, rest)
    elif command == 'hd':
        handle_roll(bot, message, name, rest, hide=True)
    else:
        message.reply_text('未知命令 `{}` 请使用 /help 查看可以用什么命令'.format(command))
    refresh(bot, update)


def error(_, update, bot_error):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, bot_error)


def get_chat(telegram_chat: telegram.Chat) -> Chat:
    chat = Chat.objects.filter(
        chat_id=telegram_chat.id
    ).first()
    if chat:
        return chat
    else:
        return Chat.objects.create(
            chat_id=telegram_chat.id,
            title=telegram_chat.title,
        )


def main():
    """Start the bot."""
    # Create the EventHandler and pass it your bot's token.
    updater = Updater(TOKEN)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("save", save))
    dp.add_handler(CommandHandler("help", bot_help))
    dp.add_handler(CommandHandler('face', set_dice_face, pass_args=True))
    dp.add_handler(CommandHandler('name', set_name, pass_args=True))

    # on otherwise i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(Filters.text, handle_message))

    updater.dispatcher.add_handler(CallbackQueryHandler(look_hide_roll))
    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    if 'WEBHOOK_URL' in os.environ:
        updater.start_webhook(listen='0.0.0.0', port=9990, url_path=TOKEN)
        url = os.path.join(os.environ['WEBHOOK_URL'], TOKEN)
        updater.bot.set_webhook(url=url)
    else:
        updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
