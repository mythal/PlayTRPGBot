from functools import partial
from typing import Optional

import telegram
from django.db import transaction
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, TelegramError

from .system import NotGm, is_group_chat, error_message, is_gm, delete_message
from .pattern import INITIATIVE_REGEX
from game.models import Round, Player, Actor
from .display import Text, get_by_user


def round_inline_handle(bot: telegram.Bot, query: telegram.CallbackQuery, gm: bool, game_round: Round):
    _ = partial(get_by_user, user=query.from_user)

    method = str(query.data)
    actors = game_round.get_actors()
    if method == 'round:next':
        next_count = game_round.counter + 1
        if next_count >= len(actors):
            next_count = 0
            game_round.round_counter += 1
        game_round.counter = next_count
        game_round.save()
        query.answer()
        refresh_round_message(bot, game_round, _)
    elif method == 'round:prev':
        prev_count = game_round.counter - 1
        if prev_count < 0:
            if game_round.round_counter <= 1:
                query.answer(text=_(Text.ALREADY_FIRST_TURN))
                return
            else:
                prev_count = len(actors) - 1
                game_round.round_counter -= 1
        game_round.counter = prev_count
        query.answer()
        refresh_round_message(bot, game_round, _, refresh=True)
        game_round.save()
    elif method == 'round:remove':
        if not gm:
            raise NotGm()

        actors = game_round.get_actors()
        if len(actors) > 1:
            current = actors[game_round.counter % len(actors)]
            current.delete()
            query.answer()
            refresh_round_message(bot, game_round, _, refresh=True)
        else:
            query.answer(show_alert=True, text=_(Text.AT_LEAST_ONE_ACTOR))
    elif method == 'round:finish':
        if not gm:
            raise NotGm()
        query.edit_message_text(_(Text.ROUND_ALREADY_FINISHED))
        remove_round(bot, game_round.chat_id)


def round_inline_callback(bot: telegram.Bot, query: telegram.CallbackQuery, gm: bool):
    game_round = Round.objects.filter(chat_id=query.message.chat_id).first()

    def _(t: Text):
        get_by_user(t, query.from_user)
    if not isinstance(game_round, Round):
        query.answer(show_alert=True, text=_(Text.GAME_NOT_IN_ROUND))
        return
    try:
        with transaction.atomic():
            round_inline_handle(bot, query, gm, game_round)
    except NotGm:
        query.answer(show_alert=True, text=_(Text.NOT_GM), cache_time=0)


def remove_round(bot: telegram.Bot, chat_id):
    for game_round in Round.objects.filter(chat_id=chat_id).all():
        message_id = game_round.message_id
        game_round.delete()
        try:
            bot.delete_message(chat_id, message_id)
        except TelegramError:
            continue


def refresh_round_message(bot: telegram.Bot, game_round: Round, get_text, refresh=False):
    reply_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(get_text(Text.ROUND_REMOVE), callback_data='round:remove'),
            InlineKeyboardButton(get_text(Text.ROUND_FINISH), callback_data='round:finish'),
            InlineKeyboardButton("←", callback_data='round:prev'),
            InlineKeyboardButton("→", callback_data='round:next'),
        ],
    ])

    actors = game_round.get_actors()
    if not actors:
        return
    game_round.counter = game_round.counter % len(actors)
    counter = game_round.counter
    state = ''
    if game_round.hide:
        state = '[{}]'.format(get_text(Text.HIDED_ROUND_LIST))
    round_counter = get_text(Text.ROUND_COUNTER).format(round_number=game_round.round_counter)
    text = '<b>{}</b> {state} #round\n\n{round_number}   [{counter}/{total}]\n\n'.format(
        get_text(Text.ROUND_INDICATOR),
        state=state,
        round_number=round_counter,
        counter=counter + 1,
        total=len(actors),
    )
    for index, actor in enumerate(actors):
        is_current = counter == index
        if is_current:
            text += '• {} ({}) ← {}\n'.format(actor.name, actor.value, get_text(Text.CURRENT))
        elif not game_round.hide:
            text += '◦ {} ({})\n'.format(actor.name, actor.value)

    if refresh:
        try:
            bot.edit_message_text(
                text,
                chat_id=game_round.chat_id,
                message_id=game_round.message_id,
                parse_mode='HTML',
                reply_markup=reply_markup,
            )
        except TelegramError:
            pass
    else:
        bot.delete_message(game_round.chat_id, game_round.message_id)
        message = bot.send_message(game_round.chat_id, text, parse_mode='HTML', reply_markup=reply_markup)
        game_round.message_id = message.message_id
        game_round.save()


