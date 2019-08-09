# Graphene Documents https://graphene-python.org/
from typing import Optional, List
import datetime

import graphene
from graphene import NonNull
from graphene_django import DjangoObjectType
from django.core.cache import cache
from django.http import HttpRequest

from archive import models as archive
from game import models as game
from user import models as user

Kind = graphene.Enum.from_enum(archive.LogKind)


def get_telegram_profile(request: HttpRequest) -> Optional[user.TelegramProfile]:
    if not request.user.is_authenticated:
        return None
    return getattr(request.user, 'telegram', None)


class Tag(DjangoObjectType):
    class Meta:
        model = archive.Tag


class Log(DjangoObjectType):
    class Meta:
        model = archive.Log
        exclude_fields = ('user_id', 'log_set', 'deleted')

    kind = Kind()
    entities = graphene.String(required=True)


class Player(DjangoObjectType):
    class Meta:
        model = game.Player


class Variable(DjangoObjectType):
    class Meta:
        model = game.Variable


class VariableMutation(graphene.Mutation):
    class Arguments:
        telegram_chat_id = graphene.ID(required=True)
        variable_id = graphene.ID(name='id')
        name = graphene.String()
        value = graphene.String()
        group = graphene.String()

    variable = graphene.Field(Variable)
    error = graphene.String()

    def mutate(self, info, telegram_chat_id, variable_id=None, name='', value='', group=''):
        my_profile = get_telegram_profile(info.context)
        if not my_profile:
            return VariableMutation(variable=None, error='You not logged in.')
        my_player = game.Player.objects.get(chat_id=telegram_chat_id, user_id=my_profile.user_id)
        if variable_id:
            variable = game.Variable.objects.get(pk=variable_id)
            if variable.player_id != my_player.id and not my_player.is_gm:
                return VariableMutation(variable=None, error='No permission.')
            if name:
                variable.name = name
            if value:
                variable.value = value
            if group:
                variable.group = group
            variable.save()
        else:
            if not name:
                return VariableMutation(variable=None, error='Create variable needs name.')
            variable = game.Variable(player=my_player, name=name, value=value, group=group)
            variable.save()
        return VariableMutation(variable=variable)


class Chat(DjangoObjectType):
    class Meta:
        model = archive.Chat
        exclude_fields = ('password', 'parent')

    log_list = graphene.Field(graphene.List(NonNull(Log), required=True), password=graphene.String())
    is_require_password = graphene.Boolean(required=True)
    counter = graphene.Int(required=True)
    page_counter = graphene.Int(required=True)
    players = graphene.Field(graphene.List(NonNull(Player), required=True))

    @staticmethod
    def resolve_players(chat: archive.Chat, info):
        return game.Player.objects.filter(chat_id=chat.chat_id).all()

    @staticmethod
    def resolve_is_require_password(chat: archive.Chat, info):
        return bool(chat.password)

    @staticmethod
    def resolve_log_list(chat: archive.Chat, info, password=''):
        log_list_cache_time_key = 'api:chat:{}:log:cache_time'.format(chat.id)
        log_list_key = 'api:chat:{}:log'.format(chat.id)
        log_list_cache_time: datetime.datetime = cache.get(log_list_cache_time_key, datetime.datetime.min)
        log_list: Optional[List[archive.Log]] = cache.get(log_list_key)

        if not chat.validate(password):
            return None

        if log_list and log_list_cache_time > chat.modified:
            return log_list
        log_list = list(chat.query_log().all())

        cache.set(log_list_key, log_list, 5 * 24 * 60 * 60)
        cache.set(log_list_cache_time_key, datetime.datetime.now())
        return log_list

    @staticmethod
    def resolve_counter(chat: archive.Chat, info):
        return chat.log_count()


class TelegramProfile(DjangoObjectType):
    player_set = graphene.Field(graphene.List(Player, required=True))

    @staticmethod
    def resolve_player_set(profile: user.TelegramProfile, info):
        return game.Player.objects.filter(user_id=profile.telegram_id).all()

    class Meta:
        model = user.TelegramProfile


class Query(graphene.ObjectType):
    chats = graphene.List(NonNull(Chat), required=True)
    chat = graphene.Field(Chat, chat_id=graphene.ID(name='id', required=True))
    player = graphene.Field(Player, player_id=graphene.ID(name='id', required=True))
    my_profile = graphene.Field(TelegramProfile)

    @staticmethod
    def resolve_my_profile(root, info):
        return get_telegram_profile(info.context)

    @staticmethod
    def resolve_chats(root, info):
        return archive.Chat.objects.filter(parent=None).all()

    @staticmethod
    def resolve_chat(root, info, chat_id: str):
        return archive.Chat.objects.filter(id=chat_id).first()

    @staticmethod
    def resolve_player(root, info, player_id: str):
        return game.Player.objects.filter(id=player_id).first()


class Mutation(graphene.ObjectType):
    variable = VariableMutation.Field()


schema = graphene.Schema(query=Query, mutation=Mutation)

