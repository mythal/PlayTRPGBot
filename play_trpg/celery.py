import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'play_trpg.settings')


app = Celery('play_trpg')

app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
