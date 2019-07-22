import pickle
import re
from typing import Optional, List
from uuid import uuid4

import telegram
from redis import Redis
from telegram import Bot
from django.conf import settings

from archive.models import Chat, Log

from entities import Me, Bold, Character, Span, Entities, Entity
from .const import TOKEN
from .patterns import ME_REGEX, VARIABLE_REGEX
from game.models import Player, Variable

bot = Bot(TOKEN)
redis = Redis(host=settings.REDIS_URL, port=settings.REDIS_PORT, db=settings.REDIS_DB)


class NotGm(Exception):
    pass


def is_group_chat(chat: telegram.Chat) -> bool:
    return isinstance(chat, telegram.Chat) and chat.type in ('supergroup', 'group')


def is_gm(chat_id: int, user_id: int) -> bool:
    player = Player.objects.filter(chat_id=chat_id, user_id=user_id).first()
    if not player:
        return False
    return player.is_gm


def get_chat(telegram_chat: telegram.Chat) -> 'Chat':
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


class RpgMessage:
    me = None
    variables = {}
    segments: List[Entity]
    entities: Entities

    def __init__(self, message: telegram.Message, start=0, temp_name=None):
        self.entities = Entities()
        self.start = start
        self.players = list(Player.objects.filter(chat_id=message.chat_id).all())
        for player in self.players:
            if player.user_id == message.from_user.id:
                self.me = Me(temp_name or player.character_name, player.id, player.full_name)
                self.variables = {}
                for variable in player.variable_set.all():
                    self.variables[variable.name.upper()] = variable.value
                break

        self.tags = []
        if message.caption:
            text = message.caption
            entities = message.caption_entities
        else:
            text = message.text
            entities = message.entities
        if not text:
            return
        assert isinstance(text, str)
        last_index = 0

        for entity in entities:
            assert isinstance(entity, telegram.MessageEntity)
            entity_offset = entity.offset
            entity_length = entity.length
            entity_end = entity_offset + entity_length
            if entity.type == entity.MENTION:
                self.push_text(text[last_index:entity_offset])
                mention = text[entity_offset:entity_end]
                self.push_mention(mention)
                last_index = entity_end
            elif entity.type == entity.TEXT_MENTION:
                self.push_text(text[last_index:entity_offset])
                self.push_text_mention(entity.user)
                last_index = entity_end
            elif entity.type == entity.HASHTAG:
                self.push_text(text[last_index:entity_offset])
                self.tags.append(text[entity_offset+1:entity_end])
                last_index = entity_end
            elif entity.type == entity.BOLD:
                self.push_text(text[last_index:entity_offset])
                self.entities.list.append(Bold(text[entity_offset:entity_end]))
                last_index = entity_end

        self.push_text(text[last_index:])
        if len(self.entities.list) > 0 and isinstance(self.entities.list[0], Span):
            v = self.entities.list[0].value
            if start < len(v):
                self.entities.list[0] = Span(v[start:])
            else:
                self.entities.list.pop(0)

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
            if not x:
                return
            resolved = self.resolve_variable(x)
            self.entities.list.append(Span(resolved))

        last_index = 0
        for match in ME_REGEX.finditer(text):
            push(text[last_index:match.start()])
            self.entities.list.append(self.me)
            last_index = match.end()
        push(text[last_index:])

    def push_mention(self, mention: str):
        username = mention[1:]  # skip @
        for player in self.players:
            if player.username == username:
                character = Character(player.character_name, player.id, player.full_name)
                return self.entities.list.append(character)
        return self.entities.list.append(Span(mention))

    def push_text_mention(self, user):
        for player in self.players:
            if player.user_id == user.id:
                character = Character(player.character_name, player.id, player.full_name)
                self.entities.list.append(character)
                return

    def has_me(self) -> bool:
        for segment in self.entities.list:
            if isinstance(segment, Me):
                return True
        return False

    def is_empty(self) -> bool:
        return len(self.entities.list) == 0

    def telegram_html_text(self) -> str:
        text = self.entities.telegram_html()
        if self.tags:
            tags = ' '.join(['#{}'.format(tag) for tag in self.tags])
            return '{} {}'.format(text, tags)
        else:
            return text


class HideRoll:
    expire_time = 30000
    REMOVE_TAG = re.compile(r'</?\w+>')

    def __init__(self, chat_id, text: str):
        self.chat_id = chat_id
        self._text = text
        self.id = uuid4()

    def key(self):
        return 'hide_roll:{}'.format(self.id)

    def set(self):
        payload = pickle.dumps(self)
        key = self.key()
        redis.set(key, payload)

    @property
    def text(self) -> str:
        return self.REMOVE_TAG.sub('', self._text)

    @staticmethod
    def get(key) -> Optional['HideRoll']:
        payload = redis.get(key)
        if not payload:
            return None
        return pickle.loads(payload)


class Deletion:
    expire_time = 300

    def __init__(self, chat_id, user_id, message_list=None, variable_id_list=None):
        self.chat_id = chat_id
        self.user_id = user_id
        self.message_list = message_list or []
        self.variable_id_list = variable_id_list or None

    @staticmethod
    def key(chat_id, message_id) -> str:
        return 'delete:{}:{}'.format(chat_id, message_id)

    @staticmethod
    def get(chat_id, message_id) -> Optional['Deletion']:
        payload = redis.get(Deletion.key(chat_id, message_id))
        if not payload:
            return None
        return pickle.loads(payload)

    def set(self, message_id):
        key = Deletion.key(self.chat_id, message_id)
        payload = pickle.dumps(self)
        redis.set(key, payload)
        redis.expire(key, self.expire_time)

    def do(self):
        for message_id in self.message_list:
            try:
                bot.delete_message(self.chat_id, message_id)
            except telegram.TelegramError:
                pass
        Log.objects.filter(chat__chat_id=self.chat_id, message_id__in=self.message_list).delete()
        if self.variable_id_list:
            Variable.objects.filter(id__in=self.variable_id_list).delete()
