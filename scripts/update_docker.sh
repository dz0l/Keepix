#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-${KEEPIX_INSTALL_DIR:-/opt/keepix}}"

if [[ ! -d "$APP_DIR/.git" ]]; then
  echo "ERROR: нет каталога с git: $APP_DIR"
  exit 1
fi
if [[ $EUID -ne 0 ]]; then
  echo "Запустите от root: sudo bash scripts/update_docker.sh $APP_DIR"
  exit 1
fi
require_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "Нет команды: $1" >&2; exit 1; }; }
require_cmd docker

cd "$APP_DIR"
git fetch --all --prune
git pull --ff-only

PRIMARY_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
if [[ -f ".env" && -n "${PRIMARY_IP:-}" && "$PRIMARY_IP" != '127.0.0.1' ]]; then
  CURRENT_HOSTS="$(grep -E '^ALLOWED_HOSTS=' .env | tail -n1 | cut -d= -f2- || true)"
  CURRENT_HOSTS="${CURRENT_HOSTS%\'}"
  CURRENT_HOSTS="${CURRENT_HOSTS#\'}"
  CURRENT_HOSTS="${CURRENT_HOSTS%\"}"
  CURRENT_HOSTS="${CURRENT_HOSTS#\"}"
  if [[ -n "$CURRENT_HOSTS" && ",$CURRENT_HOSTS," != *",$PRIMARY_IP,"* ]]; then
    NEW_HOSTS="${CURRENT_HOSTS},${PRIMARY_IP}"
    sed -i.bak -E "s|^ALLOWED_HOSTS=.*$|ALLOWED_HOSTS='${NEW_HOSTS}'|" .env || true
    echo "Обновлено ALLOWED_HOSTS: добавлен IP ${PRIMARY_IP}"
  fi
fi

docker compose --env-file .env up -d --build
docker compose ps

echo 'Обновление завершено.'
