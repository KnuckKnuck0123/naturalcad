# NaturalCAD Public Beta Ship — Design

Date: 2026-07-12
Status: Approved
Scope: Ship the existing stack as an open public beta with blocker fixes, model swapping, and public-beta policies.

## Goals

- Deploy the hosted product lane (Vercel + Cloud Run + Modal + Supabase) as an open public beta.
- Fix the five deploy/cost blockers before launch.
- Give the operator config-only model swapping (cheap <-> expensive) across all LLM roles.
- Add legal docs (Terms + Privacy) and abuse limits sized for public traffic.
- Preloaded OpenRouter credits act as the global spend ceiling; per-IP and per-session caps
  prevent any single user draining the pool.
- Hugging Face demo branch (`huggingface`) is untouched.

## Non-goals (deferred post-beta)

- Modal orchestration consolidation (moving `process_generation` into the worker).
- Multimodal spec resolution / geometry-validation accuracy upgrade.
- Payments, sign-in/auth accounts.
- Worker and frontend test suites.

## Blocker fixes

1. **Cloud Run CPU throttling.** `process_generation` runs as a FastAPI BackgroundTask after
   the 202 response; Cloud Run throttles CPU between requests, stalling generation. Fix:
   `scripts/deploy-cloud-run-backend.sh` gains `--no-cpu-throttling --min-instances=1`
   (~$15-30/mo idle cost).
2. **Double-execution race.** The poll-triggered recovery loop (`main.py get_generation`) can
   re-enqueue `process_generation` while the original background task is still running. Fix:
   atomic run claim. `process_generation` starts with a compare-and-swap claim
   (`processing_claimed_at` on the run; Supabase conditional update + in-memory analog).
   Recovery may only re-claim a claim older than 5 minutes. No claim -> no duplicate versions
   or duplicate LLM spend.
3. **Fallback cost trap.** The legacy worker path defaults to `anthropic/claude-opus-4.7` and
   is the automatic fallback whenever `resolve_spec` throws — including when only the vision
   call blips. Fix: (a) legacy default model becomes the env-configured CAD model (mid-tier);
   (b) vision-call failures are caught inside `resolve_spec` and degrade to
   no-image-summary instead of collapsing the structured path.
4. **Per-IP limits.** Guest quotas are per-session; sessions are free to mint, so public
   abusers bypass caps trivially. Fix: sliding-window per-IP limits on session creation and
   generation runs, enforced with the same Supabase RPC pattern as existing quotas (new
   migration + in-memory analog), keyed by the trusted forwarded-IP header
   (Cloudflare/Cloud Run).
5. **Honest token accounting.** Usage telemetry from failed retry attempts is dropped, so the
   guest token cap undercounts exactly the expensive runs. Fix: accumulate `usage` from every
   attempt into run telemetry.

## Model swapping

- All model roles env-driven and swappable via config-only redeploy:
  `NATURALCAD_MODE_FAST`, `NATURALCAD_MODE_BALANCED`, `NATURALCAD_MODE_QUALITY`,
  `NATURALCAD_VISION_MODEL`, plus the legacy fallback model.
- Wire the existing Fast/Balanced/Quality UI switcher: `run.profile` dispatches
  `MODEL_PROFILES[profile].model` to the worker `generate_code` call (today it always uses
  `NATURALCAD_CAD_MODEL`).
- Honest telemetry: spec resolution is deterministic (regex) — stop reporting an unused spec
  model; delete the dead spec-LLM code in the worker (`_SPEC_SYSTEM_PROMPT`,
  `SpecResolution`, unused `model` param).

## Public-beta policies

- **Legal:** `/terms` and `/privacy` pages in `apps/web` covering: beta disclaimer,
  LLM-processing disclosure (prompts/images sent to model providers via OpenRouter), data
  storage in Supabase, uploaded-image sanitization and retention, no warranty, acceptable
  use, contact. Footer links plus a "By generating, you agree to the Terms" line at the
  prompt box. Drafted by the agent; reviewed by Noah; not legal advice.
- **Limits:** tightened guest caps for public traffic (per-IP from blocker 4 plus existing
  per-session/per-project caps), documented in `cloudrun.env.yaml.example`.
- **Kill switch:** env flag that disables new generations with a friendly 503, so spend can
  be stopped instantly without tearing anything down.

## Cleanup (folded in)

- Fix env-name inconsistency in `docs/beta-deployment.md` section 4 (frontend uses
  `NATURALCAD_BACKEND_URL` / `NATURALCAD_API_KEY`, not `NEXT_PUBLIC_API_BASE_URL` /
  `API_SHARED_SECRET`).
- Fix `scripts/smoke-beta.sh` polling for nonexistent status names.

## Testing

- Extend the existing backend suite (24 tests) with: claim-lock race, per-IP quota,
  profile -> model dispatch, token accumulation across attempts.
- `npm run web:typecheck && npm run web:build` green.
- Post-deploy: `scripts/smoke-beta.sh` against the hosted stack.

## Deploy sequence

1. Commit WIP + fixes (via `./scripts/prepush-check.sh`).
2. Apply Supabase migrations; ensure private attachments bucket + public artifacts bucket.
3. Deploy Modal worker (`scripts/deploy-modal-worker.sh`).
4. Deploy Cloud Run backend (`scripts/deploy-cloud-run-backend.sh`, updated flags).
5. Deploy Vercel frontend (server-only envs: `NATURALCAD_BACKEND_URL`, `NATURALCAD_API_KEY`).
6. Run `scripts/smoke-beta.sh`; put Cloudflare in front of the public domain.

Account-level steps (Modal auth, gcloud project, Vercel envs, domain/Cloudflare) are Noah's,
per `docs/beta-handoff.md`; everything scriptable is driven by the agent with exact commands
handed over for the rest.
