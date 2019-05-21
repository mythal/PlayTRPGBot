
import telegram
from redis import Redis
from telegram import TelegramError
from telegram.ext import JobQueue

from archive.models import Chat, Log
from .const import REDIS_HOST, REDIS_PORT, REDIS_DB
from .display import Text, get
from game.models import Player


class NotGm(Exception):
    pass


def is_group_chat(chat: telegram.Chat) -> bool:
    return isinstance(chat, telegram.Chat) and chat.type in ('supergroup', 'group')


def delete_message(message: telegram.Message):
    try:
        message.delete()
    except TelegramError:
        try:
            message.reply_text(get(Text.DELETE_FAIL))
        except TelegramError:
            pass


def is_gm(chat_id: int, user_id: int) -> bool:
    player = Player.objects.filter(chat_id=chat_id, user_id=user_id).first()
    if not player:
        return False
    return player.is_gm


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


def is_author(message_id, user_id):
    return bool(Log.objects.filter(message_id=message_id, user_id=user_id).first())


def error_message(message: telegram.Message, job_queue: JobQueue, text: str):
    delete_time = 15
    try:
        send_text = '<b>[{}]</b> {}'.format(
            get(Text.ERROR),
            text,
        )
        sent = message.reply_text(send_text, parse_mode='HTML')
    except TelegramError:
        return
    context = dict(
        chat_id=message.chat_id,
        message_id_list=(message.message_id, sent.message_id),
    )
    job_queue.run_once(delay_delete_messages, delete_time, context=context)


def delay_delete_messages(bot: telegram.Bot, job):
    chat_id = job.context['chat_id']
    for message_id in job.context['message_id_list']:
        try:
            bot.delete_message(chat_id, message_id)
        except TelegramError:
            pass


def message_text_convert(message: telegram.Message) -> str:
    if not message.text:
        return ''
    assert isinstance(message.text, str)
    last_index = 0
    segments = []

    def push_name(pushed_player: Player):
        segments.append('<b>{}</b>'.format(pushed_player.character_name))

    for entity in message.entities:
        assert isinstance(entity, telegram.MessageEntity)
        entity_offset = entity.offset
        entity_length = entity.length
        entity_end = entity_offset + entity_length
        if entity.type == entity.MENTION:
            segments.append(message.text[last_index:entity_offset])
            mention = message.text[entity_offset:entity_end]
            username = mention[1:]  # skip @
            player = Player.objects.filter(chat_id=message.chat_id, username=username).first()
            push_name(player)
            last_index = entity_end
        elif entity.type == entity.TEXT_MENTION:
            player = Player.objects.filter(chat_id=message.chat_id, user_id=entity.user.id).first()
            if not player:
                continue
            segments.append(message.text[last_index:entity_offset])
            push_name(player)
            last_index = entity_end
    segments.append(message.text[last_index:])
    return ''.join(segments)


redis = Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
