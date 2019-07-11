import datetime
import logging
import os
import re
from hashlib import sha256
from functools import partial

import telegram
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler
from telegram.ext.dispatcher import run_async

from bot.say import handle_as_say, handle_say, get_tag
from bot.system import Deletion
from bot.variable import handle_list_variables, handle_variable_assign, handle_clear_variables
from .roll import set_dice_face, handle_coc_roll, handle_loop_roll, handle_normal_roll, hide_roll_callback
from .character_name import set_name, get_name
from .round_counter import round_inline_callback, start_round, hide_round,\
    public_round, next_turn, handle_initiative
from . import pattern
from . import const
from .display import Text, get_by_user, get
from .system import RpgMessage, is_group_chat, delete_message, is_gm, get_chat, error_message,\
    get_player_by_id, delay_delete_message, handle_edit_message, cancel_delete_message

from archive.models import Chat, Log
from game.models import Player, Variable

# Enable logging
logging.basicConfig(format=const.LOGGER_FORMAT, level=logging.INFO)
logger = logging.getLogger(__name__)


def start_command(_, update, job_queue):
    """Send a message when the command /start is issued."""
    message = update.message
    assert isinstance(message, telegram.Message)
    _ = partial(get_by_user, user=message.from_user)
    if not is_group_chat(message.chat):
        message.reply_text(_(Text.START_TEXT), parse_mode='HTML')
        return
    chat = get_chat(message.chat)
    if not chat.recording:
        chat.recording = True
        chat.save()
        message.chat.send_message('#start {}'.format(_(Text.START_RECORDING)))
    else:
        error_message(message, job_queue, _(Text.ALREADY_STARTED))


def save(_, update, job_queue):
    message = update.message
    assert isinstance(message, telegram.Message)
    _ = partial(get_by_user, user=message.from_user)
    if not is_group_chat(message.chat):
        return
    chat = get_chat(message.chat)
    if chat.recording:
        chat.recording = False
        chat.save_date = datetime.datetime.now()
        chat.save()
        message.chat.send_message('#save {}'.format(_(Text.SAVE)))
    else:
        error_message(message, job_queue, _(Text.ALREADY_SAVED))


def bot_help(_, update):
    """Send a message when the command /help is issued."""
    send_text = get_by_user(Text.HELP_TEXT, update.message.from_user)
    update.message.reply_text(send_text, parse_mode='HTML')


def handle_delete_callback(bot: telegram.Bot, query: telegram.CallbackQuery):
    def _(t: Text):
        return get_by_user(t, user=query.from_user)
    message = query.message
    assert isinstance(message, telegram.Message)
    deletion = Deletion.get(message.chat_id, message.message_id)
    if not deletion:
        query.answer(_(Text.INTERNAL_ERROR), alert=True)
        delete_message(message)
        return
    if deletion.user_id != query.from_user.id:
        query.answer(_(Text.MUST_SAME_USER))
        return
    delete_message(message)
    if query.data == 'delete:cancel':
        query.answer(_(Text.CANCELED))
    elif query.data == 'delete:confirm':
        deletion.do(bot)
        query.answer(_(Text.DELETED))


@run_async
def inline_callback(bot, update):
    query = update.callback_query
    assert isinstance(query, telegram.CallbackQuery)
    data = query.data or ''
    gm = is_gm(query.message.chat_id, query.from_user.id)
    if data.startswith('round'):
        round_inline_callback(bot, query, gm)
    elif data.startswith('hide_roll'):
        hide_roll_callback(bot, update)
    elif data.startswith('delete'):
        handle_delete_callback(bot, query)
    else:
        query.answer(show_alert=True, text=get_by_user(Text.UNKNOWN_COMMAND, query.from_user))


def delete_reply_markup(language_code: str):
    def _(t: Text):
        return get(t)
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(_(Text.CANCEL_DELETE), callback_data='delete:cancel'),
        InlineKeyboardButton(_(Text.CONFIRM_DELETE), callback_data='delete:confirm'),
    ]])


