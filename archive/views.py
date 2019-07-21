import datetime
from typing import Optional

from django.http import HttpResponseBadRequest
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.cache import cache_page
from django.core.paginator import Paginator

from . import forms
from .export import EXPORT_METHOD
from .models import Chat, Tag


def index(request):
    return render(request, 'index.html', dict(
        chats=Chat.objects.filter().order_by('-created')
    ))


session_key = lambda chat_id: 'chat:{}:allow'.format(chat_id)


def is_allow(session, chat_id):
    return session_key(chat_id) in session


def allow(session, chat_id):
    session[session_key(chat_id)] = True


def chat(request, chat_id):
    current: Chat = get_object_or_404(Chat, id=chat_id)
    tag_id = request.GET.get('tag', None)
    search: Optional[str] = request.GET.get('search', None)
    page_number = int(request.GET.get('page', 1))
    tag = None
    if tag_id:
        tag: Optional[Tag] = get_object_or_404(Tag, id=tag_id)

    log_set = current.query_log()
    if tag:
        log_set = log_set.filter(tag=tag)
    if search:
        for keyword in search.split():
            log_set = log_set.filter(content__icontains=keyword)
    if current.password and not is_allow(request.session, chat_id):
        return redirect('require_password', chat_id=chat_id)
    paginator = Paginator(log_set, per_page=10)
    page = paginator.page(page_number)
    context = dict(chat=current, log_list=page, tag=tag, search=search, form=forms.Search())
    return render(request, 'chat.html', context)


def require_password(request, chat_id):
    current = get_object_or_404(Chat, id=chat_id)
    wrong = False
    if request.method == 'POST':
        form = forms.Password(request.POST)
        if form.is_valid() and current.validate(form.cleaned_data['password']):
            allow(request.session, chat_id)
            return redirect(chat, chat_id=chat_id)
        wrong = True
    else:
        form = forms.Password()
    context = dict(chat=current, form=form, wrong=wrong)
    return render(request, 'require_password.html', context, status=401)


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
