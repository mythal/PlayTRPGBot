from django.db import models
from django.contrib.postgres.fields import JSONField

class Round(models.Model):
    chat_id = models.BigIntegerField(primary_key=True)
    counter = models.IntegerField(default=0)
    round_counter = models.IntegerField(default=1)
    message_id = models.BigIntegerField()
    hide = models.BooleanField(default=False)

    def get_actors(self):
        actors = Actor.objects.filter(belong=self).order_by('value').reverse().all()
        return list(actors)


class Actor(models.Model):
    name = models.CharField(max_length=128)
    value = models.IntegerField()
    belong = models.ForeignKey(Round, on_delete=models.CASCADE)


class Player(models.Model):
    character_name = models.CharField(max_length=128)
    is_gm = models.BooleanField(default=False)
    temp_character_name = models.CharField(max_length=128, blank=True, default='')
    chat_id = models.BigIntegerField(db_index=True)
    user_id = models.BigIntegerField(db_index=True)
    full_name = models.CharField(max_length=256)
    username = models.CharField(max_length=128, blank=True, default='')
    description = models.CharField(max_length=512, blank=True, default='')

    def __str__(self):
        return '{} ({})'.format(self.character_name, self.full_name)


class Variable(models.Model):
    player = models.ForeignKey(Player, models.CASCADE, null=False, blank=False, db_index=True)
    name = models.CharField(max_length=128, blank=False, null=False)
    value = models.CharField(max_length=128, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    group = models.CharField(max_length=32, default='', blank=True)

    def __str__(self):
        return '{}: [{}]'.format(self.player.character_name, self.name)
