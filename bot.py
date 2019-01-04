import os
import logging
import re
import secrets
import telegram

from dotenv import load_dotenv
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

load_dotenv()
# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

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
    update.message.reply_text(START_TEXT, parse_mode='Markdown')


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


def set_name(_, update: telegram.Update, args, chat_data: dict):
    message = update.message
    assert isinstance(message, telegram.Message)
    if len(args) == 0:
        message.reply_text('请在 /name 后写下你的角色名')
        return
    user = message.from_user
    assert isinstance(user, telegram.User)
    name = ' '.join(args)
    if 'name' in chat_data:
        chat_data['name'][user.id] = name
    else:
        chat_data['name'] = {user.id: name}
    message.chat.send_message('{} 已被设为 {}'.format(user.full_name, name))
    message.delete()


def get_default_dice_face(chat_data: dict) -> int:
    return int(chat_data.get('face', DEFAULT_FACE))


DICE_REGEX = re.compile(r'\b(\d*)d(\d*)([+\-*]?)(\d*)\b')


def handle_roll(text: str, default_face: int) -> str:
    def repl(match):
        counter = match.group(1)
        face = match.group(2)
        if counter == '':
            counter = 1
        if face == '':
            face = default_face
        counter = int(counter)
        face = int(face)
        return '<code>{}</code>'.format(eval_dice(counter, face))
    return DICE_REGEX.sub(repl, text)


ME_REGEX = re.compile(r'^[.。]me|\s[.。]me\s?')


def character_event(name: str, text: str):
    if ME_REGEX.search(text):
        return re.sub(ME_REGEX, '<b>{}</b>'.format(name), text)
    else:
        return '<b>{}</b>: 「{}」'.format(name, text)


def is_gm(bot: telegram.Bot, chat_id: int, user_id: int) -> bool:
    for member in bot.get_chat_administrators(chat_id):
        if member.user.id == user_id:
            return True
    return False


AUTHOR_MAP_KEY = 'author_map'


def record_author(message_id, user_id, chat_data):
    if AUTHOR_MAP_KEY not in chat_data:
        chat_data[AUTHOR_MAP_KEY] = {message_id: user_id}
    else:
        chat_data[AUTHOR_MAP_KEY][message_id] = user_id


def is_author(message_id, user_id, chat_data):
    if AUTHOR_MAP_KEY not in chat_data:
        chat_data[AUTHOR_MAP_KEY] = dict()
        return False
    author_map = chat_data[AUTHOR_MAP_KEY]
    assert isinstance(author_map, dict)
    return author_map.get(message_id, None) == user_id


def handle_message(bot, update, chat_data: dict):
    message = update.message
    assert isinstance(message, telegram.Message)
    text = message.text
    assert isinstance(text, str)
    message_match = re.match(r'^[.。](\w*)\s*', text)
    if not message_match:
        return

    command = message_match.group(1)

    # is there character name?
    name = None
    if 'name' in chat_data:
        name = chat_data['name'].get(message.from_user.id, None)
    if name is None and command != 'name':
        message.reply_text('请先用 /name [角色名] 设置一个角色')
        return

    # cut off command part, except ".me"
    if command == 'me':
        command = ''
        rest = text
    else:
        rest = text[message_match.end():]

    if command == 'name':
        set_name(bot, update, [rest], chat_data)
    elif command == 'r' or command == 'roll':
        message.chat.send_message(
            '{} 🎲 {}'.format(name, handle_roll(rest, get_default_dice_face(chat_data))),
            parse_mode='HTML'
        )
    elif command == '':
        msg = message.chat.send_message(character_event(name, rest), parse_mode='HTML')
        message.delete()
        record_author(msg.message_id, message.from_user.id, chat_data)
    elif command == 'del' or command == 'edit' or command == 'delete':
        user_id = message.from_user.id
        target = message.reply_to_message
        if not isinstance(target, telegram.Message):
            pass
        elif is_gm(bot, message.chat_id, user_id) or is_author(target.message_id, user_id, chat_data):
            if command == 'edit':
                target.edit_text(character_event(name, rest), parse_mode='HTML')
            else:
                target.delete()
        message.delete()
    else:
        message.reply_text('未知命令 请使用 /help 查看可以用什么命令')


def error(_, update, bot_error):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, bot_error)


def set_dice_face(_, update, args, chat_data):
    message = update.message
    assert isinstance(message, telegram.Message)
    if len(args) != 1:
        message.reply_text(
            '需要（且仅需要）指定骰子的默认面数，'
            '目前为 <b>{}</b>'.format(get_default_dice_face(chat_data)),
            parse_mode='HTML'
        )
    try:
        face = int(args[0])
    except ValueError:
        message.reply_text('面数只能是数字')
        return
    chat_data['face'] = face


def main():
    """Start the bot."""
    # Create the EventHandler and pass it your bot's token.
    updater = Updater(TOKEN)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", bot_help))
    dp.add_handler(CommandHandler('name', set_name, pass_chat_data=True, pass_args=True))
    dp.add_handler(CommandHandler('face', set_name, pass_chat_data=True, pass_args=True))

    # on otherwise i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(Filters.text, handle_message, pass_chat_data=True))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
