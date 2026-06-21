#!/usr/bin/env bash
# Bascule Sonosregie entre mode protégé (oauth2-proxy/Authentik) et ouvert.
#
#   ./set-mode.sh auth     -> app en interne :8096, oauth2-proxy en façade :8095
#   ./set-mode.sh noauth    -> app exposée directement :8095 (aucune auth)
#
# Idempotent. N'agit que sur les units Quadlet --user de cette app.
set -euo pipefail

MODE="${1:-}"
UNIT_DIR="$HOME/.config/containers/systemd"
APP="$UNIT_DIR/sonosregie.container"
PROXY="$UNIT_DIR/sonosregie-auth.container"
ENVFILE="$HOME/.config/sonosregie/oauth2-proxy.env"
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"

[[ -f "$APP" ]] || { echo "Unit app introuvable: $APP (déploie d'abord l'app)"; exit 1; }

set_bind() {  # <host> <port> : (ré)écrit les Environment=BIND_* dans le .container de l'app
  sed -i '/^Environment=BIND_HOST=/d;/^Environment=BIND_PORT=/d' "$APP"
  sed -i "\#^Image=localhost/sonosregie#a Environment=BIND_HOST=$1\nEnvironment=BIND_PORT=$2" "$APP"
}

case "$MODE" in
  auth)
    [[ -f "$ENVFILE" ]] || { echo "✗ $ENVFILE absent — lance d'abord le bootstrap Authentik."; exit 1; }
    set_bind 127.0.0.1 8096
    cp "$HERE/sonosregie-auth.container" "$PROXY"
    systemctl --user daemon-reload
    systemctl --user restart sonosregie.service
    systemctl --user start sonosregie-auth.service
    echo "✅ Mode AUTH : oauth2-proxy :8095  ->  app interne 127.0.0.1:8096"
    ;;
  noauth)
    systemctl --user stop sonosregie-auth.service 2>/dev/null || true
    rm -f "$PROXY"
    set_bind 0.0.0.0 8095
    systemctl --user daemon-reload
    systemctl --user restart sonosregie.service
    echo "✅ Mode OUVERT : app exposée directement sur :8095 (aucune auth)"
    ;;
  *)
    echo "usage: $0 auth|noauth"; exit 1 ;;
esac
