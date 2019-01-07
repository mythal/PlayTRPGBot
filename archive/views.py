from django.shortcuts import render, get_object_or_404

from .models import Chat


def index(request):
    chats = Chat.objects.all()
    return render(request, 'index.html', {'chats': chats})


def logs(request, chat_id):
    chat = get_object_or_404(Chat, id=chat_id)
    log_filter = dict()
    if chat.save_date:
        log_filter['created__lt'] = chat.save_date
    context = dict(
        chat=chat,
        logs=chat.log_set.filter(deleted=False, **log_filter),
    )
    return render(request, 'chat.html', context)
