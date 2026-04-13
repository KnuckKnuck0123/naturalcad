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

Create a `.env` file:
```
OPENAI_API_KEY=sk-...  # If using OpenAI
# Or other LLM key
```

## LLM Configuration

The current code has placeholder LLM logic. To wire up a real model:

1. **Option A: OpenAI** (easiest)
   - Add `openai` to requirements.txt
   - Set `OPENAI_API_KEY`
   
2. **Option B: Modal-hosted model**
   - Reference the model in Modal's model registry
   - Configure in the function

## Architecture

```
User Prompt (HF Space)
    → Modal Function
    → LLM interprets
    → build123d generates STL
    → Returns STL to user
```

*Created 2026-04-12*