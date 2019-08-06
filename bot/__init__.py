import django
from dotenv import load_dotenv

load_dotenv()
django.setup()

from .bot import run_bot  # noqa


__all__ = ['run_bot']
