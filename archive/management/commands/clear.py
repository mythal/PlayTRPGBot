import os
from django.core.management.base import BaseCommand
from django.core.cache import cache
from django.db import transaction

from archive.models import Chat, Tag, Log
from django.conf import settings


class Command(BaseCommand):
    help = 'Clear application data'

    def handle(self, *args, **options):
        with transaction.atomic():
            Log.objects.filter(deleted=True).delete()
            for tag in Tag.objects.all():
                if tag.log_set.count() == 0:
                    print('delete {}'.format(tag))
                    tag.delete()
            for chat in Chat.objects.all():
                if chat.log_set.count() == 0:
                    print('delete {}'.format(chat))
                    chat.delete()
            media_paths = set()
            for log in Log.objects.exclude(media='').values('media').all():
                path = os.path.join(settings.MEDIA_ROOT, log['media'])
                media_paths.add(path)
        should_remove = []
        for root, _, files in os.walk(settings.MEDIA_ROOT):
            for file in files:
                path = os.path.join(root, file)
                if path in media_paths:
                    continue
                print(path)
                should_remove.append(path)

        if should_remove:
            prompt = input("Remove these files? [Y]")
            if prompt == '' or prompt == 'Y':
                for path in should_remove:
                    os.remove(path)

        cache.clear()
