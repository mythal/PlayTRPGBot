# Generated by Django 2.1.3 on 2019-01-06 05:09

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Chat',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('chat_id', models.BigIntegerField(db_index=True, verbose_name='Chat ID')),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('title', models.CharField(max_length=256)),
                ('description', models.TextField()),
                ('save_date', models.DateTimeField(null=True)),
                ('recording', models.BooleanField(default=True)),
                ('parent', models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to='archive.Chat')),
            ],
        ),
        migrations.CreateModel(
            name='Log',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user_id', models.BigIntegerField(verbose_name='User ID')),
                ('message_id', models.BigIntegerField(verbose_name='Message ID')),
                ('user_fullname', models.CharField(blank=True, max_length=128, verbose_name='User Full Name')),
                ('character_name', models.CharField(blank=True, max_length=128, verbose_name='Character')),
                ('kind', models.IntegerField(choices=[(1, 'NORMAL'), (2, 'DICE'), (3, 'DESC'), (4, 'SYSTEM'), (5, 'ME'), (6, 'ROLL'), (7, 'HIDE_DICE')], default=1)),
                ('content', models.TextField()),
                ('media', models.FileField(blank=True, upload_to='uploads/%Y/%m/%d/')),
                ('gm', models.BooleanField(default=False, verbose_name='GM')),
                ('deleted', models.BooleanField(default=False)),
                ('created', models.DateTimeField()),
                ('modified', models.DateTimeField(auto_now=True)),
                ('chat', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='archive.Chat')),
                ('reply', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='archive.Log')),
            ],
        ),
    ]