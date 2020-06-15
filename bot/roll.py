import re
import secrets
from functools import partial

import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackContext, JobQueue

import dice
from entities import RollResult, Span, CocResult, LoopResult, Entities
from archive.models import LogKind, Log, Chat
from .patterns import LOOP_ROLL_REGEX
from .system import RpgMessage, get_chat, HideRoll, \
    is_gm
from bot.tasks import send_message, delete_message, error_message
from .display import Text, get_by_user


def set_dice_face(update, context: CallbackContext):
    message = update.message
    assert isinstance(message, telegram.Message)
    return handle_set_dice_face(message, ' '.join(context.args), context.job_queue)


def handle_set_dice_face(message: telegram.Message, text: str, job_queue, **_kwargs):
    _ = partial(get_by_user, user=message.from_user)
    chat = get_chat(message.chat)
    try:
        face = int(text.strip())
    except ValueError:
        return error_message(job_queue, message, _(Text.SET_DEFAULT_FACE_SYNTAX).format(face=chat.default_dice_face))
    chat.default_dice_face = face
    chat.save()
    delete_message(job_queue, message.chat_id, message.message_id)
    send_message(job_queue, message.chat_id, _(Text.DEFAULT_FACE_SETTLED).format(face))


def handle_coc_roll(message: telegram.Message, command: str, name: str, text: str, chat: Chat, job_queue, **__):
    """
    Call of Cthulhu
    """
    def _(t: Text):
        return get_by_user(t, user=message.from_user)

    def roll() -> int:
        return secrets.randbelow(100) + 1

    hide = command[-1] == 'h'
    text = text.strip()
    numbers = re.findall(r'\d{1,2}', text)

    # have not modifier
    rolled_list = [roll()]
    rolled = rolled_list[0]
    modifier_name = None

    # have not target value
    if len(numbers) == 0:
        handle_roll(job_queue, message, name, Entities([Span(text), RollResult(str(rolled), rolled)]), chat, hide)
        return

    skill_number = int(numbers[0])
    # have modifier
    modifier_matched = re.search('[-+]', command)
    if modifier_matched:
        modifier = modifier_matched.group(0)
        extra = 1
        if len(numbers) > 1:
            extra = int(numbers[0])
            skill_number = int(numbers[1])
        for _i in range(extra):
            rolled_list.append(roll())
        if modifier == '+':
            rolled = min(rolled_list)
            modifier_name = _(Text.COC_BONUS_DIE)
        elif modifier == '-':
            rolled = max(rolled_list)
            modifier_name = _(Text.COC_PENALTY_DIE)

    half_skill_number = skill_number // 2
    skill_number_divide_5 = skill_number // 5

    if rolled == 1:
        level = _(Text.COC_CRITICAL)
    elif rolled <= skill_number_divide_5:
        level = _(Text.COC_EXTREME_SUCCESS)
    elif rolled <= half_skill_number:
        level = _(Text.COC_HARD_SUCCESS)
    elif rolled <= skill_number:
        level = _(Text.COC_REGULAR_SUCCESS)
    elif rolled == 100:
        level = _(Text.COC_FUMBLE)
    elif rolled >= 95 and skill_number < 50:
        level = _(Text.COC_FUMBLE)
    else:
        level = _(Text.COC_FAIL)

    entities = [Span(text), Span(' → '), CocResult(rolled, level, modifier_name, rolled_list)]
    handle_roll(job_queue, message, name, Entities(entities), chat, hide)


def handle_loop_roll(message: telegram.Message, command: str, name: str, text: str, chat: Chat, job_queue, **__):
    """
    Tales from the Loop
    """
    def _(t: Text):
        return get_by_user(t, user=message.from_user)
    hide = command[-1] == 'h'
    text = text.strip()
    roll_match = LOOP_ROLL_REGEX.match(text)

    if not roll_match:
        return error_message(job_queue, message, _(Text.LOOP_SYNTAX_ERROR))
    number = int(roll_match.group(1))
    if number == 0:
        return error_message(job_queue, message, _(Text.LOOP_ZERO_DICE))
    result_list = [secrets.randbelow(6) + 1 for _i in range(number)]
    description = text[roll_match.end():]
    entities = Entities([LoopResult(result_list), Span(description)])
    handle_roll(job_queue, message, name, entities, chat, hide)


