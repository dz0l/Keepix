#!/usr/bin/env bash
set -euo pipefail

# Единая точка входа: из клона репозитория или после curl|bash.
# Репозиторий по умолчанию: https://github.com/dz0l/Keepix
# Директория установки: /opt/keepix (переопределить: KEEPIX_INSTALL_DIR)

REPO_URL="${REPO_URL:-https://github.com/dz0l/Keepix.git}"
APP_DIR="${KEEPIX_INSTALL_DIR:-/opt/keepix}"

if [[ "${EUID:-0}" -ne 0 ]]; then
  echo "Запустите от root, например: curl -fsSL .../install.sh | sudo bash"
  exit 1
fi

if [[ -f "$APP_DIR/scripts/install_docker.sh" ]]; then
  exec bash "$APP_DIR/scripts/install_docker.sh" "$APP_DIR"
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git

if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" fetch --all --prune
  git -C "$APP_DIR" pull --ff-only
else
  rm -rf "$APP_DIR"
  mkdir -p "$(dirname "$APP_DIR")"
  git clone "$REPO_URL" "$APP_DIR"
fi

exec bash "$APP_DIR/scripts/install_docker.sh" "$APP_DIR"
