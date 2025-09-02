#!/usr/bin/env bash
set -o errexit

python manage.py collectstatic --noinput
python manage.py migrate --noinput
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT