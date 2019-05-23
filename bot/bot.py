import datetime
import logging
import os
import re
from hashlib import sha256

import telegram
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram.ext.dispatcher import run_async

from bot.say import handle_as_say, handle_say
from bot.variable import handle_list_variables, handle_variable_assign
from .roll import set_dice_face, handle_coc_roll, handle_loop_roll, handle_normal_roll, hide_roll_callback
from .character_name import set_name, get_name
from .round_counter import round_inline_callback, start_round, hide_round,\
    public_round, next_turn, handle_initiative
from . import pattern
from . import const
from .display import Text, get
from .system import RpgMessage, is_group_chat, delete_message, is_gm, get_chat, error_message, get_player_by_id

from archive.models import Chat, Log
from game.models import Player

# Enable logging
logging.basicConfig(format=const.LOGGER_FORMAT, level=logging.INFO)
logger = logging.getLogger(__name__)


def start_command(_, update, job_queue):
    """Send a message when the command /start is issued."""
    message = update.message
    assert isinstance(message, telegram.Message)
    if not is_group_chat(message.chat):
        message.reply_text(get(Text.START_TEXT), parse_mode='Markdown')
        return
    chat = get_chat(message.chat)
    if not chat.recording:
        chat.recording = True
        chat.save()
        message.chat.send_message('#start {}'.format(get(Text.START_RECORDING)))
    else:
        error_message(message, job_queue, get(Text.ALREADY_STARTED))


def save(_, update, job_queue):
    message = update.message
    assert isinstance(message, telegram.Message)
    if not is_group_chat(message.chat):
        return
    chat = get_chat(message.chat)
    if chat.recording:
        chat.recording = False
        chat.save_date = datetime.datetime.now()
        chat.save()
        message.chat.send_message('#save {}'.format(get(Text.SAVE)))
    else:
        error_message(message, job_queue, get(Text.ALREADY_SAVED))


def bot_help(_, update):
    """Send a message when the command /help is issued."""
    update.message.reply_text(get(Text.HELP_TEXT), parse_mode='HTML')


@run_async
def inline_callback(bot, update):
    query = update.callback_query
    assert isinstance(query, telegram.CallbackQuery)
    data = query.data or ''
    gm = is_gm(query.message.chat_id, query.from_user.id)
    if data.startswith('round'):
        round_inline_callback(bot, query, gm)
    if data.startswith('hide_roll'):
        hide_roll_callback(bot, update)
    else:
        query.answer(show_alert=True, text=get(Text.UNKNOWN_COMMAND))


def handle_delete(chat, message: telegram.Message, job_queue):
    target = message.reply_to_message
    if isinstance(target, telegram.Message):
        user_id = message.from_user.id
        log = Log.objects.filter(chat=chat, message_id=target.message_id).first()
        if log is None:
            error_message(message, job_queue, get(Text.RECORD_NOT_FOUND))
        elif log.user_id == user_id or is_gm(message.chat_id, user_id):
            delete_message(target)
            delete_message(message)
            log.deleted = True
            log.save()
        else:
            error_message(message, job_queue, get(Text.HAVE_NOT_PERMISSION))
    else:
        error_message(message, job_queue, get(Text.NEED_REPLY))


def handle_replace(bot, chat, job_queue, message: telegram.Message, start: int):
    target = message.reply_to_message
    text = message.text[start:].strip()
    if not isinstance(target, telegram.Message):
        return error_message(message, job_queue, get(Text.NEED_REPLY))
    try:
        [old, new] = filter(lambda x: x != '', text.split('/'))
    except ValueError:
        return error_message(message, job_queue, get(Text.REPLACE_USAGE))
    assert isinstance(message.from_user, telegram.User)
    user_id = message.from_user.id
    log = Log.objects.filter(chat=chat, message_id=target.message_id).first()
    text = log.content.replace(old, new)
    if log is None:
        error_message(message, job_queue, get(Text.RECORD_NOT_FOUND))
    elif log.user_id == user_id:
        handle_say(bot, chat, job_queue, message, log.character_name, text, edit_log=log)
        delete_message(message)
    else:
        error_message(message, job_queue, get(Text.HAVE_NOT_PERMISSION))


