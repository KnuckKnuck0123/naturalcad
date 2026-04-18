#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$ROOT/apps/backend-api"
LEGACY_BACKEND_DIR="$ROOT/archive/gradio-demo-backend-legacy"

if [[ ! -f "$BACKEND_DIR/requirements.txt" ]]; then
  if [[ -f "$LEGACY_BACKEND_DIR/requirements.txt" ]]; then
    echo "apps/backend-api was removed in recent cleanup; using legacy backend from archive/ for local dev."
    BACKEND_DIR="$LEGACY_BACKEND_DIR"
  else
    echo "No local backend requirements found." >&2
    echo "Use Modal endpoint via NATURALCAD_BACKEND_URL for frontend testing." >&2
    exit 1
  fi
fi

cd "$BACKEND_DIR"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -r requirements.txt
exec uvicorn app.main:app --reload --port "${NATURALCAD_BACKEND_PORT:-8010}"
