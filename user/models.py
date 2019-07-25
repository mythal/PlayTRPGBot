from django.db import models


class TelegramProfile(models.Model):
    user = models.OneToOneField('auth.User', primary_key=True, on_delete=models.CASCADE, related_name='telegram')
    telegram_id = models.BigIntegerField('Telegram User ID', db_index=True)
    photo_url = models.URLField('Photo URL', null=True)
    username = models.CharField(max_length=128, null=True)
    first_name = models.CharField(max_length=32)
    last_name = models.CharField(max_length=32)

