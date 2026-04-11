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

## Current integration state
- `apps/gradio-demo` now creates backend jobs through `POST /v1/jobs`
- the backend currently returns a validated in-memory spec
- the Gradio app still performs local build123d execution for now
- next step is moving execution from the Gradio app into a real worker

## Notes
This is the v0 scaffold. It currently uses in-memory storage by default, but now includes a Postgres schema and a repository layer that can switch to `DATABASE_URL` when Supabase is ready.

## Supabase readiness
- schema file: `db/schema.sql`
- env placeholders added for `DATABASE_URL` and Supabase keys
- repository layer falls back to memory until the database is configured
