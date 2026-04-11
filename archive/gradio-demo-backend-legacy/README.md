# NaturalCAD Backend Scaffold

Thin private backend for the NaturalCAD Hugging Face Space.

## Purpose
- keep secrets off the Space
- rate limit and cache requests
- normalize prompts
- return structured CAD specs
- leave room for future provider routing

## Run

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8010
```

## Planned flow
1. Space sends prompt to `/v1/generate-spec`
2. Backend validates + rate limits
3. Backend returns structured JSON spec
4. Gradio app converts spec into build123d code
5. Space executes build123d and returns STL/STEP
