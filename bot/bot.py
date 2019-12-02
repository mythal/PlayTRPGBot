import datetime
import logging
import re
from hashlib import sha256
from functools import partial

import telegram
from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler, CallbackContext
from django.conf import settings

from bot.say import handle_as_say, handle_say, get_tag
from bot.system import Deletion
from bot.variable import handle_list_variables, handle_variable_assign, handle_clear_variables
from .roll import set_dice_face, handle_coc_roll, handle_loop_roll, handle_normal_roll, hide_roll_callback, \
    handle_set_dice_face
from .character_name import set_name, get_name
from .round_counter import round_inline_callback, start_round, hide_round,\
    public_round, next_turn, handle_initiative
from . import patterns
from .display import Text, get_by_user, get
from .system import Context, is_group_chat, is_gm, get_chat, get_player_by_id
from bot.tasks import send_message, delete_message, cancel_delete_message, after_edit_delete_previous_message, \
    error_message

from archive.models import Chat, Log
from game.models import Player, Variable

logger = logging.getLogger(__name__)


def login_button():
    button = telegram.InlineKeyboardButton('Login Log Archives')
    button.login_url = {
        'url': '{}/telegram-login/'.format(settings.ARCHIVE_URL),
        'request_write_access': True,
    }
    return telegram.InlineKeyboardMarkup([[
        button,
    ]])


def start_command(update, _context: CallbackContext):
    """Send a message when the command /start is issued."""
    message = update.message
    assert isinstance(message, telegram.Message)
    return handle_start(message=message)


def handle_start(message: telegram.Message, **_kwargs):
    _ = partial(get_by_user, user=message.from_user)
    if not is_group_chat(message.chat):
        send_message(message.chat_id, _(Text.START_TEXT), reply_to=message.message_id)
        return
    chat = get_chat(message.chat)
    if not chat.recording:
        chat.recording = True
        chat.save()
        send_message(message.chat_id, '#start {}'.format(_(Text.START_RECORDING)))
    else:
        error_message(message, _(Text.ALREADY_STARTED))


def save_command(update, _context: CallbackContext):
    message = update.message
    assert isinstance(message, telegram.Message)
    return handle_save(message=message)


def handle_save(message: telegram.Message, **_kwargs):
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
        error_message(message, _(Text.ALREADY_SAVED))


def help_command(update, _context: CallbackContext):
    """Send a message when the command /help is issued."""
    return handle_help(update.message)


def handle_help(message: telegram.Message, **_kwargs):
    send_text = get_by_user(Text.HELP_TEXT, message.from_user)
    message.reply_text(send_text, parse_mode='HTML', reply_markup=login_button())


def handle_delete_callback(_bot: telegram.Bot, query: telegram.CallbackQuery):
    def _(t: Text):
        return get_by_user(t, user=query.from_user)
    message = query.message
    assert isinstance(message, telegram.Message)
    deletion = Deletion.get(message.chat_id, message.message_id)
    if not deletion:
        query.answer(_(Text.INTERNAL_ERROR), alert=True)
        delete_message(message.chat_id, message.message_id)
        return
    if deletion.user_id != query.from_user.id:
        query.answer(_(Text.MUST_SAME_USER))
        return
    delete_message(message.chat_id, message.message_id)
    if query.data == 'delete:cancel':
        query.answer(_(Text.CANCELED))
    elif query.data == 'delete:confirm':
        deletion.do()
        query.answer(_(Text.DELETED))


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
        return get(t, language_code)
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(_(Text.CANCEL_DELETE), callback_data='delete:cancel'),
        InlineKeyboardButton(_(Text.CONFIRM_DELETE), callback_data='delete:confirm'),
    ]])


