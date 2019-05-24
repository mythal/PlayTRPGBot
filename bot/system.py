from functools import partial
from typing import Optional

import telegram
from redis import Redis
from telegram import TelegramError
from telegram.ext import JobQueue

from archive.models import Chat, Log
from .const import REDIS_HOST, REDIS_PORT, REDIS_DB
from .display import Text, get_by_user
from .pattern import ME_REGEX, VARIABLE_REGEX
from game.models import Player


class NotGm(Exception):
    pass


def is_group_chat(chat: telegram.Chat) -> bool:
    return isinstance(chat, telegram.Chat) and chat.type in ('supergroup', 'group')


def delete_message(message: telegram.Message):
    _ = partial(get_by_user, user=message.from_user)

    try:
        message.delete()
    except TelegramError:
        try:
            message.reply_text(_(Text.DELETE_FAIL))
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
    _ = partial(get_by_user, user=message.from_user)
    delete_time = 15
    try:
        send_text = '<b>[{}]</b> {}'.format(
            _(Text.ERROR),
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


def get_player_by_username(chat_id, username: str) -> Optional[Player]:
    if username.startswith('@'):
        username = username[1:]
    if not username:
        return None
    return Player.objects.filter(username=username, chat_id=chat_id).first()


def get_player_by_id(chat_id, user_id) -> Optional[Player]:
    if not user_id:
        return None
    return Player.objects.filter(user_id=user_id, chat_id=chat_id).first()


class Me:
    def __init__(self, player):
        self.player = player


class Bold:
    def __init__(self, text):
        self.bold = text


class RpgMessage:
    me = None
    variables = {}

    def __init__(self, message: telegram.Message, start=0):
        self.start = start
        self.players = list(Player.objects.filter(chat_id=message.chat_id).all())
        for player in self.players:
            if player.user_id == message.from_user.id:
                self.me = Me(player)
                self.variables = {}
                for variable in player.variable_set.all():
                    self.variables[variable.name.upper()] = variable.value

        self.segments = []
        self.tags = []
        if not message.text:
            return
        assert isinstance(message.text, str)
        last_index = 0

        for entity in message.entities:
            assert isinstance(entity, telegram.MessageEntity)
            entity_offset = entity.offset
            entity_length = entity.length
            entity_end = entity_offset + entity_length
            if entity.type == entity.MENTION:
                self.push_text(message.text[last_index:entity_offset])
                mention = message.text[entity_offset:entity_end]
                self.push_mention(mention)
                last_index = entity_end
            elif entity.type == entity.TEXT_MENTION:
                self.push_text(message.text[last_index:entity_offset])
                self.push_text_mention(entity.user)
                last_index = entity_end
            elif entity.type == entity.HASHTAG:
                self.push_text(message.text[last_index:entity_offset])
                self.tags.append(message.text[entity_offset+1:entity_end])
                last_index = entity_end
            elif entity.type == entity.BOLD:
                self.push_text(message.text[last_index:entity_offset])
                self.segments.append(Bold(message.text[entity_offset:entity_end]))
                last_index = entity_end

        self.push_text(message.text[last_index:])
        if len(self.segments) > 0 and isinstance(self.segments[0], str):
            if start < len(self.segments[0]):
                self.segments[0] = self.segments[0][start:]
            else:
                self.segments.pop(0)

    def replace_variable(self, matched):
        return self.variables.get(matched.group(1).upper(), matched.group(0))

    def resolve_variable(self, text: str):
        counter = 16
        text = VARIABLE_REGEX.sub(self.replace_variable, text, count=counter)
        extra_resolve_level = 3
        for _ in range(extra_resolve_level):
            if len(text) > 256:
                break
            text = VARIABLE_REGEX.sub(self.replace_variable, text, count=counter)
        return text

    def push_text(self, text: str):
        def push(x: str):
            if x:
                self.segments.append(self.resolve_variable(x))

        last_index = 0
        for match in ME_REGEX.finditer(text):
            push(text[last_index:match.start()])
            self.segments.append(self.me)
            last_index = match.end()
        push(text[last_index:])

    def push_mention(self, mention: str):
        username = mention[1:]  # skip @
        for player in self.players:
            if player.username == username:
                return self.segments.append(player)
        return self.segments.append(mention)

    def push_text_mention(self, user):
        for player in self.players:
            if player.user_id == user.id:
                self.segments.append(player)
                return

    def has_me(self) -> bool:
        for segment in self.segments:
            if isinstance(segment, Me):
                return True
        return False

    def is_empty(self) -> bool:
        return len(self.segments) == 0

    def html_text(self) -> str:
        text = ''
        for segment in self.segments:
            if isinstance(segment, str):
                text += segment
            elif isinstance(segment, Me):
                text += '<b>{}</b>'.format(segment.player.character_name)
            elif isinstance(segment, Player):
                text += '<b>{}</b>'.format(segment.character_name)
            elif isinstance(segment, Bold):
                text += '<b>{}</b>'.format(segment.bold)
        text = text.strip()
        if self.tags:
            return '{} // {}'.format(text, ' '.join(['#{}'.format(tag) for tag in self.tags]))
        else:
            return text


redis = Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
