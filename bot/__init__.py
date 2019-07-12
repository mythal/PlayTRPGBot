import django
from dotenv import load_dotenv

load_dotenv()
django.setup()

from .const import TOKEN  # noqa
from .bot import run_bot  # noqa


__all__ = ['run_bot']