def handle_delete(
        bot: telegram.Bot,
        chat: Chat,
        message: telegram.Message,
        player: Player,
        **_):
    target = message.reply_to_message
    variables = patterns.VARIABLE_REGEX.findall(message.text)
    _ = partial(get_by_user, user=message.from_user)
    # delete variable
    if len(variables) > 0:
        target_player: Player = player
        if isinstance(target, telegram.Message):
            if not player.is_gm:
                return error_message(message, _(Text.NOT_GM))
            if bot.id == target.from_user.id:
                log = Log.objects.filter(chat=chat, message_id=target.message_id, deleted=False).first()
                if not log:
                    return error_message(message, _(Text.RECORD_NOT_FOUND))
                target_player = get_player_by_id(chat.chat_id, log.user_id)
            else:
                target_player = get_player_by_id(message.chat_id, target.from_user.id)
        if not target_player:
            return error_message(message, _(Text.INVALID_TARGET))
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
            return error_message(message, _(Text.NOT_FOUND_VARIABLE_TO_DELETE))
        delete_message(message.chat_id, message.message_id)
        check_text = _(Text.CHECK_DELETE_VARIABLE).format(character=target_player.character_name)
        check_text += '\n<pre>{}</pre>'.format(delete_log)
        reply_markup = delete_reply_markup(message.from_user.language_code)
        deletion = Deletion(chat_id=message.chat_id, user_id=message.from_user.id, variable_id_list=variable_id_list)
    # delete message
    else:
        user_id = message.from_user.id
        if isinstance(target, telegram.Message):
            log = Log.objects.filter(chat=chat, message_id=target.message_id).first()
        else:
            log = Log.objects.filter(chat=chat, user_id=user_id).order_by('-created').first()
        if log is None:
            error_message(message, get_by_user(Text.RECORD_NOT_FOUND, message.from_user))
            return
        elif log.user_id != user_id and not is_gm(message.chat_id, user_id):
            error_message(message, get_by_user(Text.HAVE_NOT_PERMISSION, message.from_user))
            return
        character_name = "<b>{}</b>".format(log.temp_character_name or log.character_name)
        check_text = _(Text.DELETE_CHECK) + '\n\n[{}] {}'.format(character_name, log.content)
        reply_markup = delete_reply_markup(message.from_user.language_code)
        deletion = Deletion(message.chat_id, message.from_user.id, message_list=[log.message_id])
    delete_message(message.chat_id, message.message_id)
    sent = message.chat.send_message(check_text, parse_mode='HTML', reply_markup=reply_markup)
    deletion.set(sent.message_id)
    delete_message(message.chat_id, sent.message_id, 30)


def handle_add_tag(bot: telegram.Bot, chat, message: telegram.Message, **_kwargs):
    target = message.reply_to_message

    _ = partial(get_by_user, user=message.from_user)
    if not chat.recording:
        return error_message(message, _(Text.RECORD_NOT_FOUND))
    elif not isinstance(target, telegram.Message):
        return error_message(message, _(Text.NEED_REPLY))
    elif target.from_user.id != bot.id:
        return error_message(message, _(Text.NEED_REPLY_PLAYER_RECORD))
    assert isinstance(message.from_user, telegram.User)
    user_id = message.from_user.id
    log = Log.objects.filter(chat=chat, message_id=target.message_id).first()
    if log is None:
        error_message(message, _(Text.RECORD_NOT_FOUND))
        return
    elif log.user_id != user_id:
        error_message(message, _(Text.HAVE_NOT_PERMISSION))
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
        return error_message(message, _(Text.NOT_TAG))

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
    chat.save()
    delete_message(message.chat_id, message.message_id)


def handle_edit(chat, bot, message: telegram.Message, start: int, with_photo=None, **_kwargs):
    target = message.reply_to_message
    assert isinstance(message.from_user, telegram.User)
    user_id = message.from_user.id

    _ = partial(get_by_user, user=message.from_user)

    if not chat.recording:
        return error_message(message, _(Text.RECORD_NOT_FOUND))

    if not isinstance(target, telegram.Message):
        log = Log.objects.filter(chat=chat, user_id=user_id).order_by('-created').first()
        if not log:
            return error_message(message, _(Text.NEED_REPLY))
    elif target.from_user.id == bot.id:
        log = Log.objects.filter(chat=chat, message_id=target.message_id).first()
        if not log:
            return error_message(message, _(Text.RECORD_NOT_FOUND))
    else:
        return error_message(message, _(Text.NEED_REPLY_PLAYER_RECORD))

    if log.user_id != user_id:
        return error_message(message, _(Text.HAVE_NOT_PERMISSION))
    handle_say(chat, message, log.character_name, edit_log=log, with_photo=with_photo, start=start)


