from typing import Optional
import datetime

from django.http import HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.cache import cache_page
from django.core.paginator import Paginator
from rest_framework import serializers, viewsets, mixins

from . import forms
from .export import EXPORT_METHOD
from .models import Chat, Tag
from user.models import TelegramProfile
from game.models import Player


CACHE_TTL = 3 * 24 * 60 * 60


def index(request):
    return render(request, 'index.html', dict(
        chats=Chat.objects.filter().order_by('-modified'),
        TTL=CACHE_TTL,
        profile=getattr(request.user, 'telegram', None),
    ))


session_key = lambda chat_id: 'chat:{}:allow'.format(chat_id)


def is_allow(session, chat_id):
    return session_key(chat_id) in session


def allow(session, chat_id):
    session[session_key(chat_id)] = True


def chat_page(request, chat_id):

    chat: Chat = get_object_or_404(Chat, id=chat_id)
    tag_list = chat.query_tag()
    tag_id = request.GET.get('tag', None)
    reverse = request.GET.get('reverse', '0') != '0'
    search: Optional[str] = request.GET.get('search', None)
    page_number = int(request.GET.get('page', 1))
    tag: Optional[Tag] = None

    player = None
    telegram_profile: Optional[TelegramProfile] = getattr(request.user, 'telegram', None)
    if telegram_profile:
        player = Player.objects.filter(user_id=telegram_profile.telegram_id, chat_id=chat.chat_id).first()

    if tag_id:
        tag = get_object_or_404(Tag, id=tag_id, chat_id=chat_id)

    if chat.password and not is_allow(request.session, chat_id) and not player:
        return redirect('require_password', chat_id=chat_id)

    log_set = chat.query_log(reverse=reverse)
    if tag:
        log_set = tag.query_log(reverse=reverse)
    if search:
        for keyword in search.split():
            log_set = log_set.filter(content__icontains=keyword)
    paginator = Paginator(log_set, per_page=150)
    page = paginator.page(page_number)
    context = dict(
        chat=chat,
        page_number=page_number,
        log_list=page,
        tag_list=tag_list,
        reverse=reverse,
        tag=tag,
        search=search,
        form=forms.Search(),
        TTL=CACHE_TTL,
        player=player,
    )
    return render(request, 'chat.html', context)


def require_password(request, chat_id):
    current = get_object_or_404(Chat, id=chat_id)
    wrong = False
    if request.method == 'POST':
        form = forms.Password(request.POST)
        if form.is_valid() and current.validate(form.cleaned_data['password']):
            allow(request.session, chat_id)
            return redirect(chat_page, chat_id=chat_id)
        wrong = True
    else:
        form = forms.Password()
    context = dict(chat=current, form=form, wrong=wrong, TTL=CACHE_TTL)
    return render(request, 'require-password.html', context, status=401)


@cache_page(60)
def export(request, chat_id, _title: str, method: str):
    now = datetime.datetime.now()
    current = get_object_or_404(Chat, id=chat_id)
    if current.password and not is_allow(request.session, chat_id):
        return redirect('require_password', chat_id=chat_id)

    filename = '{}-{}'.format(now.strftime('%y-%m-%d'), current.title)
    method = method.strip()
    if method not in EXPORT_METHOD:
        return HttpResponseBadRequest('Bad Request')
    return EXPORT_METHOD[method](filename, current)


class ChatSerializers(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = Chat
        fields = ['id', 'chat_id', 'title']


class ChatViewSet(mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = Chat.objects.all()
    serializer_class = ChatSerializers
    filterset_fields = ['chat_id', 'title']

