#!/usr/bin/env bash
set -o errexit

DJANGO_SETTINGS_MODULE=config.settings
python manage.py collectstatic --noinput
python manage.py migrate --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT