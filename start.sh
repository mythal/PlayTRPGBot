#!/usr/bin/env bash
source ./.env
python manage.py migrate --noinput
python manage.py collectstatic --noinput
if [[ -z "${RUNSERVER}" ]]; then
    uwsgi --ini deploy/uwsgi.ini --socket 127.0.0.1:8880
else
    python manage.py runserver 0.0.0.0:8880
fi
