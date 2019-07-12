from functools import partial
from typing import Optional

import telegram

from .system import error_message, send_message, delete_message
from .round_counter import create_player
from .display import Text, get_by_user
from game.models import Player


def set_temp_name(chat_id, user_id, temp_name):
    player = Player.objects.filter(chat_id=chat_id, user_id=user_id).first()
    if player:
        player.temp_character_name = temp_name
        player.save()


def get_temp_name(chat_id, user_id):
    player = Player.objects.filter(chat_id=chat_id, user_id=user_id).first()
    if player:
        return player.temp_character_name or ''


def set_name(bot: telegram.Bot, update: telegram.Update, args):
    message = update.message
    assert isinstance(message, telegram.Message)

    _ = partial(get_by_user, user=message.from_user)
    if len(args) == 0:
        return error_message(message, _(Text.NAME_SYNTAX_ERROR))
    user = message.from_user
    assert isinstance(user, telegram.User)
    name = ' '.join(args).strip()
    player = create_player(bot, message, name)
    if player.is_gm:
        template = _(Text.NAME_SUCCESS_GM)
    else:
        template = _(Text.NAME_SUCCESS)
    send_text = template.format(player=user.full_name, character=name)
    send_message(message.chat_id, send_text)
    delete_message(message.chat_id, message.message_id)


def get_name(message: telegram.Message, temp=False) -> Optional[str]:
    user_id = message.from_user.id
    player = Player.objects.filter(chat_id=message.chat_id, user_id=user_id).first()
    if not player:
        return None
    elif temp:
        return player.temp_character_name
    return player.character_name


def get_name_by_username(chat_id, username):
    player = Player.objects.filter(chat_id=chat_id, username=username).first()
    if not player:
        return None
    return player.character_name
