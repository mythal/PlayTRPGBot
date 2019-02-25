import csv
import datetime

from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse, HttpResponseForbidden
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
    context['password'] = password
    if current.validate(password):
        context['logs'] = current.all_log()
        return render(request, 'chat.html', context, status=403)
    else:
        context['wrong_password'] = bool(password)
        return render(request, 'chat_password.html', context=context)


def csv_export(filename, current):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="{}.csv"' \
        .format(filename)

    writer = csv.writer(response)
    writer.writerow((
        'Message ID',
        'User Fullname',
        'Character Name',
        'Type',
        'Content',
        'Media',
        'Is GM',
        'Date',
    ))
    for log in current.all_log():
        writer.writerow((
            str(log.message_id),
            log.user_fullname,
            log.character_name,
            log.get_kind_display(),
            log.content,
            log.media_url(),
            str(log.gm),
            log.created.strftime('%y-%m-%d %H:%M:%S'),
        ))

    return response


def json_export(_, current):
    export_data = []
    for log in current.all_log():
        export_data.append({
            'message_id': log.message_id,
            'user_fullname': log.user_fullname,
            'character_name': log.character_name,
            'type': log.get_kind_display(),
            'content': log.content,
            'media': log.media_url(),
            'is_gm': log.gm,
            'created': log.created,
            'reply_to': log.reply_message_id(),
        })
    return JsonResponse(export_data, safe=False)


def export(request, chat_id, method):
    now = datetime.datetime.now()
    current = get_object_or_404(Chat, id=chat_id)
    if not current.validate(request.GET.get('password', '')):
        return HttpResponseForbidden('Forbidden')
    filename = '{}-{}'.format(now.strftime('%y-%m-%d'), current.title)

    if method == 'csv':
        return csv_export(filename, current)
    elif method == 'json':
        return json_export(filename, current)
    else:
        return HttpResponseBadRequest('Bad Request')
