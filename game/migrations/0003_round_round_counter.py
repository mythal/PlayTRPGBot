# Generated by Django 2.2.1 on 2019-05-07 00:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('game', '0002_auto_20190222_1555'),
    ]

    operations = [
        migrations.AddField(
            model_name='round',
            name='round_counter',
            field=models.IntegerField(default=1),
        ),
    ]
