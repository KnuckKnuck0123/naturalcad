# NaturalCAD Beta Handoff (Noah)

This is the short list of things only Noah can do to take the beta live.
Everything else (code, env templates, deploy scripts, smoke test, docs) is
already in the repo.

## What Leeroy already wired up

- `apps/web/.env.example` — Vercel server-only env contract
- `apps/web/vercel.json` — Vercel framework + region config
- `apps/backend-api/.env.example` — beta-aware env template including the
  three-layer guest abuse controls and Modal worker URL
- `apps/backend-api/Dockerfile` — production container for the control-plane API
- `apps/backend-api/cloudrun.env.yaml.example` — Cloud Run env template
- `scripts/deploy-modal-worker.sh` — deploys `apps/cad-worker/main.py` into the
  existing Modal app `naturalcad`
- `scripts/deploy-cloud-run-backend.sh` — deploys the control-plane API to
  Cloud Run from `apps/backend-api`
- `scripts/check-beta-readiness.sh` — local handoff checker for required files,
  account CLIs, Cloud Run env, and smoke-test env
- `scripts/apply-supabase-migrations.sh` — applies the v1 domain schema against
  the existing Supabase project
- `scripts/smoke-beta.sh` — hosted end-to-end smoke that mirrors what the
  Vercel frontend does (guest session -> project -> generation -> poll)
- `docs/beta-deployment.md` — full hosted-path story, updated to reflect that
  Modal, Supabase, and OpenRouter are inherited from the HF/alpha track
- `docs/prompt-processing-architecture.md` — architecture + beta posture
- Backend code:
  - per-project generation cap
  - per-project token cap based on real worker telemetry
  - cross-project request/window cap keyed to the guest session
  - cheaper vision-summary lane for image-guided iteration

## What only you can do

These all require your accounts, keys, or DNS.

0. **Readiness check**
   - Run:
     ```bash
     npm run beta:check
     ```
   - It should report the same account-side blockers listed below. After you
     fill `apps/backend-api/cloudrun.env.yaml` and set smoke-test envs, it
     should stop reporting required missing items.

1. **Modal**
   - From a shell with `modal token new` already authenticated:
     ```bash
     ./scripts/deploy-modal-worker.sh
     ```
   - Copy the `generate_cad_endpoint` URL Modal prints.
   - Confirm the existing Modal secrets are present and current:
     - `openrouter-secret` (with `OPENROUTER_API_KEY`)
     - `supabase-secret` (with `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
       `SUPABASE_BUCKET=naturalCAD-artifacts`)
     - `naturalcad-api-key` (with `NATURALCAD_API_KEY` matching what you will
       set as `API_SHARED_SECRET`)

2. **Supabase**
   - In Supabase Studio, grab the project's Postgres connection string from
     Project Settings > Database.
   - Apply the v1 domain migrations:
     ```bash
     SUPABASE_DB_URL='postgresql://...' ./scripts/apply-supabase-migrations.sh
     ```
   - In Supabase Studio > Storage, create a **private** bucket named
     `naturalcad-source-images`.

3. **Backend API host**
   - Recommended path: Cloud Run.
   - Copy `apps/backend-api/cloudrun.env.yaml.example` to
     `apps/backend-api/cloudrun.env.yaml`.
   - Fill in the real values, especially:
     - `API_SHARED_SECRET` (random string; remember this value)
     - `NATURALCAD_CAD_WORKER_URL` = the Modal endpoint URL from step 1
     - `NATURALCAD_CAD_WORKER_API_KEY` = same value as the Modal
       `naturalcad-api-key` secret
     - `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`
     - `NATURALCAD_SOURCE_IMAGE_BUCKET=naturalcad-source-images`
     - `NATURALCAD_ALLOWED_ORIGINS=https://beta.naturalcad.example` (and any
       other browser origin you actually use)
     - Guest caps per `docs/beta-deployment.md` §5
   - Deploy:
     ```bash
     GCP_PROJECT_ID=<project-id> \
     CLOUD_RUN_REGION=us-west1 \
     CLOUD_RUN_ENV_FILE=apps/backend-api/cloudrun.env.yaml \
     npm run beta:deploy-backend
     ```
   - Copy the service URL printed by the script.
   - Confirm `GET /v1/health` returns ok.

4. **Vercel (apps/web)**
   - Connect this repo to a Vercel project rooted at `apps/web`.
   - In Vercel project settings, set:
     - `NATURALCAD_BACKEND_URL` = the backend host URL (no trailing slash)
     - `NATURALCAD_API_KEY` = same value as backend `API_SHARED_SECRET`
   - Both must be **server-only** (no `NEXT_PUBLIC_` prefix).
   - Deploy.

5. **Cloudflare / DNS**
   - Add the beta hostname to Cloudflare DNS, CNAME to Vercel target.
   - Confirm TLS end to end.
   - Optionally turn on Bot Fight Mode / a basic WAF rule for the beta host.

6. **Smoke**
   ```bash
   BETA_API_BASE=https://api.beta.naturalcad.example \
   BETA_API_KEY=*** API_SHARED_SECRET> \
   ./scripts/smoke-beta.sh
   ```
   You should see: health ok -> guest session created -> project created ->
   generation started -> final status logged. If anything fails, the script
   prints the failing step.

## Order matters

0. `npm run beta:check` to see what is still missing locally.
1. Modal worker first (gives you the endpoint URL).
2. Supabase migrations + new bucket (gives the backend a real DB).
3. Backend API on Cloud Run (consumes Modal URL + Supabase).
4. Vercel frontend (consumes backend URL).
5. Cloudflare hostname (consumes Vercel).
6. Smoke.

## If something breaks

See `docs/beta-deployment.md` §9 for kill switches:
- throttle guests via `NATURALCAD_GUEST_RUNS_PER_WINDOW`
- read-only beta via `NATURALCAD_GUEST_PROJECT_GENERATION_CAP=1`
- disable real generation by unsetting `NATURALCAD_CAD_WORKER_URL`
- rotate `API_SHARED_SECRET` to break frontend-backend trust until redeploy
