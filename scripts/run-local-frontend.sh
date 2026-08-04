#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DEFAULT="$ROOT/.venv"
LEGACY_VENV="$HOME/.openclaw/workspace/.venvs/cadrender312"
VENV_PATH="${NATURALCAD_FRONTEND_VENV:-$VENV_DEFAULT}"

if [[ ! -x "$VENV_PATH/bin/python3" && -x "$LEGACY_VENV/bin/python3" ]]; then
  VENV_PATH="$LEGACY_VENV"
fi

cd "$ROOT"

if [[ ! -x "$VENV_PATH/bin/python3" ]]; then
  PYTHON_BIN=""
  for candidate in python3.12 python3.11 python3; do
    if command -v "$candidate" >/dev/null 2>&1; then
      PYTHON_BIN="$candidate"
      break
    fi
  done

  if [[ -z "$PYTHON_BIN" ]]; then
    echo "Could not find a usable Python interpreter to create the NaturalCAD frontend venv." >&2
    exit 1
  fi

  echo "Creating NaturalCAD frontend venv at: $VENV_PATH"
  "$PYTHON_BIN" -m venv "$VENV_PATH"
fi

source "$VENV_PATH/bin/activate"
pip install -r requirements.txt
exec python3 app.py