def handle_edit(bot, chat, job_queue, message: telegram.Message, start: int):
    target = message.reply_to_message
    if not isinstance(target, telegram.Message):
        return error_message(message, job_queue, get(Text.NEED_REPLY))

    assert isinstance(message.from_user, telegram.User)
    user_id = message.from_user.id
    log = Log.objects.filter(chat=chat, message_id=target.message_id).first()
    if log is None:
        error_message(message, job_queue, get(Text.RECORD_NOT_FOUND))
    elif log.user_id == user_id:
        rpg_message = RpgMessage(message, start)
        handle_say(bot, chat, job_queue, message, log.character_name, rpg_message, edit_log=log)
        delete_message(message)
    else:
        error_message(message, job_queue, get(Text.HAVE_NOT_PERMISSION))


def handle_lift(message: telegram.Message, job_queue, chat: Chat):
    assert isinstance(message, telegram.Message)
    reply_to = message.reply_to_message
    user_id = message.from_user.id
    if not isinstance(reply_to, telegram.Message):
        return error_message(message, job_queue, get(Text.NEED_REPLY))
    elif reply_to.from_user.id == message.bot.id:
        return error_message(message, job_queue, get(Text.NEED_REPLY_PLAYER_RECORD))
    elif reply_to.from_user.id != user_id and not is_gm(message.chat_id, user_id):
        return error_message(message, job_queue, get(Text.HAVE_NOT_PERMISSION))
    name = get_name(reply_to)
    with_photo = handle_photo(reply_to)
    handle_say(message.bot, chat, job_queue, reply_to, name, RpgMessage(reply_to), with_photo=with_photo)
    delete_message(reply_to)
    delete_message(message)


def update_player(chat_id, user: telegram.User):
    player = Player.objects.filter(chat_id=chat_id, user_id=user.id).first()
    if not player:
        return
    player.username = user.username or ''
    player.full_name = user.full_name
    player.save()


@run_async
def run_chat_job(_bot, update: telegram.Update):
    message = update.message
    assert isinstance(message, telegram.Message)
    update_player(message.chat_id, message.from_user)


@run_async
def handle_message(bot, update, job_queue):
    message = update.message
    assert isinstance(message, telegram.Message)
    with_photo = handle_photo(message)
    if not message.text or not message.text.startswith(('.', '。')):
        return
    if not is_group_chat(message.chat):
        message.reply_text(get(Text.NOT_GROUP))
        return
    elif not isinstance(message.from_user, telegram.User):
        return
    chat = get_chat(message.chat)
    player = get_player_by_id(message.chat_id, message.from_user.id)
    name = player.character_name
    if not name:
        error_message(message, job_queue, get(Text.NOT_SET_NAME))
        return

    handlers = [
        (re.compile(r'^[.。](rh?)\b'), handle_normal_roll),
        (re.compile(r'^[.。](hd)\b'), handle_normal_roll),
        (re.compile(r'^[.。](loh?)\b'), handle_loop_roll),
        (re.compile(r'^[.。](coch?[+\-]?h?)\s*'), handle_coc_roll),
        (re.compile(r'^[.。](init)\b'), handle_initiative),
        (re.compile(r'^[.。](set)\b'), handle_variable_assign),
        (re.compile(r'^[.。](list)\b'), handle_list_variables),
        (re.compile(r'^[.。](as)\b'), handle_as_say),
    ]

    for pat, handler in handlers:
        result = pattern.split(pat, message.text)
        if not result:
            continue
        command, start = result
        text = message.text[start:]
        handler(
            bot=bot,
            chat=chat,
            player=player,
            command=command,
            start=start,
            name=name,
            text=text,
            message=message,
            job_queue=job_queue,
            with_photo=with_photo,
        )
        return

    edit_command_matched = pattern.EDIT_COMMANDS_REGEX.match(message.text)
    if edit_command_matched:
        command = edit_command_matched.group(1)
        reply_to = message.reply_to_message
        if not chat.recording:
            error_message(message, job_queue, get(Text.RECORD_NOT_FOUND))
        elif not isinstance(reply_to, telegram.Message):
            error_message(message, job_queue, get(Text.NEED_REPLY))
        elif command == 'lift':
            handle_lift(message, job_queue, chat)
        elif reply_to.from_user.id != bot.id:
            error_message(message, job_queue, get(Text.NEED_REPLY_PLAYER_RECORD))
        elif command == 'del':
            handle_delete(chat, message, job_queue)
        elif command == 'edit':
            handle_edit(bot, chat, job_queue, message, start=edit_command_matched.end())
        elif command == 's':
            handle_replace(bot, chat, job_queue, message, start=edit_command_matched.end())
    else:
        rpg_message = RpgMessage(message, start=1)  # skip dot
        handle_say(bot, chat, job_queue, message, name, rpg_message, with_photo=with_photo)


