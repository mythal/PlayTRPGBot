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
    logs = graphene.List(Log, password=graphene.String(), start_date=graphene.DateTime(), end_date=graphene.DateTime())
    has_password = NonNull(graphene.Boolean)
    counter = NonNull(graphene.Int)

    @staticmethod
    def resolve_has_password(chat: models.Chat, info):
        return bool(chat.password)

    @staticmethod
    def resolve_logs(chat: models.Chat, info, password='', start_time=None, end_time=None):
        start_time = start_time or datetime.datetime.now()
        end_time = end_time or datetime.datetime.min
        if not chat.password or (chat.password and chat.validate(password)):
            return chat.all_log().filter(created__gte=end_time, created__lte=start_time).all()
        else:
            return []

    @staticmethod
    def resolve_counter(chat: models.Chat, info):
        return chat.log_count()


class Query(graphene.ObjectType):
    chats = graphene.List(Chat)

    @staticmethod
    def resolve_chats(root, info):
        return models.Chat.objects.filter(parent=None).all()


schema = graphene.Schema(query=Query)

