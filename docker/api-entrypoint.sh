#!/usr/bin/env bash
#
# The API container owns schema changes: it migrates, then serves. The worker
# waits on this container's healthcheck, so by the time it starts the schema is
# already current and there is no migration race between the two.
#
set -euo pipefail

echo "==> Applying migrations"
python manage.py migrate --noinput

echo "==> Collecting static files"
python manage.py collectstatic --noinput --clear


echo "==> Initializing superuser"
python manage.py initialize_superuser

echo "==> Starting Gunicorn on :8000"
exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-4}" \
    --timeout 120 \
    --graceful-timeout 30 \
    --access-logfile - \
    --error-logfile -
