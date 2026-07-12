#!/usr/bin/env bash
# Deploy apps/cad-worker/main.py into the existing Modal app `naturalcad`.
# Requires:
#   - `modal` CLI authenticated (`modal token new`)
#   - Modal secrets already present from the HF/alpha deploy:
#       openrouter-secret, supabase-secret, naturalcad-api-key
#
# Usage:
#   ./scripts/deploy-modal-worker.sh
#
# After deploy, copy the generate_cad_endpoint URL printed by Modal into the
# backend env as NATURALCAD_CAD_WORKER_URL.

set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."

if ! command -v modal >/dev/null 2>&1; then
  echo "[deploy-modal-worker] modal CLI not found. Install with: pip install modal" >&2
  exit 1
fi

cd apps/cad-worker
echo "[deploy-modal-worker] Deploying apps/cad-worker/main.py to Modal app 'naturalcad'..."
modal deploy main.py
echo "[deploy-modal-worker] Done. Copy the generate_cad_endpoint URL into NATURALCAD_CAD_WORKER_URL."
