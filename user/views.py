import hashlib
import hmac
import time

from django.conf import settings
from django.contrib.auth import logout, login
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.shortcuts import redirect
from rest_framework import serializers

from .models import TelegramProfile


def telegram_login(request):
    telegram_id = request.GET['id']
    first_name = request.GET['first_name']
    last_name = request.GET.get('last_name', "")
    username = request.GET.get('username', None)
    photo_url = request.GET.get('photo_url', None)
    auth_date = int(request.GET['auth_date'])
    inputted_hash = request.GET['hash']
    check_keys = list(request.GET.keys())
    check_keys.remove('hash')
    check_keys.sort()
    data_check_string = '\n'.join(['{}={}'.format(name, request.GET[name]) for name in check_keys])
    secret_key = hashlib.sha256(settings.BOT_TOKEN.encode()).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if computed_hash != inputted_hash:
        return HttpResponse('Login Fail: Wrong Data', status=401)
    elif time.time() - auth_date > 60 and not settings.DEBUG:
        return HttpResponse('Login Fail: Timeout', status=401)
    profile = TelegramProfile.objects.filter(telegram_id=telegram_id).first()
    if not profile:
        user = User.objects.create_user('telegram-{}'.format(telegram_id))
        profile = TelegramProfile(
            user=user,
            telegram_id=int(telegram_id),
            photo_url=photo_url,
            username=username,
            first_name=first_name,
            last_name=last_name,
        )
        profile.save()
    else:
        user = profile.user
    logout(request)
    login(request, user)
    return redirect('index')


def logout_page(request):
    logout(request)
    return redirect('index')
