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
- Run build123d geometry and see a GLB preview in the browser
- Download STL and STEP exports
- Upload generated STL/STEP artifacts to backend storage when backend is configured
- View backend + execution logs
- Lightweight run logging for MVP testing data (`artifacts/logs/runs.jsonl`)

## Run locally

From the repo root, the easiest path is:

```bash
npm run backend:local
npm run frontend:local
```

Those commands use:
- `scripts/run-local-backend.sh`
- `scripts/run-local-frontend.sh`

Frontend notes:
- local Gradio dev needs Python 3.10-3.13 because `build123d` does not currently publish wheels for Python 3.14+
- by default the frontend helper uses `~/.openclaw/workspace/.venvs/cadrender312`
- it defaults `NATURALCAD_BACKEND_URL` to `http://127.0.0.1:8010`
- if `apps/backend-api/.env` exists, it reuses `API_SHARED_SECRET` as `NATURALCAD_API_KEY`
- override with `NATURALCAD_FRONTEND_VENV=/path/to/venv` if needed

Manual fallback:

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
- `NATURALCAD_BACKEND_URL` (leave unset for a pure Space-only MVP, or set it to enable backend-assisted spec generation + artifact upload)
- `NATURALCAD_API_KEY`
- `NATURALCAD_BACKEND_TIMEOUT` (default `4` seconds)
- `NATURALCAD_SHOW_CODE` (default `false`; set `true` to show generated build123d code in UI logs)
- `BUILD123D_PYTHON` (defaults to the current Python runtime, which is better for Hugging Face Space deployment)

When backend is enabled and returns a `job.id`, the app will POST STL/STEP files to:
- `POST /v1/jobs/{job_id}/artifacts`

Runtime artifacts:
- latest files in `artifacts/` (`model.glb`, `model.stl`, `model.step`)
- archived runs in `artifacts/runs/` (GLB preview is ephemeral and regenerated locally)
- lightweight run logs in `artifacts/logs/runs.jsonl`

Open http://localhost:7860
