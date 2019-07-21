import csv

from django.http import HttpResponse, JsonResponse


def csv_export(filename, current):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="{}.csv"'.format(filename)

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
    for log in current.query_log():
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
    for log in current.query_log():
        export_data.append({
            'message_id': log.message_id,
            'user_fullname': log.user_fullname,
            'character_name': log.character_name,
            'type': log.get_kind_display(),
            'entities': log.entities,
            'media': log.media_url(),
            'is_gm': log.gm,
            'created': log.created,
            'reply_to': log.reply_message_id(),
        })
    return JsonResponse(export_data, safe=False)


EXPORT_METHOD = {
    'csv': csv_export,
    'json': json_export,
}

__ALL__ = ['EXPORT_METHOD']
