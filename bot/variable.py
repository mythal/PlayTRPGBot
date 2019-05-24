from functools import partial
from typing import List

import telegram

from telegram.ext import JobQueue

from . import pattern
from .display import get, Text, get_by_user
from .system import error_message, delete_message, delay_delete_messages, get_player_by_username, get_player_by_id
from game.models import Player, Variable
from archive.models import Log


def handle_clear_variables(message: telegram.Message, player: Player, job_queue, **_):
    _ = partial(get_by_user, user=message.from_user)
    player.variable_set.all().delete()
    send_text = _(Text.VARIABLE_CLEARED, message.from_user.language_code).format(character=player.character_name)
    sent = message.chat.send_message(send_text, parse_mode='HTML')
    delete_message(message)
    delete_time = 20
    job_queue.run_once(delay_delete_messages, delete_time, context=dict(
        chat_id=message.chat_id,
        message_id_list=(sent.message_id,)
    ))


def handle_list_variables(message: telegram.Message, job_queue: JobQueue, name: str, player: Player, **_):
    _ = partial(get_by_user, user=message.from_user)
    content = ''
    have_variable = False
    for variable in player.variable_set.order_by('updated').all():
        have_variable = True
        content += '<code>${}</code> {}\n'.format(variable.name, variable.value)
    if not have_variable:
        content = _(Text.VARIABLE_LIST_EMPTY)

    send_text = '<b>{}</b> #variable\n\n{}'.format(_(Text.VARIABLE_LIST_TITLE).format(character=name), content)
    list_message = message.chat.send_message(send_text, parse_mode='HTML')
    delete_message(message)
    delete_time = 30
    job_queue.run_once(delay_delete_messages, delete_time, context=dict(
        chat_id=message.chat_id,
        message_id_list=(list_message.message_id,)
    ))


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
                return _(Text.VARIABLE_ASSIGNED_EMPTY.format(**format_dict))
            else:
                return _(Text.VARIABLE_ASSIGNED).format(**format_dict)
        elif self.old_value == self.variable.value:
            return _(Text.VARIABLE_NOT_CHANGE).format(**format_dict)
        else:
            return _(Text.VARIABLE_UPDATED).format(**format_dict)


def variable_message(message: telegram.Message, job_queue: JobQueue,
                     assignment_list: List[Assignment]):
    send_text = ''
    for assignment in assignment_list:
        send_text += assignment.display(message.from_user.language_code) + '\n'
    sent = message.chat.send_message(send_text, parse_mode='HTML')
    user = message.from_user
    assert isinstance(user, telegram.User)

    delete_time = 30
    job_queue.run_once(delay_delete_messages, delete_time, context=dict(
        chat_id=message.chat_id,
        message_id_list=(message.message_id, sent.message_id)
    ))


def value_processing(text: str) -> str:
    text = pattern.VARIABLE_IGNORE_HEAD.sub('', text)
    return text.strip()


def handle_variable_assign(bot: telegram.Bot, message: telegram.Message, job_queue, start: int,
                           player: Player, **_):
    _ = partial(get_by_user, user=message.from_user)
    is_gm = player.is_gm
    assign_player_list = []
    if is_gm:
        for entity in message.entities:
            assert isinstance(entity, telegram.MessageEntity)
            offset = entity.offset
            length = entity.length
            end = offset + length
            assign_player = None
            if entity.type == entity.MENTION:
                assign_player = get_player_by_username(message.chat_id, message.text[offset:end])
            elif entity.type == entity.TEXT_MENTION:
                assign_player = get_player_by_id(message.chat_id, entity.user.id)
            if assign_player:
                assign_player_list.append(assign_player)
                start = end

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
                    error_message(message, job_queue, _(Text.RECORD_NOT_FOUND))
                    return
                user_id = log.user_id
        if user_id != player.user_id:
            player = get_player_by_id(message.chat_id, user_id)
            if not player:
                return error_message(message, job_queue, _(Text.REPLY_TO_NON_PLAYER_IN_VARIABLE_ASSIGNMENT))
        assign_player_list.append(player)
    text = message.text[start:]
    assert isinstance(text, str)
    assignment_list = []
    for line in text.splitlines():
        line = line.strip()
        # .set $VARIABLE + 42
        matched = pattern.VARIABLE_MODIFY_REGEX.match(line)
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
            matched = pattern.VARIABLE_NAME_REGEX.search(line)
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
        return error_message(message, job_queue, _(Text.VARIABLE_ASSIGN_USAGE))
    variable_message(message, job_queue, assignment_list)
