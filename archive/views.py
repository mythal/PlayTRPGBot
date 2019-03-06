import datetime

from django.http import HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import render, get_object_or_404

from . import forms
from .export import EXPORT_METHOD
from .models import Chat


def index(request):
    return render(request, 'index.html', dict(
        chats=Chat.objects.filter(parent=None).order_by('-created')
    ))


def chat(request, chat_id):
    current = get_object_or_404(Chat, id=chat_id)
    session_key = 'chat:{}:allow'.format(chat_id)
    if request.method == 'POST':
        form = forms.Password(request.POST)
        if form.is_valid() and current.validate(form.cleaned_data['password']):
            request.session[session_key] = True
    else:
        form = forms.Password()

    authenticated = session_key in request.session

    if not current.password or authenticated:
        return render(request, 'chat.html', dict(chat=current))
    else:
        return render(request, 'chat_password.html', dict(chat=current, form=form))


def export(request, chat_id, method: str):
    now = datetime.datetime.now()
    current = get_object_or_404(Chat, id=chat_id)
    if current.password and 'chat:{}:allow'.format(chat_id) not in request.session:
        return HttpResponseForbidden('Request Forbidden')

    filename = '{}-{}'.format(now.strftime('%y-%m-%d'), current.title)
    method = method.strip()
    if method in EXPORT_METHOD:
        return EXPORT_METHOD[method](filename, current)
    else:
        return HttpResponseBadRequest('Bad Request')
