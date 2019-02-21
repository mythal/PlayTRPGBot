from hashlib import sha256

from django.shortcuts import render, get_object_or_404

from .models import Chat


def index(request):
    all_chats = Chat.objects.filter(parent=None).order_by('-created')
    chat_list = []
    for x in all_chats:
        count = x.log_set.filter(deleted=False).count()
        if count > 0:
            x.log_count = count
            chat_list.append(x)
    return render(request, 'index.html', dict(chats=chat_list))


def chat(request, chat_id):
    current = get_object_or_404(Chat, id=chat_id)
    context = dict(chat=current)
    password = request.POST.get('password', '')
    if not current.password or current.password == sha256(password.encode()).hexdigest():
        context['logs'] = current.log_set.filter(deleted=False).order_by('created')
        return render(request, 'chat.html', context)
    else:
        context['wrong_password'] = bool(password)
        return render(request, 'chat_password.html', context=context)
