# Generated by Django 2.2.3 on 2019-07-26 03:26

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('archive', '0015_auto_20190726_0121'),
    ]

    operations = [
        migrations.DeleteModel(
            name='TelegramProfile',
        ),
    ]