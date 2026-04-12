#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DEFAULT="$HOME/.openclaw/workspace/.venvs/cadrender312"
VENV_PATH="${NATURALCAD_FRONTEND_VENV:-$VENV_DEFAULT}"
BACKEND_ENV_PATH="$ROOT/apps/backend-api/.env"

if [[ ! -x "$VENV_PATH/bin/python3" ]]; then
  echo "NaturalCAD frontend venv not found at: $VENV_PATH" >&2
  echo "Set NATURALCAD_FRONTEND_VENV=/path/to/venv if you want to use a different one." >&2
  exit 1
fi

if [[ -z "${NATURALCAD_BACKEND_URL:-}" ]]; then
  export NATURALCAD_BACKEND_URL="http://127.0.0.1:8010"
fi

if [[ -z "${NATURALCAD_API_KEY:-}" && -f "$BACKEND_ENV_PATH" ]]; then
  backend_secret="$(grep '^API_SHARED_SECRET=' "$BACKEND_ENV_PATH" | tail -n 1 | cut -d= -f2-)"
  if [[ -n "$backend_secret" ]]; then
    export NATURALCAD_API_KEY="$backend_secret"
  fi
fi

cd "$ROOT"
source "$VENV_PATH/bin/activate"
pip install -r requirements.txt
exec python3 app.py
