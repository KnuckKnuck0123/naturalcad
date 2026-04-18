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
OPENROUTER_API_URL=https://openrouter.ai/api/v1/chat/completions  # optional override
OPENROUTER_REFERER=https://huggingface.co/spaces/noahtheboa/naturalcad  # optional
OPENROUTER_TITLE=NaturalCAD  # optional
NATURALCAD_LOG_CODE=false  # optional, default false
NATURALCAD_INCLUDE_CODE_IN_RESPONSE=false  # optional, default false
```

Also required for uploads/logging:

```
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_BUCKET=naturalCAD-artifacts
```

## Architecture

```
User Prompt (HF Space)
    → Modal Function
    → LLM interprets
    → build123d generates STL
    → Returns STL to user
```

*Created 2026-04-12*
