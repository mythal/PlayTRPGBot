from functools import partial

import telegram
from telegram.ext import JobQueue

from bot.tasks import edit_message, edit_message_photo, edit_message_caption, delete_message, \
    error_message, set_photo
from archive.models import LogKind, Log, Tag, Chat
from . import display, patterns
from .character_name import set_temp_name, get_temp_name
from .system import RpgMessage, is_gm, bot
from .display import Text, get_by_user


def get_symbol(chat_id, user_id) -> str:
    symbol = ''
    if is_gm(chat_id, user_id):
        symbol = display.GM_SYMBOL
    return symbol + ' '


def is_empty_message(text):
    return patterns.ME_REGEX.sub('', text).strip() == ''


def handle_as_say(chat, job_queue: JobQueue, message: telegram.Message, start: int, name: str, with_photo=None,
                  edit_log=None, **_):
    user_id = message.from_user.id

    _ = partial(get_by_user, user=message.from_user)
    match = patterns.AS_REGEX.match(message.caption or message.text)

    if match:
        temp_name = match.group(1).strip()
        if temp_name.strip() == '':
            return error_message(job_queue, message, _(Text.EMPTY_NAME))
        set_temp_name(chat.chat_id, user_id, temp_name)
        handle_say(job_queue, chat, message, temp_name, edit_log=edit_log, with_photo=with_photo,
                   start=match.end(), temp_name=temp_name)
    else:
        temp_name = get_temp_name(chat.chat_id, user_id) or ''
        if temp_name == '':
            return error_message(job_queue, message, _(Text.AS_SYNTAX_ERROR))
        handle_say(job_queue, chat, message, name, edit_log=edit_log, with_photo=with_photo,
                   start=start, temp_name=temp_name)


def get_tag(chat: Chat, name: str):
    tag, _ = Tag.objects.update_or_create(chat=chat, name=name)
    return tag


def handle_say(job_queue: JobQueue, chat: Chat, message: telegram.Message, name: str, edit_log=None,
               with_photo=None, temp_name=None, start=0):
    _ = partial(get_by_user, user=message.from_user)
    rpg_message = RpgMessage(message, start, temp_name)
    user_id = message.from_user.id
    gm = is_gm(message.chat_id, user_id)

    kind = LogKind.NORMAL.value

    text = rpg_message.telegram_html_text().strip()

    if not text and not with_photo:
        error_message(job_queue, message, _(Text.EMPTY_MESSAGE))
        return

    if rpg_message.has_me():
        kind = LogKind.ME.value
        send_text = text
    else:
        send_text = '<b>{}</b>: {}'.format(temp_name or name, text)
    symbol = get_symbol(message.chat_id, user_id)
    send_text = symbol + send_text

    if isinstance(edit_log, Log):
        return on_edit(job_queue, chat, edit_log, kind, message, rpg_message, send_text, text, with_photo)

    # set reply log
    reply_log = None
    target = message.reply_to_message
    if isinstance(target, telegram.Message) and target.from_user.id == bot.id:
        reply_to_message_id = target.message_id
        reply_log = Log.objects.filter(chat=chat, message_id=reply_to_message_id).first()

    if not chat.recording:
        send_text = '[{}] '.format(_(Text.NOT_RECORDING)) + send_text

    send_and_record(job_queue, chat, gm, kind, message, name, reply_log, rpg_message, send_text, temp_name,
                    text, with_photo)


def send_and_record(job_queue: JobQueue, chat, gm, kind, message: telegram.Message, name, reply_log, rpg_message, send_text, temp_name,
                    content, with_photo):
    reply_to_message_id = None
    if isinstance(reply_log, Log):
        reply_to_message_id = reply_log.message_id
    # send message
    if isinstance(with_photo, telegram.PhotoSize):
        sent = message.chat.send_photo(
            photo=with_photo,
            caption=send_text,
            reply_to_message_id=reply_to_message_id,
            parse_mode='HTML',
        )
    else:
        sent = message.chat.send_message(
            send_text,
            reply_to_message_id=reply_to_message_id,
            parse_mode='HTML',
        )
    if not chat.recording:
        return
    # record log
    created_log = Log.objects.create(
        message_id=sent.message_id,
        source_message_id=message.message_id,
        chat=chat,
        user_id=message.from_user.id,
        user_fullname=message.from_user.full_name,
        kind=kind,
        reply=reply_log,
        entities=rpg_message.entities.to_object(),
        character_name=name,
        temp_character_name=temp_name or '',
        content=content,
        gm=gm,
        created=message.date,
    )
    for name in rpg_message.tags:
        created_log.tag.add(get_tag(chat, name))
    created_log.save()
    # download and write photo file
    if with_photo:
        set_photo(job_queue, created_log.id, with_photo.file_id)
    delete_message(job_queue, message.chat_id, message.message_id, 10)
    chat.save()


def on_edit(job_queue: JobQueue, chat: Chat, edit_log: Log, kind, message, rpg_message: RpgMessage, send_text, text,
            with_photo):
    assert isinstance(edit_log, Log)
    chat_id = message.chat_id
    message_id = edit_log.message_id
    if edit_log.media:
        if isinstance(with_photo, telegram.PhotoSize):
            edit_message_photo(job_queue, chat_id, message_id, with_photo.file_id)
            set_photo(job_queue, edit_log.id, with_photo.file_id)
        edit_message_caption(job_queue, chat_id, message_id, send_text)
    else:
        edit_message(job_queue, chat_id, message_id, send_text)
    edit_log.tag.clear()
    for tag_name in rpg_message.tags:
        tag = get_tag(chat, tag_name)
        edit_log.tag.add(tag)
    edit_log.content = text
    edit_log.entities = rpg_message.entities.to_object()
    edit_log.kind = kind
    edit_log.save()
    delete_message(job_queue, message.chat_id, message.message_id, 25)
    chat.save()
    return
