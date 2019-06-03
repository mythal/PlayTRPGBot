from typing import Optional

import graphene

from graphene import NonNull
from graphene_django import DjangoObjectType
from graphene.types.generic import GenericScalar

from . import models

Kind = graphene.Enum.from_enum(models.LogKind)


class Tag(DjangoObjectType):
    class Meta:
        model = models.Tag


class Log(DjangoObjectType):
    class Meta:
        model = models.Log
        exclude_fields = ('user_id', 'log_set', 'deleted')

    kind = Kind()
    entities = GenericScalar()


class LogList(graphene.ObjectType):
    log_list = graphene.List(Log)
    total_page = graphene.Int()
    tag_name = graphene.String()


class Chat(DjangoObjectType):
    page_limit = 256

    class Meta:
        model = models.Chat
        exclude_fields = ('password',)

    log_list = graphene.Field(LogList, password=graphene.String(), page=graphene.Int(), tag_id=graphene.String())
    has_password = NonNull(graphene.Boolean)
    counter = NonNull(graphene.Int)
    page_counter = NonNull(graphene.Int)

    @staticmethod
    def resolve_has_password(chat: models.Chat, info):
        return bool(chat.password)

    @staticmethod
    def resolve_page_counter(chat: models.Chat, info):
        return chat.all_log().count() % Chat.page_limit

    @staticmethod
    def resolve_log_list(chat: models.Chat, info, password='', tag_id=None, page=1):
        if page < 1:
            page = 1
        limit = Chat.page_limit
        offset = (page - 1) * Chat.page_limit
        tag_name = None
        if not chat.password or (chat.password and chat.validate(password)):
            query_set = chat.all_log()
            if tag_id:
                tag: Optional[models.Tag] = models.Tag.objects.filter(id=int(tag_id), chat=chat).first()
                if tag:
                    query_set = tag.log_set.all()
            query_set = query_set.select_related('reply').prefetch_related('tag')
            log_counter = query_set.count()
            log_list = LogList(
                tag_name=tag_name,
                log_list=query_set[offset:offset+limit].all(),
                total_page=log_counter // Chat.page_limit + 1
            )
            return log_list
        else:
            return None

    @staticmethod
    def resolve_counter(chat: models.Chat, info):
        return chat.log_count()


class Query(graphene.ObjectType):
    chats = graphene.List(Chat)
    chat = graphene.Field(Chat, id=graphene.Int())

    @staticmethod
    def resolve_chats(root, info):
        return models.Chat.objects.filter(parent=None).all()

    @staticmethod
    def resolve_chat(root, info, id):
        return models.Chat.objects.get(id=id)


schema = graphene.Schema(query=Query)

