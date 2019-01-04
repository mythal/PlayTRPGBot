import os
import logging
import re
import secrets
import telegram

from dotenv import load_dotenv
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters

load_dotenv()
# Enable logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

DEFAULT_FACE = 100
BUFFER_TIME = 20
TOKEN = os.environ['BOT_TOKEN']

logger = logging.getLogger(__name__)


help_file = open('./help.md')
start_file = open('./start.md')
HELP_TEXT = help_file.read()
START_TEXT = start_file.read()
help_file.close()
start_file.close()


def start(_, update):
    """Send a message when the command /start is issued."""
    update.message.reply_text(START_TEXT, parse_mode='Markdown')


def bot_help(_, update):
    """Send a message when the command /help is issued."""
    update.message.reply_text(HELP_TEXT, parse_mode='Markdown')


def eval_dice(counter, face) -> str:
    if counter > 0x1000:
        return '<code>too much dice</code>'
    elif face > 0x1000:
        return '<code>too much dice face</code>'
    result = [secrets.randbelow(face) + 1 for _ in range(counter)]
    result_repr = '[...]'
    if len(result) < 0x10:
        result_repr = repr(result)
    return '<code>{}={}</code>'.format(result_repr, sum(result))


def set_name(_, update: telegram.Update, args, chat_data: dict):
    message = update.message
    assert isinstance(message, telegram.Message)
    if len(args) == 0:
        message.reply_text('请在 /name 后写下你的角色名')
        return
    user = message.from_user
    assert isinstance(user, telegram.User)
    name = ' '.join(args)
    if 'name' in chat_data:
        chat_data['name'][user.id] = name
    else:
        chat_data['name'] = {user.id: name}
    message.reply_text('{} 已被设为 {}'.format(user.full_name, name))


def echo(bot, update, job_queue, chat_data: dict):
    """Echo the user message."""
    def repl(match):
        counter = match.group(1)
        face = match.group(2)
        if counter == '':
            counter = 1
        if face == '':
            face = chat_data.get('face', DEFAULT_FACE)
        counter = int(counter)
        face = int(face)
        return eval_dice(counter, face)
    message = update.message
    assert isinstance(message, telegram.Message)
    text = message.text
    assert isinstance(text, str)
    message_match = re.match(r'^[\.。](\w*)\s*', text)
    if not message_match:
        return
    command = message_match.group(1)

    if command == 'me':
        command = ''
        rest = text
    else:
        rest = text[message_match.end():]

    name = None
    if 'name' in chat_data:
        name = chat_data['name'].get(message.from_user.id, None)
    if name is None:
        message.reply_text('请先用 /name [角色名] 设置一个角色')
        return
    if command == 'name':
        set_name(bot, update, [rest], chat_data)
    elif command == 'r' or command == 'roll':
        rest = re.sub(r'\b(\d*)d(\d*)\b', repl, rest)
        message.chat.send_message('{} 🎲 {}'.format(name, rest), parse_mode='HTML')
    elif command == '' or command == 'me':
        me_regex = re.compile(r'^[\.。]me|\s[\.。]me\s?')
        if me_regex.search(rest):
            message.chat.send_message(
                me_regex.sub('<b>{}</b>'.format(name), rest),
                parse_mode='HTML'
            )
        else:
            message.chat.send_message('<b>{}</b>: 「{}」'.format(name, rest), parse_mode='HTML')
        job_queue.run_once(
            lambda _bot, _job: message.delete(),
            BUFFER_TIME,
            context=message.chat_id
        )


def error(_, update, bot_error):
    """Log Errors caused by Updates."""
    logger.warning('Update "%s" caused error "%s"', update, bot_error)


def main():
    """Start the bot."""
    # Create the EventHandler and pass it your bot's token.
    updater = Updater(TOKEN)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", bot_help))
    dp.add_handler(CommandHandler('name', set_name, pass_chat_data=True, pass_args=True))

    # on otherwise i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(Filters.text, echo, pass_job_queue=True, pass_chat_data=True))

    # log all errors
    dp.add_error_handler(error)

    # Start the Bot
    updater.start_polling()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()
