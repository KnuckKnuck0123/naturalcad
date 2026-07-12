#!/usr/bin/env bash
# Beta end-to-end smoke: hits the hosted backend through the same path the
# Vercel frontend uses, and confirms guest session + project + generation
# behavior at least round-trips.
#
# Usage:
#   BETA_API_BASE=https://api.beta.naturalcad.example \
#   BETA_API_KEY=<API_SHARED_SECRET> \
#   ./scripts/smoke-beta.sh

set -euo pipefail

: "${BETA_API_BASE:?Set BETA_API_BASE to the backend base URL, e.g. https://api.beta.naturalcad.example}"
: "${BETA_API_KEY:?Set BETA_API_KEY to the API_SHARED_SECRET value}"

H_KEY=("-H" "x-api-key: $BETA_API_KEY")
JSON=("-H" "content-type: application/json")

echo "[smoke] 1. health"
curl -sS -f "${BETA_API_BASE%/}/v1/health" "${H_KEY[@]}" | sed 's/.*/  &/'

echo "[smoke] 2. guest session"
SESSION_RESP=$(curl -sS -f -X POST "${BETA_API_BASE%/}/v1/auth/guest" "${H_KEY[@]}" "${JSON[@]}" -d '{}')
SESSION_ID=$(echo "$SESSION_RESP" | python3 -c 'import json,sys;print(json.load(sys.stdin)["session_id"])')
echo "  session_id=$SESSION_ID"

H_SESS=("-H" "x-session-id: $SESSION_ID")

echo "[smoke] 3. create project"
PROJECT_RESP=$(curl -sS -f -X POST "${BETA_API_BASE%/}/v1/projects" \
  "${H_KEY[@]}" "${H_SESS[@]}" "${JSON[@]}" \
  -d '{"title":"smoke","mode":"part","output_type":"3d_solid"}')
PROJECT_ID=$(echo "$PROJECT_RESP" | python3 -c 'import json,sys;print(json.load(sys.stdin)["id"])')
echo "  project_id=$PROJECT_ID"

echo "[smoke] 4. start generation"
GEN_RESP=$(curl -sS -f -X POST "${BETA_API_BASE%/}/v1/projects/$PROJECT_ID/generations" \
  "${H_KEY[@]}" "${H_SESS[@]}" "${JSON[@]}" \
  -d "$(python3 -c 'import json,uuid;print(json.dumps({"message":"a 50x30x6 mm flat bracket with two 5 mm mounting holes","parent_version_id":None,"attachment_ids":[],"profile":"balanced","idempotency_key":str(uuid.uuid4())}))')")
RUN_ID=$(echo "$GEN_RESP" | python3 -c 'import json,sys;print(json.load(sys.stdin)["id"])')
echo "  run_id=$RUN_ID status=$(echo "$GEN_RESP" | python3 -c 'import json,sys;print(json.load(sys.stdin)["status"])')"

echo "[smoke] 5. poll until done (max 60s)"
for i in $(seq 1 30); do
  POLL=$(curl -sS -f "${BETA_API_BASE%/}/v1/projects/$PROJECT_ID/generations/$RUN_ID" "${H_KEY[@]}" "${H_SESS[@]}")
  STATUS=$(echo "$POLL" | python3 -c 'import json,sys;print(json.load(sys.stdin)["status"])')
  echo "  attempt $i status=$STATUS"
  case "$STATUS" in
    succeeded|completed|done|failed|needs_clarification|awaiting_clarification) break ;;
  esac
  sleep 2
done

echo "[smoke] final status: $STATUS"
echo "$POLL" | python3 -m json.tool | head -40
