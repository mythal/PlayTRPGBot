import datetime
import io
import uuid
import logging
import base64
from functools import partial

import telegram
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, TelegramError
from django.core.cache import cache

from archive.models import Log
from bot.display import get, Text, get_by_user
from bot.system import bot
from game.models import Round
from play_trpg.celery import app


logger = logging.getLogger(__name__)


@app.task
def set_photo_task(log_id, file_id):
    log = Log.objects.get(id=log_id)
    log.media.save('{}.jpeg'.format(uuid.uuid4()), io.BytesIO(b''))
    media = log.media.open('rb+')
    bot.get_file(file_id).download(out=media)
    media.close()
    log.save()


@app.task
def after_edit_delete_previous_message_task(log_id):
    edit_log = Log.objects.get(id=log_id)
    if not isinstance(edit_log, Log):
        return
    bot.delete_message(edit_log.chat.chat_id, message_id=edit_log.message_id)
    edit_log.delete()


@app.task
def delete_message_task(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
    except telegram.error.BadRequest:
        pass
    cache.delete(deletion_task_key(chat_id, message_id))


@app.task
def send_timer_massage(chat_id, timer, comment: str):
    encoded_comment = base64.b64encode(comment.encode())
    reply_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⟳", callback_data='timer:new:{}:{}'.format(timer, encoded_comment.decode())),
        ]
    ])
    text = '{}秒倒计时结束'.format(timer)
    if len(comment) > 0:
        text += ': {}'.format(comment)
    try:
        bot.send_message(chat_id, text, reply_markup=reply_markup)
    except telegram.error.BadRequest:
        pass


@app.task
def send_message_task(chat_id, text, reply_to=None, parse_mode='HTML', delete_after=None):
    try:
        sent = bot.send_message(chat_id, text, parse_mode, disable_web_page_preview=True, reply_to_message_id=reply_to)
    except telegram.error.TelegramError:
        logger.exception('Error on send message')
        return
    if delete_after and delete_after > 0:
        delete_message(chat_id, sent.message_id, delete_after)


@app.task
def edit_message_task(chat_id, message_id, text, parse_mode):
    bot.edit_message_text(text, chat_id, message_id, parse_mode=parse_mode)


@app.task
def answer_callback_query_task(query_id, text, show_alert, cache_time):
    bot.answer_callback_query(query_id, text, show_alert, cache_time=cache_time)


@app.task
def edit_message_photo_task(chat_id, message_id, media_id):
    media = telegram.InputMediaPhoto(media_id)
    bot.edit_message_media(chat_id, message_id, media=media)


@app.task
def edit_message_caption_task(chat_id, message_id, text, parse_mode):
    bot.edit_message_caption(chat_id, message_id, caption=text, parse_mode=parse_mode)


@app.task
def update_round_message_task(chat_id, language_code, refresh):
    def get_text(t):
        return get(t, language_code)

    game_round = Round.objects.get(chat_id=chat_id)
    reply_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(get_text(Text.ROUND_REMOVE), callback_data='round:remove'),
            InlineKeyboardButton(get_text(Text.ROUND_FINISH), callback_data='round:finish'),
            InlineKeyboardButton("←", callback_data='round:prev'),
            InlineKeyboardButton("/next", callback_data='round:next'),
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


def answer_callback_query(query_id, text=None, show_alert=False, cache_time=0):
    answer_callback_query_task.delay(query_id, text, show_alert, cache_time)


def edit_message(chat_id, message_id, text, parse_mode='HTML'):
    edit_message_task.delay(chat_id, message_id, text, parse_mode)


def edit_message_photo(chat_id, message_id, media_id):
    edit_message_photo_task.delay(chat_id, message_id, media_id)


def edit_message_caption(chat_id, message_id, text, parse_mode='HTML'):
    edit_message_caption_task.delay(chat_id, message_id, text, parse_mode)


def send_message(chat_id, text, reply_to=None, parse_mode='HTML', delete_after=None):
    send_message_task.delay(chat_id, text, reply_to, parse_mode, delete_after)


def deletion_task_key(chat_id, message_id):
    return 'deletion:{}:{}'.format(chat_id, message_id)


def delete_message(chat_id, message_id, when=0):
    key = deletion_task_key(chat_id, message_id)
    task_id = cache.get(key)
    if task_id:
        app.control.revoke(task_id)
    if when > 0:
        task = delete_message_task.apply_async((chat_id, message_id), countdown=when)
        cache.set(key, task.id)
    else:
        delete_message_task.delay(chat_id, message_id)


def timer_message(chat_id, timer, comment):
    send_date = datetime.datetime.utcnow() + datetime.timedelta(seconds=timer)
    send_timer_massage.apply_async((chat_id, timer, comment), eta=send_date)


def cancel_delete_message(chat_id, message_id):
    key = deletion_task_key(chat_id, message_id)
    task_id = cache.get(key)
    if not task_id:
        return
    app.control.revoke(task_id)
    cache.delete(key)


def after_edit_delete_previous_message(log_id):
    after_edit_delete_previous_message_task.delay(log_id)


def error_message(message: telegram.Message, text: str):
    _ = partial(get_by_user, user=message.from_user)
    send_text = '<b>[{}]</b> {}'.format(_(Text.ERROR), text)
    send_message(message.chat_id, send_text, reply_to=message.message_id, delete_after=20)
    delete_message(message.chat_id, message.message_id, 20)
