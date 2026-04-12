# NaturalCAD Backend API

FastAPI backend for NaturalCAD.

## Purpose
- keep secrets off the Hugging Face Space
- validate and rate-limit public requests
- create jobs and track status
- generate structured CAD specs
- provide a clean place for worker, DB, and storage integration

## Run locally

```bash
cd apps/backend-api
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8010
```

## Initial endpoints
- `GET /v1/health`
- `POST /v1/jobs`
- `GET /v1/jobs/{job_id}`
- `POST /v1/generate-spec`
- `POST /v1/jobs/{job_id}/artifacts` (multipart upload: `kind` + `file`)

## Current integration state
- `apps/gradio-demo` now creates backend jobs through `POST /v1/jobs`
- the backend currently returns a validated compositional in-memory spec (v1.1 semantic shape)
- the Gradio app still performs local build123d execution for now
- next step is moving execution from the Gradio app into a real worker
- backend models now include an early **compositional spec v1.1** shape for the next generation stage, so model output is not forced into a rigid family-first schema too early

See also:
- `docs/compositional-spec-v1.1.md`

## Notes
This is the v0 scaffold. It currently uses in-memory storage by default, but now includes a Postgres schema and a repository layer that can switch to `DATABASE_URL` when Supabase is ready.

## Supabase readiness
- schema file: `db/schema.sql`
- env placeholders added for `DATABASE_URL` and Supabase keys
- repository layer falls back to memory until the database is configured
- artifact uploads now write to Supabase Storage when these env vars are set:
  - `SUPABASE_URL`
  - `SUPABASE_SERVICE_ROLE_KEY`
  - `SUPABASE_BUCKET`
  - optional: `STORAGE_MAX_UPLOAD_BYTES`

## Fly.io deployment notes
- backend app can be deployed directly from `apps/backend-api`
- internal service port should be `8000`
- backend Docker image should start with `uvicorn`, not `fastapi run`
- recommended startup command is already baked into `apps/backend-api/Dockerfile`
- Hugging Face Space should call this backend via:
  - variable: `NATURALCAD_BACKEND_URL`
  - secret: `NATURALCAD_API_KEY`
- backend should keep the matching value in `API_SHARED_SECRET`

### Suggested setup order
1. Create Supabase project
2. Run `db/schema.sql` in SQL editor
3. Create Storage bucket (default: `naturalCAD-artifacts` if matching the current deployed config)
4. Add backend env vars and restart API
5. Deploy backend host (Fly.io is the current path)
6. Wire Hugging Face Space env vars and rebuild
7. Confirm Gradio app calls `/v1/jobs/{job_id}/artifacts` after STL/STEP export
