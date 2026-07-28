#!/usr/bin/env bash
set -Eeuo pipefail

cd /app

python manage.py check
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py bootstrap_plans

exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-10000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --timeout "${GUNICORN_TIMEOUT:-180}" \
  --access-logfile - \
  --error-logfile -