def handle_normal_roll(message: telegram.Message, command: str, name: str, start: int, chat: Chat, job_queue, **_):
    rpg_message = RpgMessage(message, start)
    hide = command[-1] == 'h'
    entities = rpg_message.entities.list
    roll_counter = 0
    next_entities = []
    try:
        for entity in entities:
            if isinstance(entity, Span):
                result_entities = dice.roll_entities(entity.value, chat.default_dice_face)
                local_roll_counter = 0
                for result_entity in result_entities:
                    if isinstance(result_entity, RollResult):
                        local_roll_counter += 1
                if local_roll_counter > 0:
                    next_entities.extend(result_entities)
                    roll_counter += local_roll_counter
                else:
                    next_entities.append(entity)
            else:
                next_entities.append(entity)
        if roll_counter == 0:
            default_roll_entities = dice.roll_entities('1d', chat.default_dice_face)
            default_roll_entities.extend(next_entities)
            next_entities = default_roll_entities
    except dice.RollError as e:
        error_text = Text.ERROR
        if len(e.args) > 0:
            error_kind = e.args[0]
            try:
                error_text = Text[error_kind.value]
            except KeyError:
                pass
        return error_message(job_queue, message, get_by_user(error_text, message.from_user))
    handle_roll(job_queue, message, name, Entities(next_entities), chat, hide)


def handle_roll(job_queue: JobQueue, message: telegram.Message, name: str, entities: Entities, chat: Chat, hide=False):
    _ = partial(get_by_user, user=message.from_user)
    kind = LogKind.ROLL.value
    result_text = entities.telegram_html()
    if hide:
        hide_roll = HideRoll(message.chat_id, result_text)
        hide_roll.set()
        keyboard = [[InlineKeyboardButton(_(Text.GM_LOOKUP), callback_data=hide_roll.key())]]

        reply_markup = InlineKeyboardMarkup(keyboard)
        text = '<b>{}</b> {}'.format(name, _(Text.ROLL_HIDE_DICE))
        kind = LogKind.HIDE_DICE.value
    else:
        text = '{} 🎲 {}'.format(name, result_text)
        reply_markup = None
    if not chat.recording:
        text = '[{}] '.format(_(Text.NOT_RECORDING)) + text
    sent = message.chat.send_message(
        text,
        reply_markup=reply_markup,
        parse_mode='HTML'
    )
    user = message.from_user
    assert isinstance(user, telegram.User)
    if chat.recording:
        Log.objects.create(
            user_id=user.id,
            message_id=sent.message_id,
            chat=chat,
            content=result_text,
            entities=entities.to_object(),
            user_fullname=user.full_name,
            character_name=name,
            gm=is_gm(message.chat_id, user.id),
            kind=kind,
            created=message.date,
        )
        chat.save()
    delete_message(job_queue, message.chat_id, message.message_id, 25)


def hide_roll_callback(_, update):
    query = update.callback_query
    assert isinstance(query, telegram.CallbackQuery)
    _ = partial(get_by_user, user=query.from_user)
    gm = is_gm(query.message.chat_id, query.from_user.id)
    key = query.data
    if not gm:
        query.answer(_(Text.ONLY_GM_CAN_LOOKUP), show_alert=True)
        return
    hide_roll = HideRoll.get(key)
    if hide_roll:
        text = hide_roll.text
    else:
        text = _(Text.HIDE_ROLL_NOT_FOUND)
    query.answer(
        show_alert=True,
        text=text,
        cache_time=10000,
    )
