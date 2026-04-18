#!/usr/bin/env bash
set -euo pipefail

echo "[prepush] checking for tracked env/secrets artifacts"

# Block obvious sensitive files from being tracked.
blocked_paths=(
  "*.env"
  "*.env.*"
  "**/artifacts/logs/*.jsonl"
  "**/.venv/**"
)

tracked_files="$(git ls-files)"

for pattern in "${blocked_paths[@]}"; do
  if git ls-files "$pattern" | grep -q .; then
    echo "[prepush] blocked tracked path matches pattern: $pattern"
    git ls-files "$pattern"
    exit 1
  fi
done

echo "[prepush] scanning staged diff for probable secret values"

# Detect likely secret VALUES, not generic key names in docs.
if git diff --cached -- . | rg -n --no-heading \
  "(sk-[A-Za-z0-9_-]{16,}|Bearer\s+[A-Za-z0-9._-]{20,}|(API|SECRET|TOKEN|PASSWORD)\s*=\s*['\"]?[A-Za-z0-9._-]{16,}|SUPABASE_SERVICE_ROLE_KEY\s*=\s*['\"]?[A-Za-z0-9._-]{16,})"; then
  echo "[prepush] potential secret-like content found in staged diff"
  echo "[prepush] review with: git diff --cached"
  exit 1
fi

echo "[prepush] OK"
