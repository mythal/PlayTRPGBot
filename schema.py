from typing import Optional

import graphene
from graphene import NonNull
from graphene_django import DjangoObjectType
from django.core.cache import cache

from archive import models

Kind = graphene.Enum.from_enum(models.LogKind)


class Tag(DjangoObjectType):
    class Meta:
        model = models.Tag


class Log(DjangoObjectType):
    class Meta:
        model = models.Log
        exclude_fields = ('user_id', 'log_set', 'deleted')

    kind = Kind()
    entities = graphene.String(required=True)


class LogList(graphene.ObjectType):
    records = graphene.List(NonNull(Log), required=True)
    total_page = graphene.Int(required=True)
    tag_name = graphene.String()
    modified = graphene.DateTime()


class Chat(DjangoObjectType):
    page_limit = 256

    class Meta:
        model = models.Chat
        exclude_fields = ('password', 'parent')

    log_list = graphene.Field(LogList, password=graphene.String(), page=graphene.Int(), tag_id=graphene.String())
    is_require_password = graphene.Boolean(required=True)
    counter = graphene.Int(required=True)
    page_counter = graphene.Int(required=True)

    @staticmethod
    def resolve_is_require_password(chat: models.Chat, info):
        return bool(chat.password)

    @staticmethod
    def resolve_page_counter(chat: models.Chat, info):
        return chat.query_log().count() % Chat.page_limit

    @staticmethod
    def resolve_log_list(chat: models.Chat, info, password='', tag_id=None, page=1):
        limit = Chat.page_limit
        offset = (page - 1) * limit
        tag_name = None
        if page < 1 or (chat.password and not chat.validate(password)):
            return None

        cached_log_list_key = 'graphql:chat:{}:log:tag:{}:page:{}'.format(chat.id, tag_id or '_', page)
        cached_log_list: Optional[LogList] = cache.get(cached_log_list_key)
        if cached_log_list:
            if chat.modified == cached_log_list.modified:
                return cached_log_list

        query_set = chat.query_log()
        if tag_id:
            tag: Optional[models.Tag] = models.Tag.objects.filter(id=tag_id, chat=chat).first()
            if tag:
                query_set = tag.log_set.all()
        log_counter = query_set.count()
        log_list = LogList(
            tag_name=tag_name,
            records=query_set[offset:offset+limit].all(),
            total_page=log_counter // Chat.page_limit + 1,
            modified=chat.modified,
        )
        cache.set(cached_log_list_key, log_list, 1 * 60 * 60)
        return log_list

    @staticmethod
    def resolve_counter(chat: models.Chat, info):
        return chat.log_count()


class Query(graphene.ObjectType):
    chats = graphene.List(NonNull(Chat), required=True)
    chat = graphene.Field(Chat, id=graphene.Int(required=True))

    @staticmethod
    def resolve_chats(root, info):
        return models.Chat.objects.filter(parent=None).all()

    @staticmethod
    def resolve_chat(root, info, id):
        return models.Chat.objects.get(id=id)


schema = graphene.Schema(query=Query)

