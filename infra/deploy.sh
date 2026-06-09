#!/usr/bin/env bash
# Runs on the LXC container after the /deploy endpoint pulls main.
# Idempotent: safe to re-run. Logs to /var/log/hyzerpath-deploy.log if writable.
set -euo pipefail

APP_DIR="${APP_DIR:-/home/hyzerpath/hyzerpath}"
VENV="${VENV:-$APP_DIR/backend/.venv}"
WEB_ROOT="${WEB_ROOT:-/var/www/hyzerpath}"
SERVICE="${SERVICE:-hyzerpath}"

LOG="/var/log/hyzerpath-deploy.log"
if touch "$LOG" 2>/dev/null; then
    exec >>"$LOG" 2>&1
fi
echo "=== deploy $(date -Is) — $(git -C "$APP_DIR" rev-parse --short HEAD) ==="

# --- backend ---
cd "$APP_DIR/backend"
"$VENV/bin/pip" install -q -r requirements.txt
"$VENV/bin/alembic" upgrade head

# --- frontend ---
cd "$APP_DIR/frontend"
npm ci --silent
npm run build
mkdir -p "$WEB_ROOT"
rsync -a --delete build/ "$WEB_ROOT/"

# --- restart API (last: kills the process that spawned us) ---
sudo systemctl restart "$SERVICE"
echo "=== deploy complete ==="
