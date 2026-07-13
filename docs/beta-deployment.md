# NaturalCAD Beta Deployment

> Scope: getting NaturalCAD onto a small, controlled, public beta on the current
> stack (Vercel + backend API + Modal CAD worker + Supabase + Cloudflare in
> front). This is **not** a launch doc. It is a hardening + data-collection doc.

## 1. Stack Roles

- **Vercel** — hosts `apps/web` (Next.js). Frontend delivery only.
- **Backend API (`apps/backend-api`)** — control plane. Auth, sessions, projects,
  quotas, generation orchestration, prompt processing, Supabase persistence,
  worker dispatch. Default beta host: Cloud Run.
- **Modal CAD worker (`apps/cad-worker`)** — heavy CAD execution, vision summary
  lane, spec merge, model calls, artifact production.
- **Supabase** — sessions, projects, versions, runs, attachments, artifacts.
- **Cloudflare** — domain, edge, TLS, and (later) WAF / rate-limit assist.

The frontend never talks to Modal directly. The frontend never talks to model
providers directly. All traffic goes:

```
browser -> Vercel (Next.js) -> Backend API -> Modal worker -> model providers
                                          -> Supabase
```

## 1.5 Inherited Infrastructure (from the HF/alpha track)

NaturalCAD already runs a production alpha on the `huggingface` branch. The new
beta does **not** stand up Modal, Supabase, or OpenRouter from zero. Those are
reused:

- **Modal app**: `modal.App("naturalcad")` already exists. `main`'s
  `apps/cad-worker/main.py` targets the same app, so `modal deploy` just
  publishes the new revision.
- **Modal secrets**: `openrouter-secret`, `supabase-secret`,
  `naturalcad-api-key` are already created and the new worker reads exactly
  those names.
- **Supabase project**: the alpha already provides `SUPABASE_URL`,
  `SUPABASE_SERVICE_ROLE_KEY`, and the artifacts bucket
  `naturalCAD-artifacts` used by the worker.
- **OpenRouter key**: already wired into the worker through
  `openrouter-secret`.

What the beta **adds on top of** that inherited stack:

- a separate Supabase bucket `naturalcad-source-images` for the new
  image-iteration lane (so beta does not pollute the alpha's
  `naturalCAD-artifacts`)
- the v1 domain schema migrations
  (`20260424_000001_domain_v1.sql`, `20260621_000002_iterative_generation.sql`)
- a hosted **backend API** for the domain control plane
- a Vercel-hosted `apps/web` frontend
- a Cloudflare beta hostname

Leaving the HF Space and the alpha worker revision alone is intentional: that
flow stays up while the beta lights up beside it.

## 2. Beta Goals

1. Collect real prompts and iteration traces.
2. Observe failure modes (parsing, spec drift, dimension errors, model timeouts).
3. Confirm that the new iteration-memory architecture actually carries forward
   constraints across turns.
4. Confirm that image-guided iteration is useful at a cost we can sustain.
5. Validate that guest abuse controls hold up under realistic spam.

This is not about polish. This is about learning.

## 3. Pre-flight Checklist

A small beta should not go live until all of these are true.

### 3.1 Frontend (Vercel / `apps/web`)
- [ ] `npm run web:typecheck` clean
- [ ] `npm run web:build` clean
- [ ] Mode switcher (`Fast / Balanced / Quality`) reachable
- [ ] Workspace sidebar surfaces spec, iteration memory, carried constraints,
      unresolved questions
- [ ] Viewer controls (spin/refit/tone) work on hosted build
- [ ] `NEXT_PUBLIC_*` envs only contain values safe to expose

### 3.2 Backend API (`apps/backend-api`)
- [ ] `pytest` clean (currently 24 passed)
- [ ] `API_SHARED_SECRET` set in hosted environment
- [ ] `NATURALCAD_ALLOWED_ORIGINS` lists every browser origin we expect
- [ ] Supabase env vars set (or explicit decision to run in-memory for the beta)
- [ ] Guest quotas tuned (see §5)
- [ ] Logs go somewhere we can actually read

### 3.3 CAD Worker (`apps/cad-worker`)
- [ ] Reachable from backend with `NATURALCAD_CAD_WORKER_URL` + key
- [ ] Vision summary lane uses cheaper model than spec/CAD lane
- [ ] Spec merge carries `iteration_memory` and feature/constraint structure
- [ ] Token telemetry returned to backend so per-project token caps mean something

### 3.4 Supabase
- [ ] `naturalcad-source-images` bucket created and access-controlled
- [ ] Tables and policies in place for projects/runs/versions/messages/attachments
- [ ] Service role key lives only on the backend, never in the browser

