# NaturalCAD Hugging Face Space MVP

## Goal

Ship NaturalCAD quickly as a public testable demo.

Primary goals:
- get real users testing the interaction
- collect prompt/result data
- learn what people actually want
- defer heavier backend infrastructure until the product proves itself

## Product strategy

This MVP is intentionally simple.

NaturalCAD v0 should be:
- a Hugging Face Space
- a Gradio app
- a prompt-to-geometry demo
- a data-gathering surface

It should not yet be:
- a full distributed backend system
- a polished production SaaS
- a heavily abstracted multi-service platform

## What we keep now

- `apps/gradio-demo`
- prompt input
- stub/backend-assisted spec generation if useful
- build123d execution path
- STL preview
- STL and STEP downloads
- lightweight run logging
- examples and clean presentation

## What we defer

- Fly.io deployment
- Supabase integration
- hosted object storage
- worker separation
- full job queue
- advanced auth system
- fine-grained persistence and audit pipeline

## Minimal requirements before public testing

1. The Space must run reliably
2. The demo must generate models from prompts
3. The UI must be clear and attractive enough for strangers to try
4. We should capture lightweight feedback and run metadata
5. We should avoid obvious abuse vectors where possible

## Recommended lightweight data capture

For each run, capture only what helps learning:
- timestamp
- prompt
- mode
- output type
- inferred geometry family
- success or failure
- runtime duration
- optional notes or error string

This can begin as flat-file logging inside the Space or another lightweight mechanism, then migrate later.

## Security posture for MVP

Keep it simple:
- no public arbitrary code input
- prompt input only
- keep prompts length-limited
- keep timeouts in place
- keep generated artifacts bounded
- do not expose secrets in frontend code

This is not full production hardening. It is enough to ship a controlled public demo.

## Phase model

### Phase 1
Ship the Hugging Face Space and gather usage.

### Phase 2
If traction appears, add external persistence and better job tracking.

### Phase 3
If usage justifies it, move to hosted backend, storage, scaling, and eventually model fine-tuning.

## Decision

NaturalCAD should optimize for public testing first, and infrastructure maturity second.
