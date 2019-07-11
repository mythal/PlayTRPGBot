import django
from dotenv import load_dotenv
from celery import Celery
from telegram import Bot


app = Celery('tasks', broker='redis://redis', backend='redis://redis')

load_dotenv()
django.setup()

from .const import TOKEN  # noqa

bot = Bot(TOKEN)

from .bot import run_bot  # noqa


__all__ = ['run_bot']
