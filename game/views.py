from typing import Optional

from rest_framework import serializers, viewsets, mixins
from rest_framework.exceptions import PermissionDenied

from .models import Variable, Player
from archive.models import TelegramProfile


class PlayerSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Player
        fields = ['id', 'character_name', 'is_gm', 'temp_character_name', 'chat_id', 'user_id']


class VariableSerializer(serializers.HyperlinkedModelSerializer):
    player = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Variable
        fields = ['id', 'name', 'value', 'group', 'player']


class PlayerViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Player.objects.all()
    serializer_class = PlayerSerializer

    def get_queryset(self):
        user = self.request.user
        telegram_profile: Optional[TelegramProfile] = getattr(user, 'telegram', None)
        if not telegram_profile:
            raise PermissionDenied('Before you can view variables, you need to sign in.')
        return Player.objects.filter(user_id=telegram_profile.telegram_id)


class VariableViewSet(viewsets.ModelViewSet):
    queryset = Variable.objects.all()
    serializer_class = VariableSerializer
    filterset_fields = ['player']

    def get_queryset(self):
        user = self.request.user
        telegram_profile: Optional[TelegramProfile] = getattr(user, 'telegram', None)
        if not telegram_profile:
            raise PermissionDenied('Before you can view variables, you need to sign in.')
        players = Player.objects.filter(user_id=telegram_profile.telegram_id)
        return Variable.objects.filter(player__in=players)




