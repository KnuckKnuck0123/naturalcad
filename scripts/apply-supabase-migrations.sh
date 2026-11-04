#!/usr/bin/env bash
# Apply the v1 domain + iterative_generation migrations against the existing
# Supabase project that the HF/alpha deploy already uses.
#
# Requires:
#   - SUPABASE_DB_URL env (Postgres connection string from Supabase project settings)
#   - `psql` installed
#
# Usage:
#   SUPABASE_DB_URL='postgresql://...' ./scripts/apply-supabase-migrations.sh

set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/.."

if [[ -z "${SUPABASE_DB_URL:-}" ]]; then
  echo "[apply-supabase-migrations] SUPABASE_DB_URL not set." >&2
  echo "  Set it to the project connection string from Supabase > Project Settings > Database." >&2
  exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "[apply-supabase-migrations] psql not found." >&2
  exit 1
fi

for migration in \
  supabase/migrations/20260424_000001_domain_v1.sql \
  supabase/migrations/20260621_000002_iterative_generation.sql; do
  echo "[apply-supabase-migrations] Applying $migration"
  psql "$SUPABASE_DB_URL" -v ON_ERROR_STOP=1 -f "$migration"
done

echo "[apply-supabase-migrations] Done."
echo "Reminder: also create the storage bucket 'naturalcad-source-images' (private)."
