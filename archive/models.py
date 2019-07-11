from enum import Enum, auto
from hashlib import sha256

from django.db import models
from django.core.cache import cache
from django.contrib.postgres.fields import JSONField


class LogKind(Enum):
    NORMAL = auto()
    DICE = auto()
    DESC = auto()
    SYSTEM = auto()
    ME = auto()
    ROLL = auto()
    HIDE_DICE = auto()
    VARIABLE = auto()
    DIVIDER = auto()


def choice(enum):
    return [(kind.value, kind.name) for kind in enum]


class Chat(models.Model):
    chat_id = models.BigIntegerField('Chat ID', db_index=True)
    created = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=256)
    parent = models.ForeignKey('Chat', on_delete=models.CASCADE, null=True, default=None, blank=True)
    description = models.TextField(blank=True)
    save_date = models.DateTimeField(null=True)
    recording = models.BooleanField(default=True)
    password = models.CharField(max_length=512, default='')
    default_dice_face = models.IntegerField(default=20)
    gm_mode = models.BooleanField(default=False)
    gm_mode_notice = models.BigIntegerField(null=True, default=None)

    def all_log(self):
        return self.log_set.filter(deleted=False).order_by('created').prefetch_related('reply', 'tag')

    def log_count(self):
        key = 'chat:counter:{}'.format(self.chat_id)
        counter = cache.get(key)
        if not counter:
            counter = self.all_log().count()
            cache.set(key, counter, 60*60)
        return counter

    def validate(self, password):
        if not self.password:
            return True
        else:
            return self.password == sha256(password.encode()).hexdigest()

    def __str__(self):
        return self.title


class Log(models.Model):
    user_id = models.BigIntegerField('User ID')
    message_id = models.BigIntegerField('Message ID', db_index=True)
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, db_index=True)
    user_fullname = models.CharField('User Full Name', max_length=128, blank=True)
    character_name = models.CharField('Character', max_length=128, blank=True)
    source_message_id = models.BigIntegerField('Source Message ID', db_index=True, null=True, default=None)
    temp_character_name = models.CharField(max_length=128, blank=True, default='')
    kind = models.IntegerField(choices=choice(LogKind), default=LogKind.NORMAL.value)
    content = models.TextField(default='', blank=True, null=False)
    entities = JSONField()
    media = models.FileField(upload_to='uploads/%Y/%m/%d/', blank=True)
    gm = models.BooleanField('GM', default=False)
    reply = models.ForeignKey('Log', on_delete=models.SET_NULL, null=True, blank=True, editable=False)
    deleted = models.BooleanField(default=False)
    created = models.DateTimeField()
    modified = models.DateTimeField(auto_now=True)
    tag = models.ManyToManyField('Tag')

    def reply_message_id(self):
        if self.reply:
            return self.reply.message_id
        else:
            return None

    def media_url(self):
        if self.media:
            return self.media.url
        else:
            return ''

    def __str__(self):
        name = self.character_name or self.user_fullname or 'SYSTEM'
        return '{} - {} - {}'.format(self.chat.title, name, self.id)


class Tag(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE)
    name = models.CharField(max_length=128)

    def __str__(self):
        return '{}::{}'.format(self.chat.title, self.name)
