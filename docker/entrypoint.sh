#!/usr/bin/env sh
set -eu

if [ "${WAIT_FOR_DB:-1}" = "1" ]; then
  echo "Waiting for PostgreSQL..."
  python - <<'PY'
import os
import time

import psycopg2

host = os.getenv("DB_HOST", "db")
port = int(os.getenv("DB_PORT", "5432"))
name = os.getenv("DB_NAME", "")
user = os.getenv("DB_USER", "")
password = os.getenv("DB_PASSWORD", "")

for _ in range(60):
    try:
        psycopg2.connect(
            host=host,
            port=port,
            dbname=name,
            user=user,
            password=password,
            connect_timeout=3,
        ).close()
        print("PostgreSQL is ready.")
        break
    except Exception:
        time.sleep(2)
else:
    raise SystemExit("PostgreSQL is not reachable.")
PY
fi

python manage.py migrate
python manage.py collectstatic --noinput

chmod -R a+rX /app/staticfiles || true
chmod -R a+rX /app/media || true

if [ "$(id -u)" = "0" ]; then
  chown -R app:app /app/media /app/staticfiles /app/backups || true
  exec su -s /bin/sh app -c "gunicorn keepix.wsgi:application --bind 0.0.0.0:8000 --workers ${GUNICORN_WORKERS:-3} --timeout 120"
fi

exec gunicorn keepix.wsgi:application \
  --bind "0.0.0.0:8000" \
  --workers "${GUNICORN_WORKERS:-3}" \
  --timeout 120
