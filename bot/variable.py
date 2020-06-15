from functools import partial
from typing import List

import telegram

from . import patterns
from .display import get, Text, get_by_user
from .system import get_player_by_username,\
    get_player_by_id
from bot.tasks import send_message, delete_message, error_message
from game.models import Player, Variable
from archive.models import Log


def handle_clear_variables(message: telegram.Message, player: Player, job_queue, **_):
    _ = partial(get_by_user, user=message.from_user)
    player.variable_set.all().delete()
    send_text = _(Text.VARIABLE_CLEARED).format(character=player.character_name)
    send_message(job_queue, message.chat_id, send_text, delete_after=20)
    delete_message(job_queue, message.chat_id, message.message_id)


def handle_list_variables(message: telegram.Message, name: str, player: Player, job_queue, **_):
    _ = partial(get_by_user, user=message.from_user)
    content = ''
    have_variable = False
    for variable in player.variable_set.order_by('updated').all():
        have_variable = True
        content += '<code>${}</code> {}\n'.format(variable.name, variable.value)
    if not have_variable:
        content = _(Text.VARIABLE_LIST_EMPTY)

    send_text = '<b>{}</b>\n\n{}'.format(_(Text.VARIABLE_LIST_TITLE).format(character=name), content)
    send_message(job_queue, message.chat_id, send_text, delete_after=30)
    delete_message(job_queue, message.chat_id, message.message_id)


class IgnoreLine:
    def __init__(self, text):
        self.text = text


class Assignment:
    def __init__(self, player: Player, variable: Variable, old_value: str = None):
        self.player = player
        self.variable = variable
        self.old_value = old_value

    def display(self, language_code: str):
        _ = partial(get, language_code=language_code)
        character = self.player.character_name
        format_dict = dict(
            character=character,
            variable=self.variable.name,
            old_value=self.old_value,
            value=self.variable.value
        )
        if self.old_value is None:
            if not self.variable.value:
                return _(Text.VARIABLE_ASSIGNED_EMPTY).format(**format_dict)
            else:
                return _(Text.VARIABLE_ASSIGNED).format(**format_dict)
        elif self.old_value == self.variable.value:
            return _(Text.VARIABLE_NOT_CHANGE).format(**format_dict)
        else:
            return _(Text.VARIABLE_UPDATED).format(**format_dict)


def variable_message(job_queue, message: telegram.Message, assignment_list: List[Assignment]):
    send_text = ''
    for assignment in assignment_list:
        send_text += assignment.display(message.from_user.language_code) + '\n'
    send_message(job_queue, message.chat_id, send_text, delete_after=40)
    delete_message(job_queue, message.chat_id, message.message_id, 25)


def value_processing(text: str) -> str:
    text = patterns.VARIABLE_IGNORE_HEAD.sub('', text)
    return text.strip()


def handle_variable_assign(bot: telegram.Bot, message: telegram.Message, start: int,
                           player: Player, job_queue, **_):
    _ = partial(get_by_user, user=message.from_user)
    is_gm = player.is_gm
    assign_player_list = []
    text = message.caption or message.text
    if is_gm:
        for entity in message.entities:
            assert isinstance(entity, telegram.MessageEntity)
            offset = entity.offset
            length = entity.length
            end = offset + length
            assign_player = None
            if entity.type == entity.MENTION:
                assign_player = get_player_by_username(message.chat_id, text[offset:end])
            elif entity.type == entity.TEXT_MENTION:
                assign_player = get_player_by_id(message.chat_id, entity.user.id)
            if assign_player:
                assign_player_list.append(assign_player)
                start = end
            else:
                error_text = '{}\n\n{}'.format(_(Text.VARIABLE_ASSIGN_USAGE), _(Text.VARIABLE_ASSIGN_GM_USAGE))
                error_message(job_queue, message, error_text)
                return

    if not assign_player_list:
        user_id = message.from_user.id
        # when reply to a message
        if isinstance(message.reply_to_message, telegram.Message) and is_gm:
            reply_to = message.reply_to_message
            user_id = reply_to.from_user.id
            # reply to a bot message
            if user_id == bot.id:
                log = Log.objects.filter(message_id=reply_to.message_id, chat__chat_id=message.chat_id).first()
                if not log:
                    error_message(job_queue, message, _(Text.RECORD_NOT_FOUND))
                    return
                user_id = log.user_id
        if user_id != player.user_id:
            player = get_player_by_id(message.chat_id, user_id)
            if not player:
                return error_message(job_queue, message, _(Text.REPLY_TO_NON_PLAYER_IN_VARIABLE_ASSIGNMENT))
        assign_player_list.append(player)
    text = text[start:]
    assert isinstance(text, str)
    assignment_list = []
    for line in text.splitlines():
        line = line.strip()
        # .set $VARIABLE + 42
        matched = patterns.VARIABLE_MODIFY_REGEX.match(line)
        if matched:
            var_name = matched.group(1)
            operator = matched.group(2)
            value = value_processing(line[matched.end():])
            for assign_player in assign_player_list:
                variable = Variable.objects.filter(player=assign_player, name__iexact=var_name).first()
                if not variable:
                    variable = Variable.objects.create(player=assign_player, name=var_name, value=value)
                    old_value = None
                else:
                    old_value = variable.value
                    if old_value.isdigit() and value.isdigit() and len(old_value) < 6 and len(value) < 6:
                        if operator == '+':
                            variable.value = str(int(old_value) + int(value))
                        elif operator == '-':
                            variable.value = str(int(old_value) - int(value))
                    elif operator == '+':
                        variable.value = old_value + ', ' + value
                    else:
                        continue
                variable.save()
                assignment_list.append(Assignment(assign_player, variable, old_value))
        else:
            matched = patterns.VARIABLE_NAME_REGEX.search(line)
            if not matched:
                continue
            var_name = matched.group(1).strip()
            value = value_processing(line[matched.end():])
            for assign_player in assign_player_list:
                variable = Variable.objects.filter(player=assign_player, name__iexact=var_name).first()
                old_value = None
                if not variable:
                    variable = Variable.objects.create(player=assign_player, name=var_name, value=value)
                else:
                    old_value = variable.value
                    variable.value = value
                    variable.save()
                assignment_list.append(Assignment(assign_player, variable, old_value))

    if len(assignment_list) == 0:
        return error_message(job_queue, message, _(Text.VARIABLE_ASSIGN_USAGE))
    variable_message(job_queue, message, assignment_list)