### 3.5 Cloudflare / Domain
- [ ] DNS for the beta hostname points at Vercel
- [ ] TLS confirmed end to end
- [ ] Optional: WAF / bot fight mode on for the beta hostname

## 4. Required Environment Variables

### Backend API
```
NATURALCAD_ENV=beta
API_SHARED_SECRET=<long random>
NATURALCAD_CAD_WORKER_URL=https://<modal-endpoint>
NATURALCAD_CAD_WORKER_API_KEY=<modal key>
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service role>
NATURALCAD_SOURCE_IMAGE_BUCKET=naturalcad-source-images
NATURALCAD_ALLOWED_ORIGINS=https://beta.naturalcad.example,https://naturalcad.example
NATURALCAD_RATE_WINDOW_SECONDS=3600
NATURALCAD_GUEST_RUNS_PER_WINDOW=20
NATURALCAD_SIGNED_RUNS_PER_WINDOW=200
NATURALCAD_GUEST_PROJECT_GENERATION_CAP=10
NATURALCAD_GUEST_PROJECT_TOKEN_CAP=120000
NATURALCAD_MAX_GUEST_ATTACHMENTS=3
NATURALCAD_MODE_FAST=openai/gpt-4o-mini
NATURALCAD_MODE_BALANCED=google/gemini-2.5-pro
NATURALCAD_MODE_QUALITY=anthropic/claude-sonnet-4
NATURALCAD_VISION_MODEL=google/gemini-2.5-flash
NATURALCAD_CAD_MODEL=anthropic/claude-sonnet-4
NATURALCAD_VISION_SUMMARY_MAX_TOKENS=220
```

For Cloud Run, copy `apps/backend-api/cloudrun.env.yaml.example` to
`apps/backend-api/cloudrun.env.yaml`, fill it with the real values, and deploy
with:

```bash
GCP_PROJECT_ID=<project-id> \
CLOUD_RUN_REGION=us-west1 \
CLOUD_RUN_ENV_FILE=apps/backend-api/cloudrun.env.yaml \
npm run beta:deploy-backend
```

The backend image is defined in `apps/backend-api/Dockerfile`. It listens on
`0.0.0.0:$PORT`, which is required by Cloud Run.

### Frontend (Vercel)
```
NEXT_PUBLIC_API_BASE_URL=https://api.beta.naturalcad.example
API_SHARED_SECRET=<same as backend>            # server-only, used by route handlers
```

`API_SHARED_SECRET` must be configured as a **server-only** env in Vercel, not as
`NEXT_PUBLIC_*`. The browser never sees it.

### Modal CAD worker
```
NATURALCAD_CAD_WORKER_API_KEY=<same as backend>
OPENROUTER_API_KEY=<openrouter key>
```

## 5. Guest Abuse / Cost Controls

NaturalCAD ships guest beta protections in three explicit layers:

