#!/usr/bin/env bash
# Local readiness checklist for the NaturalCAD beta handoff.
#
# This does not deploy anything. It reports which account-side pieces still
# need attention before running the deployment scripts.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

failures=0
warnings=0

ok() {
  printf '[ok] %s\n' "$1"
}

warn() {
  warnings=$((warnings + 1))
  printf '[warn] %s\n' "$1"
}

fail() {
  failures=$((failures + 1))
  printf '[missing] %s\n' "$1"
}

need_file() {
  if [[ -f "$1" ]]; then
    ok "$1"
  else
    fail "$1"
  fi
}

need_executable() {
  if [[ -x "$1" ]]; then
    ok "$1"
  else
    fail "$1 is not executable"
  fi
}

need_command() {
  if command -v "$1" >/dev/null 2>&1; then
    ok "$1 command"
  else
    fail "$1 command"
  fi
}

optional_command() {
  if command -v "$1" >/dev/null 2>&1; then
    ok "$1 command"
  else
    warn "$1 command not found"
  fi
}

echo "NaturalCAD beta readiness"
echo

echo "Files"
need_file "apps/backend-api/Dockerfile"
need_file "apps/backend-api/cloudrun.env.yaml.example"
need_file "apps/web/vercel.json"
need_file "docs/beta-deployment.md"
need_file "docs/beta-handoff.md"
need_executable "scripts/deploy-modal-worker.sh"
need_executable "scripts/deploy-cloud-run-backend.sh"
need_executable "scripts/apply-supabase-migrations.sh"
need_executable "scripts/smoke-beta.sh"

echo
echo "Local commands"
need_command "npm"
need_command "python3"
need_command "curl"
optional_command "modal"
optional_command "gcloud"
optional_command "psql"

echo
echo "Cloud Run env"
if [[ -f "apps/backend-api/cloudrun.env.yaml" ]]; then
  ok "apps/backend-api/cloudrun.env.yaml"
  if grep -Eq 'replace-with|naturalcad\.example|example\.com' "apps/backend-api/cloudrun.env.yaml"; then
    fail "apps/backend-api/cloudrun.env.yaml still contains placeholder values"
  else
    ok "apps/backend-api/cloudrun.env.yaml has no obvious placeholders"
  fi
else
  fail "apps/backend-api/cloudrun.env.yaml (copy from .example and fill real values)"
fi

echo
echo "Smoke env"
if [[ -n "${BETA_API_BASE:-}" ]]; then
  ok "BETA_API_BASE set"
else
  warn "BETA_API_BASE not set yet"
fi
if [[ -n "${BETA_API_KEY:-}" ]]; then
  ok "BETA_API_KEY set"
else
  warn "BETA_API_KEY not set yet"
fi

echo
if (( failures > 0 )); then
  echo "Readiness: blocked on $failures required item(s), with $warnings warning(s)."
  exit 1
fi

echo "Readiness: required local handoff pieces are present, with $warnings warning(s)."
