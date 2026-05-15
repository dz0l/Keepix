#!/usr/bin/env bash
set -euo pipefail

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "ERROR: нет команды: $1" >&2
    exit 1
  }
}

escape_env_value() {
  printf '%s' "$1" | sed "s/'/'\"'\"'/g"
}

if [[ "${EUID:-0}" -ne 0 ]]; then
  echo "Запуск от root: sudo bash scripts/install_docker.sh"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
if [[ -n "${1:-}" ]]; then
  APP_DIR="$1"
else
  APP_DIR="$PROJECT_DIR"
fi

PRIMARY_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
ALLOWED_HOSTS_DEFAULT='localhost,127.0.0.1'
if [[ -n "${PRIMARY_IP:-}" && "$PRIMARY_IP" != '127.0.0.1' ]]; then
  ALLOWED_HOSTS_DEFAULT="${ALLOWED_HOSTS_DEFAULT},${PRIMARY_IP}"
fi

# По умолчанию — полностью автоматически (без вопросов): для интерактива задайте KEEPIX_INTERACTIVE=1.
AUTO_INSTALL=1
if [[ "${KEEPIX_INTERACTIVE:-0}" == '1' && -t 0 && -t 1 ]]; then
  AUTO_INSTALL=0
fi

prompt_default() {
  local label="$1"
  local default_value="$2"
  local value
  read -r -p "$label [$default_value]: " value
  echo "${value:-$default_value}"
}

prompt_secret() {
  local label="$1"
  local value
  read -r -s -p "$label: " value
  echo
  echo "$value"
}

if [[ "$AUTO_INSTALL" -eq 1 ]]; then
  REPO_URL_EFFECTIVE=""
  if [[ -d "$APP_DIR/.git" ]]; then
    REPO_URL_EFFECTIVE="$(git -C "$APP_DIR" config --get remote.origin.url 2>/dev/null || true)"
  fi
  if [[ -z "${REPO_URL_EFFECTIVE:-}" ]]; then
    REPO_URL_EFFECTIVE="${REPO_URL:-https://github.com/dz0l/Keepix.git}"
  fi
  APP_PORT="${KEEPIX_APP_PORT:-80}"
  DEBUG_VALUE="${KEEPIX_DEBUG:-0}"
  ALLOWED_HOSTS_VALUE="${KEEPIX_ALLOWED_HOSTS:-$ALLOWED_HOSTS_DEFAULT}"
  DB_NAME_VALUE="${KEEPIX_DB_NAME:-keepix_db}"
  DB_USER_VALUE="${KEEPIX_DB_USER:-keepix_user}"
  DB_PASSWORD_VALUE="${KEEPIX_DB_PASSWORD:-$(openssl rand -base64 32 | tr -d '\n')}"
else
  REPO_CURRENT="$(git -C "$APP_DIR" config --get remote.origin.url 2>/dev/null || true)"
  REPO_URL_EFFECTIVE="$(prompt_default 'URL репозитория' "${REPO_CURRENT:-https://github.com/dz0l/Keepix.git}")"
  APP_PORT="$(prompt_default 'Опубликованный HTTP-порт' '80')"
  DEBUG_VALUE="$(prompt_default 'DEBUG (0/1)' '0')"
  ALLOWED_HOSTS_VALUE="$(prompt_default 'ALLOWED_HOSTS (через запятую)' "$ALLOWED_HOSTS_DEFAULT")"
  DB_NAME_VALUE="$(prompt_default 'Имя базы PostgreSQL' 'keepix_db')"
  DB_USER_VALUE="$(prompt_default 'Пользователь БД' 'keepix_user')"
  DB_PASSWORD_VALUE="$(prompt_secret 'Пароль пользователя БД')"
  DB_PASSWORD_VALUE="${DB_PASSWORD_VALUE//$'\r'/}"
fi

SECRET_KEY_VALUE="${KEEPIX_SECRET_KEY:-}"
if [[ -z "$SECRET_KEY_VALUE" ]]; then
  SECRET_KEY_VALUE="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(80))
PY
)"
fi

if [[ -z "$DB_PASSWORD_VALUE" ]]; then
  echo 'ERROR: пароль БД пустой'
  exit 1
fi

echo '=== Установка Docker-пакетов Keepix ==='
export DEBIAN_FRONTEND=noninteractive
require_cmd apt-get
require_cmd openssl
apt-get update -qq
apt-get install -y -qq ca-certificates curl gnupg lsb-release git python3

if ! command -v docker >/dev/null 2>&1 || ! docker compose version >/dev/null 2>&1; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
    $(. /etc/os-release && echo "$VERSION_CODENAME") stable" >/etc/apt/sources.list.d/docker.list
  apt-get update -qq
  apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

mkdir -p "$APP_DIR"

if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" fetch --all --prune || true
  git -C "$APP_DIR" pull --ff-only || true
else
  rm -rf "$APP_DIR"
  git clone "$REPO_URL_EFFECTIVE" "$APP_DIR"
fi

cd "$APP_DIR"

{
  printf "SECRET_KEY='%s'\n" "$(escape_env_value "$SECRET_KEY_VALUE")"
  printf 'DEBUG=%s\n' "$DEBUG_VALUE"
  printf 'FORCE_HTTPS=0\n'
  printf 'USE_X_ACCEL=1\n'
  printf "ALLOWED_HOSTS='%s'\n" "$(escape_env_value "$ALLOWED_HOSTS_VALUE")"
  printf "DB_NAME='%s'\n" "$(escape_env_value "$DB_NAME_VALUE")"
  printf "DB_USER='%s'\n" "$(escape_env_value "$DB_USER_VALUE")"
  printf "DB_PASSWORD='%s'\n" "$(escape_env_value "$DB_PASSWORD_VALUE")"
  printf 'DB_HOST=db\n'
  printf 'DB_PORT=5432\n'
  printf 'APP_PORT=%s\n' "$APP_PORT"
} >"$APP_DIR/.env"
chmod 600 "$APP_DIR/.env"

echo 'Сборка и запуск контейнеров...'
if ! docker compose --env-file "$APP_DIR/.env" up -d --build; then
  docker compose logs --tail=120 db >&2 || true
  docker compose logs --tail=120 app >&2 || true
  exit 1
fi

echo
echo '=== Keepix установлен ==='
echo "Откройте в браузере: http://${PRIMARY_IP:-<ip-сервера>}:${APP_PORT}/accounts/login/"
echo "Создайте администратора (пароль спросит интерактивно — не передавайте в строке команд):"
echo "  docker compose exec -it app python manage.py create_staff_user admin --role admin"
echo "Учётные данные БД записаны в: $APP_DIR/.env"
