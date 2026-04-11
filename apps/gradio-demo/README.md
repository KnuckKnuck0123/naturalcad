# NaturalCAD

Gradio prototype for NaturalCAD, a public natural-language CAD modeler built on build123d.

## Purpose

- Fast Hugging Face Spaces deployment
- Test prompt → spec → CAD loop
- Validate interaction model before deeper productization
- Keep the MVP portable enough to offload execution later if Space limits become a problem

## Features

- Prompt-driven model generation through the NaturalCAD backend when available
- Local fallback generation if the backend is unavailable
- Run build123d geometry and see STL preview
- Download STL and STEP exports
- View backend + execution logs
- Lightweight run logging for MVP testing data (`artifacts/logs/runs.jsonl`)

## Run locally

Start the backend first:

```bash
cd ../backend-api
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn app.main:app --reload --port 8010
```

Then run the Gradio app:

```bash
pip install -r requirements.txt
python app/main.py
```

Current Space-oriented dependency note:
- `build123d==0.10.0` is now declared directly in `requirements.txt`
- if Hugging Face Space cannot reliably support the CAD dependency stack, we can keep the UI there and offload execution to a container or VM later without changing the product direction

Optional environment variables:
- `NATURALCAD_BACKEND_URL` (leave unset for a pure Space-only MVP, or set it to enable backend-assisted spec generation)
- `NATURALCAD_API_KEY`
- `NATURALCAD_BACKEND_TIMEOUT` (default `4` seconds)
- `BUILD123D_PYTHON` (defaults to the current Python runtime, which is better for Hugging Face Space deployment)

Runtime artifacts:
- latest files in `artifacts/`
- archived runs in `artifacts/runs/`
- lightweight run logs in `artifacts/logs/runs.jsonl`

Open http://localhost:7860