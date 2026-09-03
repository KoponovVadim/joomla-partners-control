#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

[ -f .env ] || cp .env.example .env

env_value() {
  sed -n "s/^$1=//p" .env | tail -n 1
}

invalid_env=0
for key in   SECRET_KEY   CREDENTIAL_ENCRYPTION_KEY   POSTGRES_DB   POSTGRES_USER   POSTGRES_PASSWORD   ALLOWED_HOSTS   CSRF_TRUSTED_ORIGINS   PUBLIC_BASE_URL
do
  value="$(env_value "$key")"
  if [ -z "$value" ] || [ "$value" = "change-me" ]; then
    echo "Ошибка: задайте безопасное значение $key в .env." >&2
    invalid_env=1
  fi
done

debug_value="$(env_value DEBUG)"
case "$(printf '%s' "$debug_value" | tr '[:upper:]' '[:lower:]')" in
  0|false|no|off) ;;
  *)
    echo "Ошибка: production deploy требует DEBUG=0 в .env." >&2
    invalid_env=1
    ;;
esac

case "$(env_value PUBLIC_BASE_URL)" in
  https://*) ;;
  *)
    echo "Ошибка: PUBLIC_BASE_URL должен начинаться с https://." >&2
    invalid_env=1
    ;;
esac
case "$(env_value CSRF_TRUSTED_ORIGINS)" in
  *https://*) ;;
  *)
    echo "Ошибка: CSRF_TRUSTED_ORIGINS должен содержать HTTPS origin." >&2
    invalid_env=1
    ;;
esac

[ "$invalid_env" -eq 0 ] || exit 1

current_port="$(env_value APP_PORT)"
case "$current_port" in
  ""|*[!0-9]*) current_port="" ;;
esac

keep_port=0
if [ -n "$current_port" ]; then
  if python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', int('$current_port'))); s.close()" 2>/dev/null; then
    keep_port=1
  elif docker compose port web 8000 2>/dev/null | grep -q ":${current_port}$"; then
    keep_port=1
  fi
fi
if [ "$keep_port" -ne 1 ]; then
  current_port="$(python3 scripts/find_free_port.py)"
  if grep -q '^APP_PORT=' .env; then
    sed -i "s/^APP_PORT=.*/APP_PORT=${current_port}/" .env
  else
    printf '\nAPP_PORT=%s\n' "$current_port" >> .env
  fi
fi

docker compose up -d --build
echo "Joomla Partners Control запущен:"
echo "http://127.0.0.1:${current_port}"
