#!/bin/bash
celery -A taskflow worker -l info -B &
gunicorn taskflow.wsgi:application --bind 0.0.0.0:$PORT --workers 2
