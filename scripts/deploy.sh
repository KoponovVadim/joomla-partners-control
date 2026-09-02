#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
[ -f .env ] || cp .env.example .env
current_port="$(sed -n 's/^APP_PORT=//p' .env | tail -n 1)"
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
if grep -q '=change-me$' .env; then
  echo "Внимание: замените значения change-me в .env перед production-запуском." >&2
fi
docker compose up -d --build
echo "Joomla Partners Control запущен:"
echo "http://127.0.0.1:${current_port}"
