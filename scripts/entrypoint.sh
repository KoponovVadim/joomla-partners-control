#!/bin/sh
set -eu
python - <<'PY'
import os, socket, time
host = os.getenv("POSTGRES_HOST", "db")
port = int(os.getenv("POSTGRES_PORT", "5432"))
for attempt in range(60):
    try:
        with socket.create_connection((host, port), timeout=2):
            break
    except OSError:
        if attempt == 59: raise
        time.sleep(1)
PY
python manage.py migrate --noinput
python manage.py collectstatic --noinput
exec gunicorn jpc.wsgi:application --bind 0.0.0.0:8000 --workers "${GUNICORN_WORKERS:-3}" --timeout 60 --access-logfile -

