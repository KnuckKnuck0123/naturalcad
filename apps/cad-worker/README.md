# NaturalCAD Modal Worker

## Setup

1. Install Modal CLI:
```bash
pip install modal
```

2. Set your API key:
```bash
modal token set YOUR_API_KEY
```

## Running Locally

```bash
cd apps/cad-worker
modal run main.py
```

## Deploying

```bash
modal deploy main
```

## Environment Variables Needed

Set these as Modal secrets/env vars:

```
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=openai/gpt-4o-mini  # or any OpenRouter model id you want
NATURALCAD_SPEC_MODEL=google/gemini-2.5-pro  # vision-capable spec resolver
NATURALCAD_CAD_MODEL=anthropic/claude-sonnet-4
OPENROUTER_API_URL=https://openrouter.ai/api/v1/chat/completions  # optional override
OPENROUTER_REFERER=https://huggingface.co/spaces/noahtheboa/naturalcad  # optional
OPENROUTER_TITLE=NaturalCAD  # optional
NATURALCAD_LOG_CODE=false  # optional, default false
NATURALCAD_INCLUDE_CODE_IN_RESPONSE=false  # optional, default false
NATURALCAD_STORE_CODE=true  # optional, default true (stores generated code in DB)
NATURALCAD_STORE_GLB=false  # optional, default false (skip GLB upload to storage)
NATURALCAD_VERBOSE_LOGS=false  # optional, default false (only error logging)
```

Also required for uploads/logging:

```
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_BUCKET=naturalCAD-artifacts
```

## Architecture

```
Project message + sanitized references
    → vision model resolves a validated spec
    → CAD model generates build123d code from the spec
    → no-secret Modal executor validates and runs code
    → trusted publisher stores GLB/STL/STEP artifacts
```

The executor has no attached OpenRouter or Supabase secrets and blocks network
access. Reference-image text is explicitly treated as untrusted data.

*Created 2026-04-12*
