import telegram

from telegram.ext import JobQueue

from . import pattern, system
from .display import get, Text
from .system import error_message, delete_message, delay_delete_messages, get_player_by_username, get_player_by_id
from game.models import Player, Variable
from archive.models import Log, LogKind, Chat


def handle_list_variables(message: telegram.Message, job_queue: JobQueue, name: str, player: Player, **_):
    content = ''
    for variable in player.variable_set.order_by('updated').all():
        content += '<code>${}</code> {}\n'.format(variable.name, variable.value)

    send_text = '<b>{}</b> #variable\n\n{}'.format(get(Text.VARIABLE_LIST_TITLE).format(character=name), content)
    list_message = message.chat.send_message(send_text, parse_mode='HTML')
    delete_message(message)
    delete_time = 30
    job_queue.run_once(delay_delete_messages, delete_time, context=dict(
        chat_id=message.chat_id,
        message_id_list=(list_message.message_id,)
    ))


def variable_message(message: telegram.Message, job_queue: JobQueue, chat: Chat, player: Player, is_gm: bool,
                     variable: Variable, old_value=None):
    character = player.character_name
    if old_value is None:
        if not variable.value:
            send_text = get(Text.VARIABLE_ASSIGNED_EMPTY)\
                .format(character=character, variable=variable.name)
        else:
            send_text = get(Text.VARIABLE_ASSIGNED)\
                .format(character=character, variable=variable.name, value=variable.value)
    elif old_value == variable.value:
        send_text = get(Text.VARIABLE_NOT_CHANGE)\
            .format(character=character, variable=variable.name, value=variable.value)
    else:
        send_text = get(Text.VARIABLE_UPDATED)\
            .format(character=character, variable=variable.name, old_value=old_value, value=variable.value)
    if not chat.recording:
        send_text = '[{}] {}'.format(get(Text.NOT_RECORDING), send_text)
    sent = message.chat.send_message(send_text, parse_mode='HTML')
    delete_message(message)
    if chat.recording:
        Log.objects.create(
            message_id=sent.message_id,
            chat=chat,
            user_id=player.user_id,
            user_fullname=player.full_name,
            kind=LogKind.VARIABLE.value,
            character_name=character,
            content=send_text,
            gm=is_gm,
            created=message.date,
        )

    delete_time = 10
    job_queue.run_once(delay_delete_messages, delete_time, context=dict(
        chat_id=message.chat_id,
        message_id_list=(message.message_id,)
    ))


def handle_variable_assign(bot: telegram.Bot, message: telegram.Message, job_queue, start: int,
                           chat: Chat, player: Player, **_):
    is_gm = player.is_gm
    assign_list = []
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
            if player:
                assign_list.append(assign_player)
                start = end

    if not assign_list:
        user_id = message.from_user.id
        # when reply to a message
        if isinstance(message.reply_to_message, telegram.Message) and is_gm:
            reply_to = message.reply_to_message
            user_id = reply_to.from_user.id
            # reply to a bot message
            if user_id == bot.id:
                log = Log.objects.filter(message_id=reply_to.message_id, chat__chat_id=message.chat_id).first()
                if not log:
                    error_message(message, job_queue, get(Text.RECORD_NOT_FOUND))
                    return
                user_id = log.user_id
        if user_id != player.user_id:
            player = get_player_by_id(message.chat_id, user_id)
            if not player:
                return error_message(message, job_queue, get(Text.REPLY_TO_NON_PLAYER_IN_VARIABLE_ASSIGNMENT))
        assign_list.append(player)
    text = message.text[start:].strip()

    # .set $VARIABLE + 42
    matched = pattern.VARIABLE_MODIFY_REGEX.match(text)
    if matched:
        var_name = matched.group(1)
        operator = matched.group(2)
        value = text[matched.end():].strip()
        for assign_player in assign_list:
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
                    return error_message(message, job_queue, get(Text.VARIABLE_ASSIGN_USAGE))
            variable.save()
            return variable_message(message, job_queue, chat, assign_player, is_gm, variable, old_value)

    for match in pattern.VARIABLE_NAME_REGEX.finditer(text):
        var_name = match.group(1).strip()
        value = text[match.end():].strip()
        for assign_player in assign_list:
            variable = Variable.objects.filter(player=assign_player, name__iexact=var_name).first()
            old_value = None
            if not variable:
                variable = Variable.objects.create(player=assign_player, name=var_name, value=value)
            else:
                old_value = variable.value
                variable.value = value
                variable.save()
            return variable_message(message, job_queue, chat, assign_player, is_gm, variable, old_value)
    else:
        error_message(message, job_queue, get(Text.VARIABLE_ASSIGN_USAGE))
