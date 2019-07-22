import os

BUFFER_TIME = 20
TOKEN = os.environ['BOT_TOKEN']
LOGGER_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
WEBHOOK_PORT = 9990
BOT_WEBHOOK_URL = os.environ.get('BOT_WEBHOOK_URL', None)
