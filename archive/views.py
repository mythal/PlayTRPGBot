from django.shortcuts import render, get_object_or_404

from .models import Chat


def index(request):
    chats = Chat.objects.all().order_by('created')
    return render(request, 'index.html', {'chats': chats})


def logs(request, chat_id):
    chat = get_object_or_404(Chat, id=chat_id)
    context = dict(
        chat=chat,
        logs=chat.log_set.filter(deleted=False).order_by('created'),
    )
    return render(request, 'chat.html', context)
