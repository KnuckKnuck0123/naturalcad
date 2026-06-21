# Backend API v1 (Domain App Control Plane)

This API is the foundation for domain app features while keeping the Hugging Face alpha stable.

## What is implemented now
- Guest session bootstrap (`POST /v1/auth/guest`)
- Signed user session bootstrap from Supabase token (`POST /v1/auth/session`)
- Model profiles for switcher (`GET /v1/models`)
- Project creation (`POST /v1/projects`)
- Conversational generation scaffold (`POST /v1/projects/{id}/generate`)
  - supports optional `image_urls` references for guided generations
- Param slider patch flow (`PATCH /v1/projects/{id}/versions/{version_id}/parameters`)
- Project detail + version history (`GET /v1/projects/{id}`)
- Durable project messages and explicitly branchable immutable versions
- Asynchronous, idempotent generation runs (`POST /v1/projects/{id}/generations`)
- Clarification turns that resume a pending run without creating fake versions
- Private source-image reservation, sanitization, preview, deletion, and expiry
- Two-stage spec resolution followed by spec-to-build123d generation

## Current storage mode
- DB-backed repository is now wired when `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` are set.
- Automatic fallback to in-memory repository when Supabase env vars are unset.
- Supabase migration scaffold: `supabase/migrations/20260424_000001_domain_v1.sql`

## Local run
```bash
npm run backend:local
```

## DB bootstrap (next)
```bash
supabase db push
```

## Required headers
- `x-api-key`: optional when `API_SHARED_SECRET` is empty
- `x-session-id`: required for project and generation routes

## Auth notes
- `POST /v1/auth/session` expects a Supabase access token and returns a NaturalCAD session id.
- This enables non-Google account paths (email/password and magic-link).

## Generation behavior
- The API persists a run and returns `202`; clients poll the run endpoint.
- The worker first resolves a validated structured spec, then generates CAD code from that spec.
- Generated code executes in a separate Modal function with no declared secrets.
- If `NATURALCAD_CAD_WORKER_URL` is unset, deterministic mock responses unblock local frontend work.

## Security boundaries
- Browser traffic uses the same-origin Next.js BFF; gateway secrets never enter the browser bundle.
- The effective guest session is an HttpOnly cookie and is not returned in project payloads.
- Arbitrary remote image URLs are not accepted. Uploads use private, object-scoped signed reservations.
- Uploaded images are decoded, metadata-stripped, resized, and re-encoded before model access.
- Apply `20260621_000002_iterative_generation.sql` before enabling the new endpoints with Supabase.

## Notes
- This is intentionally scaffold-first to enable frontend feature work in parallel with infra setup.
- Hugging Face alpha (`huggingface` branch) is not changed by this API work.
