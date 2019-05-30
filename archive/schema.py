import datetime
import graphene

from graphene import NonNull
from graphene_django import DjangoObjectType

from . import models

Kind = graphene.Enum.from_enum(models.LogKind)


class Log(DjangoObjectType):
    class Meta:
        model = models.Log
        exclude_fields = ('user_id', 'log_set', 'deleted')
    kind = Kind()


class Chat(DjangoObjectType):
    class Meta:
        model = models.Chat
        exclude_fields = ('password', 'log_set')
    logs = graphene.List(
        Log,
        password=graphene.String(),
        start_date=graphene.DateTime(),
        end_date=graphene.DateTime(),
        count=graphene.Int(),
    )
    has_password = NonNull(graphene.Boolean)
    counter = NonNull(graphene.Int)

    @staticmethod
    def resolve_has_password(chat: models.Chat, info):
        return bool(chat.password)

    @staticmethod
    def resolve_logs(chat: models.Chat, info, password='', start_time=None, end_time=None, count=256):
        if not chat.password or (chat.password and chat.validate(password)):
            query_set = chat.all_log()
            if start_time:
                query_set = query_set.filter(created__lte=start_time)
            if end_time:
                query_set = query_set.filter(created__gte=end_time)
            if count:
                query_set = query_set[:count]
            return query_set
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