def handle_lift(message: telegram.Message, chat: Chat, **_kwargs):
    assert isinstance(message, telegram.Message)
    reply_to = message.reply_to_message
    user_id = message.from_user.id
    _ = partial(get_by_user, user=message.from_user)
    if not chat.recording:
        return error_message(message, _(Text.RECORD_NOT_FOUND))
    elif not isinstance(reply_to, telegram.Message):
        return error_message(message, _(Text.NEED_REPLY))
    elif reply_to.from_user.id == message.bot.id:
        return error_message(message, _(Text.NEED_REPLY_PLAYER_RECORD))
    elif reply_to.from_user.id != user_id and not is_gm(message.chat_id, user_id):
        return error_message(message, _(Text.HAVE_NOT_PERMISSION))
    name = get_name(reply_to)
    if not name:
        return error_message(message, _(Text.INVALID_TARGET))
    with_photo = get_maximum_photo(reply_to)
    handle_say(chat, reply_to, name, with_photo=with_photo)
    delete_message(reply_to.chat_id, reply_to.message_id)
    delete_message(message.chat_id, message.message_id)


message_handlers = [
    (re.compile(r'^[.。](start)\b'), handle_start),
    (re.compile(r'^[.。](save)\b'), handle_save),
    (re.compile(r'^[.。](help)\b'), handle_help),
    (re.compile(r'^[.。](face)\s+'), handle_set_dice_face),
    (re.compile(r'^[.。[【](rh?)\b'), handle_normal_roll),
    (re.compile(r'^[.。[【](hd)\b'), handle_normal_roll),
    (re.compile(r'^[.。[【](loh?)\b'), handle_loop_roll),
    (re.compile(r'^[.。[【](coch?[+\-]?h?)\s*'), handle_coc_roll),
    (re.compile(r'^[.。[【](init)\b'), handle_initiative),
    (re.compile(r'^[.。[【](set)\b'), handle_variable_assign),
    (re.compile(r'^[.。[【](list)\b'), handle_list_variables),
    (re.compile(r'^[.。[【](clear)\b'), handle_clear_variables),
    (re.compile(r'^[.。[【](as)\b'), handle_as_say),
    (re.compile(r'^[.。[【](del)\b'), handle_delete),
    (re.compile(r'^[.。[【](lift)\b'), handle_lift),
    (re.compile(r'^[.。[【](edit)\b'), handle_edit),
    (re.compile(r'^[.。[【](tag)\b'), handle_add_tag),
]


def start_gm_mode(bot: telegram.Bot, message: telegram.Message, chat: Chat):
    _ = partial(get_by_user, user=message.from_user)
    if chat.gm_mode:
        return
    chat.gm_mode = True
    chat.save()
    sent = bot.send_message(chat.chat_id, _(Text.START_GM_MODE), parse_mode='HTML')
    chat.gm_mode_notice = sent.message_id
    chat.save()


def finish_gm_mode(message: telegram.Message, chat: Chat):
    _ = partial(get_by_user, user=message.from_user)
    if chat.gm_mode:
        if chat.gm_mode_notice:
            delete_message(chat.chat_id, chat.gm_mode_notice, 20)
        chat.gm_mode = False
        chat.gm_mode_notice = None
        chat.save()

    send_message(chat.chat_id, _(Text.FINISH_GM_MODE), delete_after=20)
    delete_message(message.chat_id, message.message_id)


def is_start_gm_mode(text: str) -> bool:
    return text.startswith(('[', '【'))


def is_finish_gm_mode(text: str) -> bool:
    text = text.rstrip()
    return len(text) > 0 and (text[-1] == ']' or text[-1] == '】')


def is_ellipsis(text: str) -> bool:
    text = text.replace('。', '.')
    return text.startswith('..') and not text.startswith('..me')


def is_command(text: str) -> bool:
    return text.startswith(('.', '。'))


