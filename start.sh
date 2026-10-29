#!/bin/bash
gunicorn taskflow.wsgi:application --bind 0.0.0.0:$PORT --workers 2