def handle_delete(
        bot: telegram.Bot,
        chat: Chat,
        message: telegram.Message,
        job_queue: telegram.ext.JobQueue,
        player: Player,
        **_):
    target = message.reply_to_message
    variables = pattern.VARIABLE_REGEX.findall(message.text)
    _ = partial(get_by_user, user=message.from_user)
    # delete variable
    if len(variables) > 0:
        target_player: Player = player
        if isinstance(target, telegram.Message):
            if not player.is_gm:
                return error_message(message, job_queue, _(Text.NOT_GM))
            if bot.id == target.from_user.id:
                log = Log.objects.filter(chat=chat, message_id=target.message_id, deleted=False).first()
                if not log:
                    return error_message(message, job_queue, _(Text.RECORD_NOT_FOUND))
                target_player = get_player_by_id(chat.chat_id, log.user_id)
            else:
                target_player = get_player_by_id(message.chat_id, target.from_user.id)
        if not target_player:
            return error_message(message, job_queue, _(Text.INVALID_TARGET))
        delete_log = ''
        variable_id_list = []
        for variable_name in variables:
            variable = Variable.objects.filter(name__iexact=variable_name, player=target_player).first()
            if not variable:
                continue
            if variable.value:
                delete_log += '${} = {}\n'.format(variable.name, variable.value)
            else:
                delete_log += '${}'.format(variable.name)
            variable_id_list.append(variable.id)
        if not variable_id_list:
            return error_message(message, job_queue, _(Text.NOT_FOUND_VARIABLE_TO_DELETE))
        delete_message(message)
        check_text = _(Text.CHECK_DELETE_VARIABLE).format(character=target_player.character_name)
        check_text += '\n<pre>{}</pre>'.format(delete_log)
        reply_markup = delete_reply_markup(message.from_user.language_code)
        deletion = Deletion(chat_id=message.chat_id, user_id=message.from_user.id, variable_id_list=variable_id_list)
    # delete message
    elif isinstance(target, telegram.Message):
        user_id = message.from_user.id
        log = Log.objects.filter(chat=chat, message_id=target.message_id).first()
        if log is None:
            error_message(message, job_queue, get_by_user(Text.RECORD_NOT_FOUND, message.from_user))
            return
        elif log.user_id != user_id and not is_gm(message.chat_id, user_id):
            error_message(message, job_queue, get_by_user(Text.HAVE_NOT_PERMISSION, message.from_user))
            return
        check_text = _(Text.DELETE_CHECK) + '\n\n{}'.format(target.caption_html or target.text_html)
        reply_markup = delete_reply_markup(message.from_user.language_code)
        deletion = Deletion(message.chat_id, message.from_user.id, message_list=[target.message_id])
    else:
        error_message(message, job_queue, get_by_user(Text.DELETE_USAGE, message.from_user))
        return
    delete_message(message)
    sent = message.chat.send_message(check_text, parse_mode='HTML', reply_markup=reply_markup)
    deletion.set(sent.message_id)
    delay_delete_message(job_queue, message.chat_id, sent.message_id, 30)


def handle_add_tag(bot: telegram.Bot, chat, job_queue, message: telegram.Message):
    target = message.reply_to_message

    _ = partial(get_by_user, user=message.from_user)
    if not isinstance(target, telegram.Message):
        return error_message(message, job_queue, _(Text.NEED_REPLY))

    assert isinstance(message.from_user, telegram.User)
    user_id = message.from_user.id
    log = Log.objects.filter(chat=chat, message_id=target.message_id).first()
    if log is None:
        error_message(message, job_queue, _(Text.RECORD_NOT_FOUND))
        return
    elif log.user_id != user_id:
        error_message(message, job_queue, _(Text.HAVE_NOT_PERMISSION))
        return

    assert isinstance(log, Log)
    tag_list = []
    if message.caption:
        text = message.caption
        entities = message.caption_entities
    else:
        text = message.text
        entities = message.entities
    for entity in entities:
        if isinstance(entity, telegram.MessageEntity) and entity.type == entity.HASHTAG:
            tag = text[entity.offset+1:entity.offset+entity.length]
            if tag:
                tag = get_tag(chat, tag)
                if tag not in log.tag.all():
                    tag_list.append(tag)
    if not tag_list:
        return error_message(message, job_queue, _(Text.NOT_TAG))

    tag_text = ''.join([' #{}'.format(tag.name) for tag in tag_list])

    if target.photo:
        edit_text = str(target.caption_html) + tag_text
        bot.edit_message_caption(
            chat_id=target.chat_id,
            message_id=target.message_id,
            caption=edit_text,
            parse_mode='HTML',
        )
    else:
        edit_text = str(target.text_html) + tag_text
        target.edit_text(edit_text, parse_mode='HTML')

    for tag in tag_list:
        log.tag.add(tag)

    log.save()
    delete_message(message)