def start_round(bot: telegram.Bot, update: telegram.Update, job_queue):
    message = update.message
    assert isinstance(message, telegram.Message)
    _ = partial(get_by_user, user=message.from_user)
    if not is_group_chat(message.chat):
        return error_message(message, job_queue, _(Text.NOT_GROUP))
    chat = message.chat
    text = '{} #round\n\n\n{}'.format(_(Text.ROUND_INDICATOR), _(Text.ROUND_INDICATOR_INIT))
    message = chat.send_message(text, parse_mode='HTML')
    message_id = message.message_id
    chat_id = message.chat_id
    remove_round(bot, chat_id)
    Round.objects.create(chat_id=chat_id, message_id=message_id, hide=False)


def get_round(update: telegram.Update, job_queue) -> Optional[Round]:
    message = update.message
    assert isinstance(message, telegram.Message)
    _ = partial(get_by_user, user=message.from_user)

    if not is_group_chat(message.chat):
        return error_message(message, job_queue, _(Text.NOT_GROUP))
    game_round = Round.objects.filter(chat_id=message.chat_id).first()
    if not game_round:
        return error_message(message, job_queue, _(Text.GAME_NOT_IN_ROUND))
    return game_round


def hide_round(bot: telegram.Bot, update: telegram.Update, job_queue):
    game_round = get_round(update, job_queue)
    message = update.message
    assert isinstance(message, telegram.Message)
    _ = partial(get_by_user, user=message.from_user)

    if not game_round:
        return
    if not is_gm(message.chat_id, message.from_user.id):
        return error_message(message, job_queue, _(Text.NOT_GM))
    game_round.hide = True
    game_round.save()
    refresh_round_message(bot, game_round, _, refresh=True)
    bot.delete_message(message.chat_id, message.message_id)


def public_round(bot: telegram.Bot, update: telegram.Update, job_queue):
    game_round = get_round(update, job_queue)
    _ = partial(get_by_user, user=update.message.from_user)
    if not game_round:
        return
    if not is_gm(update.message.chat_id, update.message.from_user.id):
        error_text = get_by_user(Text.NOT_GM, update.message.from_user)
        return error_message(update.message, job_queue, error_text)
    game_round.hide = False
    game_round.save()
    refresh_round_message(bot, game_round, _, refresh=True)
    bot.delete_message(update.message.chat_id, update.message.message_id)


def next_turn(bot: telegram.Bot, update: telegram.Update, job_queue):
    game_round = get_round(update, job_queue)
    if not game_round:
        return
    actors = game_round.get_actors()
    next_count = game_round.counter + 1
    if next_count >= len(actors):
        next_count = 0
        game_round.round_counter += 1
    game_round.counter = next_count
    game_round.save()
    get_text = partial(get_by_user, user=update.message.from_user)
    refresh_round_message(bot, game_round, get_text, refresh=False)
    bot.delete_message(update.message.chat_id, update.message.message_id)


def create_player(bot: telegram.Bot, message: telegram.Message, character_name: str) -> Player:
    assert isinstance(message.from_user, telegram.User)
    administrators = bot.get_chat_administrators(message.chat_id, timeout=250)
    is_admin = False
    for admin in administrators:
        if message.from_user.id == admin.user.id:
            is_admin = True
            break
    defaults = dict(
        character_name=character_name,
        full_name=message.from_user.full_name,
        username=message.from_user.username or '',
        is_gm=is_admin,
    )
    player, created = Player.objects.update_or_create(
        defaults=defaults,
        chat_id=message.chat_id,
        user_id=message.from_user.id,
    )
    return player


def handle_initiative(message: telegram.Message, job_queue, name: str, text: str, **_):
    _ = partial(get_by_user, user=message.from_user)

    text = text.strip()
    match = INITIATIVE_REGEX.match(text)
    number = text
    if match is not None:
        name = match.group(1).strip()
        number = match.group(2)
    elif not text.isnumeric() or len(text) > 4:
        usage = _(Text.INIT_USAGE)
        error_message(message, job_queue, usage)
        return

    game_round = Round.objects.filter(chat_id=message.chat_id).first()
    if not isinstance(game_round, Round):
        error_message(message, job_queue, _(Text.INIT_WITHOUT_ROUND))
    Actor.objects.create(belong_id=message.chat_id, name=name, value=int(number))
    refresh_round_message(message.bot, game_round, _, refresh=True)
    delete_message(message)
