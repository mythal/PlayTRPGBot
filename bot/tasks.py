import io
import uuid
import logging
import base64
from functools import partial

import telegram
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, TelegramError
from telegram.ext import JobQueue, CallbackContext
from django.core.cache import cache

from archive.models import Log
from bot.display import get, Text, get_by_user
from bot.system import bot
from game.models import Round
from play_trpg.celery import app

logger = logging.getLogger(__name__)


def set_photo_task(log_id, file_id):
    log = Log.objects.get(id=log_id)
    log.media.save('{}.jpeg'.format(uuid.uuid4()), io.BytesIO(b''))
    media = log.media.open('rb+')
    bot.get_file(file_id).download(out=media)
    media.close()
    log.save()


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


def send_timer_massage(context: CallbackContext):
    context = context.job.context
    comment = context['comment']
    timer = context['timer']
    chat_id = context['chat_id']
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


def send_message_task(job_queue, chat_id, text, reply_to=None, parse_mode='HTML', delete_after=None):
    try:
        sent = bot.send_message(chat_id, text, parse_mode, disable_web_page_preview=True, reply_to_message_id=reply_to)
    except telegram.error.TelegramError:
        logger.exception('Error on send message')
        return
    if delete_after and delete_after > 0:
        delete_message(job_queue, chat_id, sent.message_id, delete_after)


def edit_message_task(chat_id, message_id, text, parse_mode):
    bot.edit_message_text(text, chat_id, message_id, parse_mode=parse_mode)


def answer_callback_query_task(query_id, text, show_alert, cache_time):
    bot.answer_callback_query(query_id, text, show_alert, cache_time=cache_time)


def edit_message_photo_task(chat_id, message_id, media_id):
    media = telegram.InputMediaPhoto(media_id)
    bot.edit_message_media(chat_id, message_id, media=media)


def edit_message_caption_task(chat_id, message_id, text, parse_mode):
    bot.edit_message_caption(chat_id, message_id, caption=text, parse_mode=parse_mode)


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


def answer_callback_query(job_queue: JobQueue, query_id, text=None, show_alert=False, cache_time=0):
    job_queue.run_once(lambda _: answer_callback_query_task(query_id, text, show_alert, cache_time), 0)


def edit_message(job_queue: JobQueue, chat_id, message_id, text, parse_mode='HTML'):
    job_queue.run_once(lambda _: edit_message_task(chat_id, message_id, text, parse_mode), 0)


def edit_message_photo(job_queue: JobQueue, chat_id, message_id, media_id):
    job_queue.run_once(lambda _: edit_message_photo_task(chat_id, message_id, media_id), 0)


def edit_message_caption(job_queue: JobQueue, chat_id, message_id, text, parse_mode='HTML'):
    job_queue.run_once(lambda _: edit_message_caption_task(chat_id, message_id, text, parse_mode), 0)


def send_message(job_queue: JobQueue, chat_id, text, reply_to=None, parse_mode='HTML', delete_after=None):
    job_queue.run_once(
        lambda context: send_message_task(context.job_queue, chat_id, text, reply_to, parse_mode, delete_after),
        0
    )


def deletion_task_key(chat_id, message_id):
    return 'deletion:{}:{}'.format(chat_id, message_id)


def delete_message(job_queue: JobQueue, chat_id, message_id, when=0):
    key = deletion_task_key(chat_id, message_id)
    delete_tasks = job_queue.get_jobs_by_name(key)
    for task in delete_tasks:
        # Deletion will be postponed
        task.schedule_removal()
    job_queue.run_once(lambda _: delete_message_task(chat_id, message_id), when, name=key)


def timer_message(job_queue: JobQueue, chat_id, timer, comment):
    job_queue.run_once(send_timer_massage, timer, dict(
        timer=timer,
        chat_id=chat_id,
        comment=comment,
    ))


def cancel_delete_message(chat_id, message_id):
    key = deletion_task_key(chat_id, message_id)
    task_id = cache.get(key)
    if not task_id:
        return
    app.control.revoke(task_id)
    cache.delete(key)


def after_edit_delete_previous_message(job_queue: JobQueue, log_id):
    job_queue.run_once(lambda _: after_edit_delete_previous_message_task(log_id), 0)


def error_message(job_queue: JobQueue, message: telegram.Message, text: str):
    _ = partial(get_by_user, user=message.from_user)
    send_text = '<b>[{}]</b> {}'.format(_(Text.ERROR), text)
    send_message(job_queue, message.chat_id, send_text, reply_to=message.message_id, delete_after=20)
    delete_message(job_queue, message.chat_id, message.message_id, 20)


def set_photo(job_queue: JobQueue, log_id, file_id):
    job_queue.run_once(lambda _: set_photo_task(log_id, file_id), 0)
