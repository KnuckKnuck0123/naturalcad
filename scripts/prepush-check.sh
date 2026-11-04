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

# .env.example files are tracked templates with placeholder values only.
allowed_example_files=(
  "apps/backend-api/.env.example"
  "apps/backend-api/cloudrun.env.yaml.example"
  "apps/web/.env.example"
  "archive/gradio-demo-backend-legacy/.env.example"
)

tracked_files="$(git ls-files)"

for pattern in "${blocked_paths[@]}"; do
  matches=$(git ls-files "$pattern" || true)
  if [[ -n "$matches" ]]; then
    # Filter out explicitly allowed example templates.
    unexpected=""
    for file in $matches; do
      is_allowed=0
      for allowed in "${allowed_example_files[@]}"; do
        if [[ "$file" == "$allowed" ]]; then
          is_allowed=1
          break
        fi
      done
      if [[ "$is_allowed" -eq 0 ]]; then
        unexpected="${unexpected}${file}\n"
      fi
    done
    if [[ -n "$unexpected" ]]; then
      echo -e "[prepush] blocked tracked path matches pattern: $pattern"
      echo -e "$unexpected"
      exit 1
    fi
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
