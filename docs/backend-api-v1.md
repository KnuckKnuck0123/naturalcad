# Backend API v1 (Domain App Control Plane)

This API is the foundation for domain app features while keeping the Hugging Face alpha stable.

## What is implemented now
- Guest session bootstrap (`POST /v1/auth/guest`)
- Model profiles for switcher (`GET /v1/models`)
- Project creation (`POST /v1/projects`)
- Conversational generation scaffold (`POST /v1/projects/{id}/generate`)
- Param slider patch flow (`PATCH /v1/projects/{id}/versions/{version_id}/parameters`)
- Project detail + version history (`GET /v1/projects/{id}`)

## Current storage mode
- In-memory repository (for fast iteration)
- Supabase migration scaffold added: `supabase/migrations/20260424_000001_domain_v1.sql`
- Next step: wire repository methods to Supabase tables

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

## Generation behavior
- If `NATURALCAD_CAD_WORKER_URL` is set, API forwards generation requests to the Modal CAD worker.
- If not set, API returns a mock-success response to unblock frontend integration work.

## Notes
- This is intentionally scaffold-first to enable frontend feature work in parallel with infra setup.
- Hugging Face alpha (`huggingface` branch) is not changed by this API work.
