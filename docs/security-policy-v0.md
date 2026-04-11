# NaturalCAD Security Policy v0

## Goal

Protect the MVP from spam, casual abuse, cost blowups, and unsafe execution.

This policy is intentionally simple. It is meant to be good enough to launch a controlled MVP, not to solve every future security problem.

## Core rules

1. Public users submit prompts, not raw code
2. Every request is validated server-side
3. Every request is rate-limited
4. Every job is logged
5. Geometry execution runs in an isolated worker
6. Artifacts are stored off-machine
7. Secrets never live in the frontend
8. Old artifacts expire automatically

## Threats we care about first

### Spam
Risk:
- repeated submissions
- queue flooding
- scripted abuse

Controls:
- per-IP rate limit
- per-session rate limit
- max prompt length
- max jobs per hour
- optional cooldown after repeated failures

### Unsafe execution
Risk:
- arbitrary code execution
- prompt output leading to unsafe Python generation

Controls:
- public API accepts prompts only
- model output must pass schema validation
- worker runs in isolated environment
- job timeout enforced
- memory and disk limits enforced where possible

### Storage abuse
Risk:
- giant artifacts
- too many retained runs
- disk growth

Controls:
- max artifact size
- max artifacts per job
- retention window
- deletion policy for expired outputs

### Secret leakage
Risk:
- exposing credentials in Space frontend or repo

Controls:
- secrets only in backend environment
- no privileged DB or storage credentials in public UI
- use server-generated access URLs when needed

## Required limits for v0

### Request limits
- max prompt length: 1000 to 2000 chars
- max jobs per minute per IP: low
- max jobs per hour per session: capped
- reject oversized payloads

### Execution limits
- max worker runtime per job
- max exported artifact count
- max artifact size
- max queue depth before temporary rejection

### Retention limits
- artifact expiration window
- log retention window
- optional purge job for expired runs

## Authentication model

For MVP, choose one of these:

### Option A, easiest
- public anonymous access
- strict rate limiting
- lowest cost and simplest onboarding

### Option B, safer
- anonymous low-tier access
- signed session token from backend
- optional authenticated users later for higher limits

Recommended MVP choice:
- start with Option A plus strong rate limits
- add sign-in only if abuse appears

## Data handling rules

### Store in database
- prompt
- normalized prompt if used
- job status
- model used
- timestamps
- failure reason
- artifact references
- anonymized client metadata

### Store in object storage
- STL
- STEP
- previews
- optional log files

### Never store in frontend
- endpoint secrets
- DB credentials
- storage keys
- worker credentials

## Worker isolation expectations

The worker should:
- run separately from the public web tier
- have minimal permissions
- use temporary local working files only
- upload final artifacts to hosted storage
- avoid broad access to the rest of the system

## Abuse response policy

If abuse is detected:
1. tighten rate limits
2. temporarily disable anonymous submissions if needed
3. purge abusive artifacts
4. rotate credentials if exposure is suspected
5. review logs and affected jobs

## MVP launch checklist

- [ ] Prompt-only public interface
- [ ] Server-side validation
- [ ] Rate limiting enabled
- [ ] Secrets stored server-side only
- [ ] Worker timeout enabled
- [ ] Hosted DB connected
- [ ] Hosted storage connected
- [ ] Artifact retention policy defined
- [ ] Audit logging enabled
- [ ] No laptop in production path

## Security posture summary

NaturalCAD v0 should be treated as a controlled public MVP.
It should be easy to use, but intentionally constrained.
The goal is not maximum openness. The goal is safe iteration.