1. **Per-project generation cap** — `NATURALCAD_GUEST_PROJECT_GENERATION_CAP`.
   Limits how many *new* generations a single guest project can produce. Set to
   `0` to disable for trusted-internal runs (e.g. Noah's own testing).

2. **Per-project token cap** — `NATURALCAD_GUEST_PROJECT_TOKEN_CAP`. Aggregates
   real worker telemetry (spec + vision + CAD model calls) so it represents
   actual spend, not just request count.

3. **Cross-project request/window cap** — `NATURALCAD_GUEST_RUNS_PER_WINDOW`
   inside a sliding `NATURALCAD_RATE_WINDOW_SECONDS` window. This is keyed to
   the **guest session**, not the project, so opening many fresh projects from
   the same browser session does not bypass the cap.

### Recommended starting values for public beta
| Setting | Value | Why |
| --- | --- | --- |
| `NATURALCAD_RATE_WINDOW_SECONDS` | `3600` | Rolling hour |
| `NATURALCAD_GUEST_RUNS_PER_WINDOW` | `20` | Anti-project-hopping spam control |
| `NATURALCAD_SIGNED_RUNS_PER_WINDOW` | `200` | Signed users get much more headroom |
| `NATURALCAD_GUEST_PROJECT_GENERATION_CAP` | `10` | Lets a real user iterate, kills a bot |
| `NATURALCAD_GUEST_PROJECT_TOKEN_CAP` | `120000` | Caps real $ cost per guest project |
| `NATURALCAD_MAX_GUEST_ATTACHMENTS` | `3` | Limit image-iteration abuse surface |
| `NATURALCAD_IP_SESSIONS_PER_WINDOW` | `3` | Per-network guest session cap |
| `NATURALCAD_IP_RUNS_PER_WINDOW` | `10` | Per-network generation cap |
| `NATURALCAD_GENERATIONS_DISABLED` | `false` | Kill switch (`true` = pause new gens) |

### Noah's testing override
Per workspace memory: Noah's own testing flows should be effectively unlimited.
For internal testing, point the browser at a backend with:
```
NATURALCAD_GUEST_RUNS_PER_WINDOW=1000000
NATURALCAD_GUEST_PROJECT_GENERATION_CAP=0
NATURALCAD_GUEST_PROJECT_TOKEN_CAP=0
```
or use a signed session.

## 6. Kill Switch

For emergencies, set `NATURALCAD_GENERATIONS_DISABLED=true` on the Cloud Run
service. This returns `503` on `POST /v1/projects/{id}/generations` without
tearing down the rest of the app. To stop spend instantly without a full
deploy, update the env in Google Cloud Console and restart the revision.

## 7. Prompt Poisoning / Injection Hardening

Beta posture, not final.

- **Treat all user prompt + attachment text as untrusted.** Never let prompt
  content escape into system role or tool-permission context inside the worker.
- **Spec layer is a structural firewall.** The backend always converts free
  prompts into a structured spec before the CAD model is allowed to act. The
  CAD model should not receive raw freeform user text without spec wrapping.
- **Image inputs go through the cheaper vision-summary lane first.** That lane
  produces a constrained text summary; the CAD model sees the summary, not
  arbitrary OCR.
- **Reject overlong prompts / attachment payloads at the API boundary.**
- **Strip provider control tokens / role markers** (`<|system|>`, `system:`,
  jailbreak phrasing) defensively from incoming prompt text before forwarding.
- **Log suspicious inputs** for review rather than silently dropping them.

## 7. Telemetry to Capture in Beta

At a minimum:

- prompt text (hashed if PII concerns)
- mode (fast/balanced/quality)
- parsed spec snapshot
- iteration memory snapshot
- worker model used + token counts
- success / failure / timeout
- artifact format produced
- whether the user kept iterating after this turn

This is the data that lets us tune prompt processing and model routing.

## 8. Rollout Order

0. Check local handoff readiness:
   ```bash
   npm run beta:check
   ```
   It should only be blocked by account-side values you still need to fill in.
1. From `main`, deploy the new CAD worker into the existing Modal app:
   ```bash
   ./scripts/deploy-modal-worker.sh
   ```
   Copy the printed `generate_cad_endpoint` URL.
2. Apply v1 domain migrations to the existing Supabase project:
   ```bash
   SUPABASE_DB_URL='postgresql://...' ./scripts/apply-supabase-migrations.sh
   ```
   Then in Supabase Studio, create the **private** storage bucket
   `naturalcad-source-images`.
3. Ship the backend API (`apps/backend-api`) to Cloud Run with beta envs set,
   including `NATURALCAD_CAD_WORKER_URL` from step 1 and the inherited
   `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY`:
   ```bash
   GCP_PROJECT_ID=<project-id> \
   CLOUD_RUN_REGION=us-west1 \
   CLOUD_RUN_ENV_FILE=apps/backend-api/cloudrun.env.yaml \
   npm run beta:deploy-backend
   ```
4. Deploy `apps/web` to Vercel. Set server-only `NATURALCAD_BACKEND_URL`
   and `NATURALCAD_API_KEY` in the Vercel project (matches `API_SHARED_SECRET`
   on the backend).
5. Point the beta hostname at Vercel via Cloudflare and confirm TLS.
6. Smoke test through the backend before opening to anyone:
   ```bash
   BETA_API_BASE=https://api.beta.naturalcad.example \
   BETA_API_KEY=*** API_SHARED_SECRET> \
   ./scripts/smoke-beta.sh
   ```
7. Open to outside testers in small batches; monitor quotas, token spend,
   latency.

## 9. Additional Kill Switches

If something goes wrong in beta:

- Drop `NATURALCAD_GUEST_RUNS_PER_WINDOW` to a very small number to throttle
  guest traffic without taking the site down.
- Set `NATURALCAD_GUEST_PROJECT_GENERATION_CAP=1` to effectively read-only
  guests.
- Unset `NATURALCAD_CAD_WORKER_URL` to disable real generation while keeping the
  product browsable.
- Rotate `API_SHARED_SECRET` to invalidate frontend -> backend trust until the
  frontend redeploys with the new value.
