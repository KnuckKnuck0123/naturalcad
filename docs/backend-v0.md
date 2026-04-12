# NaturalCAD Backend v0

## Goal

Build a low-cost backend for NaturalCAD that is safe enough for an MVP:
- public UI on Hugging Face Spaces
- hosted inference on Hugging Face
- no important execution on Noah's laptop
- no public arbitrary code execution
- logs, metadata, and artifacts stored off-machine

## Guiding priorities

1. Keep costs low
2. Prevent spam and abuse
3. Keep secrets off the frontend
4. Avoid exposing raw Python execution to the public
5. Keep the system simple enough to actually ship

## Recommended stack

### Frontend
- Hugging Face Space
- current Gradio app is the fastest path

### Backend API
- FastAPI deployed on Fly.io
- reason: build123d and worker logic are already Python-adjacent, so this reduces stack complexity while giving us a sturdier app host for API + worker processes

### Inference
- Hugging Face Inference Endpoint or hosted HF model endpoint
- prefer free or low-cost model path for MVP

### Database
- Supabase Postgres
- reason: structured job records, artifact metadata, and status transitions fit naturally in Postgres, and Supabase gives a good hosted dashboard with low MVP friction

### Object storage
- hosted object storage, not local disk
- S3-compatible storage is preferred

### Worker
- isolated Python worker for geometry generation
- build123d execution should happen here, not in the public frontend tier

## Trust boundaries

### Hugging Face Space
Allowed:
- collect prompts
- submit jobs to backend
- display status and results

Not allowed:
- store backend secrets
- directly execute build123d jobs
- write directly to database with privileged credentials
- be the source of truth for rate limiting or audit policy

### Backend API
Responsible for:
- request validation
- rate limiting
- job creation
- inference calls
- schema validation
- queue handoff
- database writes
- artifact metadata
- audit logs

### Worker
Responsible for:
- consuming approved jobs
- generating structured CAD outputs
- optionally translating internal spec to build123d code
- exporting STL/STEP
- uploading artifacts to hosted storage
- updating job status

### Database
Store:
- job records
- prompt text
- derived structured spec
- status transitions
- artifact metadata
- session or user metadata
- audit events
- rate-limit counters if needed

### Object storage
Store:
- STL files
- STEP files
- previews
- log blobs if needed

## Public input model

### Public API rule
Public users submit prompts, not arbitrary code.

That means:
- user sends prompt text
- backend calls model
- model returns structured data or a constrained internal representation
- worker generates geometry from approved internal data

### Internal flexibility
Internally, NaturalCAD may still generate build123d code if that helps implementation.
But code generation should stay behind the backend/worker boundary, not exposed as a public execution surface.

## Job lifecycle

Use these statuses:
- `submitted`
- `validated`
- `queued`
- `running`
- `completed`
- `failed`

Optional later:
- `blocked`
- `expired`
- `canceled`

## Minimal API shape

### `POST /jobs`
Create a job.

Input:
- prompt
- optional session id
- optional client metadata

Server actions:
- validate payload
- apply rate limit
- create job record
- call inference or enqueue pre-inference flow

Returns:
- job id
- status

### `GET /jobs/{job_id}`
Fetch job status.

Returns:
- current status
- error info if failed
- artifact metadata if completed

### `GET /jobs/{job_id}/artifacts`
Return artifact metadata and signed URLs if applicable.

### `GET /health`
Basic health check.

## Suggested Postgres tables

### `jobs`
Columns:
- `id`
- `created_at`
- `updated_at`
- `status`
- `prompt`
- `normalized_prompt`
- `spec_json`
- `error_text`
- `client_session_id`
- `ip_hash`
- `model_info_json`

### `artifacts`
Columns:
- `id`
- `job_id`
- `kind` (`stl`, `step`, `preview`, `log`)
- `storage_key`
- `size_bytes`
- `created_at`
- `expires_at`

### `audit_events`
Columns:
- `id`
- `job_id`
- `event_type`
- `created_at`
- `details_json`

### `rate_limits`
Optional if not handled elsewhere.

## Queue strategy

For MVP, keep it simple.

Options:
1. DB-backed queue with polling
2. lightweight Redis queue later if needed

Recommendation:
- start with a DB-backed queue and one worker
- upgrade only when traffic justifies it

## Low-cost implementation order

### Phase 0
- keep Gradio frontend
- do not deploy public raw code execution

### Phase 1
- create FastAPI service on Fly.io
- add `POST /jobs` and `GET /jobs/{job_id}`
- connect Supabase Postgres
- add simple rate limiting

### Phase 2
- connect HF inference endpoint
- store prompt, status, and response metadata
- validate returned structured output

### Phase 3
- add Python worker
- generate artifacts
- upload artifacts to hosted storage
- return signed artifact links

### Phase 4
- tighten retention, add auth tiers, add cancellation, add preview generation

## Spec direction for the next phase

NaturalCAD should move next toward a **loose compositional / semantic JSON spec** rather than a rigid family-first schema.

Reason:
- rigid family routing too early will bias the model toward repetitive safe defaults
- concept-grade generation needs room for novelty, unexpected topology, and broader prompt coverage
- reuse and dedupe should exist, but as later optimization layers rather than the main creative frame

Recommended next spec target:
- `intent`
- `semantic_part`
- `family_hint` (optional, not dominant)
- `geometry`
- `dimensions`
- `constraints`
- `style`
- `dedupe`

Reference:
- `docs/compositional-spec-v1.1.md`

## What not to do in v0

- no public arbitrary Python execution
- no local laptop as production backend
- no secrets in frontend code
- no unlimited artifact retention
- no complicated microservice split

## Default recommendation

NaturalCAD v0 should ship as:
- Hugging Face Space frontend
- FastAPI backend on Fly.io
- Supabase Postgres
- hosted object storage
- one Python worker
- strict prompt-only public interface