def handle_edit(bot, chat, job_queue, message: telegram.Message, start: int, with_photo=None):
    target = message.reply_to_message

    _ = partial(get_by_user, user=message.from_user)
    if not isinstance(target, telegram.Message):
        return error_message(message, job_queue, _(Text.NEED_REPLY))

    assert isinstance(message.from_user, telegram.User)
    user_id = message.from_user.id
    log = Log.objects.filter(chat=chat, message_id=target.message_id).first()
    if log is None:
        error_message(message, job_queue, _(Text.RECORD_NOT_FOUND))
    elif log.user_id == user_id:
        rpg_message = RpgMessage(message, start)
        handle_say(bot, chat, job_queue, message, log.character_name, rpg_message, edit_log=log, with_photo=with_photo)
        delete_message(message)
    else:
        error_message(message, job_queue, _(Text.HAVE_NOT_PERMISSION))


def handle_lift(message: telegram.Message, job_queue, chat: Chat):
    assert isinstance(message, telegram.Message)
    reply_to = message.reply_to_message
    user_id = message.from_user.id
    _ = partial(get_by_user, user=message.from_user)
    if not isinstance(reply_to, telegram.Message):
        return error_message(message, job_queue, _(Text.NEED_REPLY))
    elif reply_to.from_user.id == message.bot.id:
        return error_message(message, job_queue, _(Text.NEED_REPLY_PLAYER_RECORD))
    elif reply_to.from_user.id != user_id and not is_gm(message.chat_id, user_id):
        return error_message(message, job_queue, _(Text.HAVE_NOT_PERMISSION))
    name = get_name(reply_to)
    if not name:
        return error_message(message, job_queue, _(Text.INVALID_TARGET))
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


message_handlers = [
    (re.compile(r'^[.。](rh?)\b'), handle_normal_roll),
    (re.compile(r'^[.。](hd)\b'), handle_normal_roll),
    (re.compile(r'^[.。](loh?)\b'), handle_loop_roll),
    (re.compile(r'^[.。](coch?[+\-]?h?)\s*'), handle_coc_roll),
    (re.compile(r'^[.。](init)\b'), handle_initiative),
    (re.compile(r'^[.。](set)\b'), handle_variable_assign),
    (re.compile(r'^[.。](list)\b'), handle_list_variables),
    (re.compile(r'^[.。](clear)\b'), handle_clear_variables),
    (re.compile(r'^[.。](as)\b'), handle_as_say),
    (re.compile(r'^[.。](del)\b'), handle_delete),
]