def handle_message(update: telegram.Update, context: CallbackContext):
    bot = context .bot
    message: telegram.Message = update.message

    edit_log = None
    if update.edited_message:
        message = update.edited_message
        edit_log = Log.objects.filter(chat__chat_id=message.chat_id, source_message_id=message.message_id).first()
        cancel_delete_message(message.chat_id, message. message_id)
    elif not isinstance(message, telegram.Message):
        return
    elif not isinstance(message.from_user, telegram.User):
        return
    language_code: str = message.from_user.language_code

    def _(x: Text):
        return get(x, language_code)

    with_photo = get_maximum_photo(message)
    text = message.text
    if with_photo:
        text = message.caption

    if not isinstance(text, str):
        return
    # ignore ellipsis
    elif is_ellipsis(text):
        return

    if not is_group_chat(message.chat):
        message.reply_text(_(Text.NOT_GROUP))
        return

    chat = get_chat(message.chat)
    player = get_player_by_id(message.chat_id, message.from_user.id)

    # handle GM mode
    if player and player.is_gm and (is_start_gm_mode(text) or is_finish_gm_mode(text)):
        if is_start_gm_mode(text):
            start_gm_mode(bot, message, chat)
            if len(text.rstrip()) == 1:
                delete_message(message.chat_id, message.message_id)
                return
        elif is_finish_gm_mode(text):
            finish_gm_mode(message, chat)
            return
    # not start with . / 。, ignore
    elif not is_command(text):
        return

    # user hasn't set name
    if not player:
        error_message(message, _(Text.NOT_SET_NAME))
        return

    # in the GM mode
    if chat.gm_mode and not player.is_gm and not edit_log:
        if is_command(text):
            send_message(
                chat.chat_id,
                _(Text.PLAYER_IN_THE_GM_MODE),
                reply_to=message.message_id,
                delete_after=5
            )
        return

    name = player.character_name

    for pattern, handler in message_handlers:
        result = patterns.split(pattern, text)
        if not result:
            continue
        command, start = result
        rest = text[start:]
        if handler is not handle_as_say and edit_log:
            after_edit_delete_previous_message(edit_log.id)

        handler(
            bot=bot,
            chat=chat,
            player=player,
            command=command,
            start=start,
            name=name,
            text=rest,
            message=message,
            job_queue=context.job_queue,
            with_photo=with_photo,
            language_code=language_code,
            edit_log=edit_log,
            context=Context(bot, chat, player, command, name, start, rest, message,
                            context.job_queue, language_code, with_photo, edit_log)
        )
        return
    handle_say(chat, message, name, edit_log=edit_log, with_photo=with_photo, start=1)


def get_maximum_photo(message: telegram.Message):
    photo_size_list = message.photo
    if len(photo_size_list) == 0:
        return None
    photo_size_list.sort(key=lambda p: p.file_size)
    return photo_size_list[-1]


def handle_error(update, context: CallbackContext):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, context.error)


def handle_status(update, _context: CallbackContext):
    assert isinstance(update.message, telegram.Message)
    message = update.message

    chat = get_chat(message.chat)
    if message.new_chat_title:
        chat.title = message.new_chat_title
        chat.save()


def new_member(update, context: CallbackContext):
    for member in update.message.new_chat_members:
        if member.id == context.bot.id:
            return handle_help(message=update.message)


def set_password(update, context: CallbackContext):
    message = update.message
    assert isinstance(message, telegram.Message)
    args = context.args
    _ = partial(get_by_user, user=message.from_user)

    if len(args) > 1:
        text = _(Text.PASSWORD_USAGE)
        return error_message(message, text)
    chat = get_chat(message.chat)
    if args:
        password = str(args[0])
        chat.password = sha256(password.encode()).hexdigest()
    else:
        chat.password = ''
    chat.save()
    send_message(message.chat_id, _(Text.PASSWORD_SUCCESS), message.message_id)


def run_bot():
    """Start the bot."""
    # Create the EventHandler and pass it your bot's token.
    updater = Updater(settings.BOT_TOKEN, use_context=True)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start_command))
    dp.add_handler(CommandHandler("save", save_command))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler('face', set_dice_face, pass_args=True))
    dp.add_handler(CommandHandler('name', set_name, pass_args=True))
    dp.add_handler(CommandHandler('round', start_round))
    dp.add_handler(CommandHandler('public', public_round))
    dp.add_handler(CommandHandler('hide', hide_round))
    dp.add_handler(CommandHandler('next', next_turn))
    dp.add_handler(CommandHandler('password', set_password, pass_args=True))
    dp.add_handler(MessageHandler(
        Filters.text | Filters.photo | Filters.command,
        handle_message,
        pass_job_queue=True,
    ))
    dp.add_handler(MessageHandler(Filters.status_update.new_chat_members, new_member))
    dp.add_handler(MessageHandler(Filters.status_update, handle_status))
    dp.add_handler(CallbackQueryHandler(inline_callback))
    # log all errors
    dp.add_error_handler(handle_error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()