def handle_photo(message: telegram.Message):
    photo_size_list = message.photo
    if len(photo_size_list) == 0:
        return None
    photo_size_list.sort(key=lambda p: p.file_size)
    return photo_size_list[-1]


def handle_error(_, update, bot_error):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, bot_error)


def handle_status(bot, update):
    assert isinstance(update.message, telegram.Message)
    message = update.message
    chat = get_chat(message.chat)
    if message.new_chat_title:
        chat.title = message.new_chat_title
        chat.save()
    if message.new_chat_members:
        for user in message.new_chat_members:
            if user.id == bot.id:
                message.chat.send_message(
                    get(Text.START_TEXT),
                    parse_mode='Markdown',
                    disable_web_page_preview=True
                )


def set_password(_, update, args, job_queue):
    message = update.message
    assert isinstance(message, telegram.Message)
    if len(args) != 1:
        text = get(Text.PASSWORD_USAGE)
        return error_message(message, job_queue, text)
    chat = get_chat(message.chat)
    chat.password = sha256(str(args[0]).encode()).hexdigest()
    chat.save()
    message.reply_text(Text.PASSWORD_SUCCESS)


def run_bot():
    """Start the bot."""
    # Create the EventHandler and pass it your bot's token.
    updater = Updater(const.TOKEN)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start_command, pass_job_queue=True))
    dp.add_handler(CommandHandler("save", save, pass_job_queue=True))
    dp.add_handler(CommandHandler("help", bot_help))
    dp.add_handler(CommandHandler('face', set_dice_face, pass_args=True, pass_job_queue=True))
    dp.add_handler(CommandHandler('name', set_name, pass_args=True, pass_job_queue=True))
    dp.add_handler(CommandHandler('round', start_round, pass_job_queue=True))
    dp.add_handler(CommandHandler('public', public_round, pass_job_queue=True))
    dp.add_handler(CommandHandler('hide', hide_round, pass_job_queue=True))
    dp.add_handler(CommandHandler('next', next_turn, pass_job_queue=True))
    dp.add_handler(CommandHandler('password', set_password, pass_args=True, pass_job_queue=True))
    dp.add_handler(MessageHandler(
        Filters.text | Filters.photo,
        handle_message,
        channel_post_updates=False,
        pass_job_queue=True,
    ))
    dp.add_handler(MessageHandler(Filters.status_update, handle_status))
    # always execute `run_chat_job`.
    dp.add_handler(
        MessageHandler(
            Filters.all,
            run_chat_job,
            channel_post_updates=False,
        ),
        group=42
    )

    updater.dispatcher.add_handler(CallbackQueryHandler(inline_callback))
    # log all errors
    dp.add_error_handler(handle_error)

    # Start the Bot
    if 'WEBHOOK_URL' in os.environ:
        updater.start_webhook(listen='0.0.0.0', port=const.WEBHOOK_PORT, url_path=const.TOKEN)
        url = os.path.join(os.environ['WEBHOOK_URL'], const.TOKEN)
        updater.bot.set_webhook(url=url)
    else:
        updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()