@run_async
def handle_message(bot, update: telegram.Update, job_queue):
    message: telegram.Message = update.message
    if update.edited_message:
        message = update.edited_message
        edit_log = Log.objects.filter(chat__chat_id=message.chat_id, source_message_id=message.message_id).first()
        cancel_delete_message(job_queue, message.chat_id, message. message_id)
    elif isinstance(message, telegram.Message):
        edit_log = None
    else:
        return
    _ = partial(get_by_user, user=message.from_user)

    language_code: str = message.from_user.language_code
    with_photo = handle_photo(message)
    text = message.text
    if with_photo:
        text = message.caption
    if not text or not text.startswith(('.', '。')):
        return
    # ignore ... or 。。
    if text.startswith(('。。', '..')) and not text.startswith(('。。me', '..me')):
        return
    if not is_group_chat(message.chat):
        message.reply_text(_(Text.NOT_GROUP))
        return
    elif not isinstance(message.from_user, telegram.User):
        return

    chat = get_chat(message.chat)
    player = get_player_by_id(message.chat_id, message.from_user.id)
    if not player:
        error_message(message, job_queue, _(Text.NOT_SET_NAME))
        return
    name = player.character_name

    for pat, handler in message_handlers:
        result = pattern.split(pat, text)
        if not result:
            continue
        command, start = result
        rest = text[start:]
        if handler is not handle_as_say:
            handle_edit_message(bot, edit_log)

        handler(
            bot=bot,
            chat=chat,
            player=player,
            command=command,
            start=start,
            name=name,
            text=rest,
            message=message,
            job_queue=job_queue,
            with_photo=with_photo,
            language_code=language_code,
            edit_log=edit_log,
        )
        return
    edit_command_matched = pattern.EDIT_COMMANDS_REGEX.match(text.lower())
    if edit_command_matched:
        command = edit_command_matched.group(1).lower()
        reply_to = message.reply_to_message
        if not chat.recording:
            error_message(message, job_queue, _(Text.RECORD_NOT_FOUND))
        elif not isinstance(reply_to, telegram.Message):
            error_message(message, job_queue, _(Text.NEED_REPLY))
        elif command == 'lift':
            handle_lift(message, job_queue, chat)
        elif reply_to.from_user.id != bot.id:
            error_message(message, job_queue, _(Text.NEED_REPLY_PLAYER_RECORD))
        elif command == 'edit':
            handle_edit(bot, chat, job_queue, message, start=edit_command_matched.end(),
                        with_photo=with_photo)
        elif command == 'tag':
            handle_add_tag(bot, chat, job_queue, message)
    else:
        rpg_message = RpgMessage(message, start=1)
        handle_say(bot, chat, job_queue, message, name, rpg_message, with_photo=with_photo, edit_log=edit_log)


def handle_photo(message: telegram.Message):
    photo_size_list = message.photo
    if len(photo_size_list) == 0:
        return None
    photo_size_list.sort(key=lambda p: p.file_size)
    return photo_size_list[-1]


def handle_error(_, update, bot_error):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, bot_error)


def handle_status(bot: telegram.Bot, update):
    assert isinstance(update.message, telegram.Message)
    message = update.message

    chat = get_chat(message.chat)
    if message.new_chat_title:
        chat.title = message.new_chat_title
        chat.save()
    if message.new_chat_members:
        for user in message.new_chat_members:
            if user.id == bot.id:
                admin = None
                for x in bot.get_chat_administrators(update.message.chat_id):
                    if isinstance(x, telegram.ChatMember):
                        admin = x.user
                        break
                message.chat.send_message(
                    get_by_user(Text.START_TEXT, admin),
                    parse_mode='HTML',
                    disable_web_page_preview=True
                )


def set_password(_, update, args, job_queue):
    message = update.message
    assert isinstance(message, telegram.Message)

    _ = partial(get_by_user, user=message.from_user)

    if len(args) > 1:
        text = _(Text.PASSWORD_USAGE)
        return error_message(message, job_queue, text)
    chat = get_chat(message.chat)
    if args:
        password = str(args[0])
        chat.password = sha256(password.encode()).hexdigest()
    else:
        chat.password = ''
    chat.save()
    message.reply_text(_(Text.PASSWORD_SUCCESS))


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
        Filters.text | Filters.photo | Filters.command,
        handle_message,
        channel_post_updates=False,
        pass_job_queue=True,
        edited_updates=True,
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
    if const.BOT_WEBHOOK_URL is not None:
        updater.start_webhook(listen='0.0.0.0', port=const.WEBHOOK_PORT, url_path=const.TOKEN)
        url = os.path.join(const.BOT_WEBHOOK_URL, const.TOKEN)
        updater.bot.set_webhook(url=url)
    else:
        updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()
