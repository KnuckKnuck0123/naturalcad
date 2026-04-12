---
title: NaturalCAD
emoji: 🍃
colorFrom: slate
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# NaturalCAD

<p align="center">
  <img src="docs/assets/naturalcad-icon-selected.jpg" alt="NaturalCAD icon" width="220" />
</p>

**NaturalCAD** is a public prompt-to-CAD demo built around build123d.

Current local preview posture:
- browser preview uses GLB when available
- STEP remains the main CAD handoff artifact
- STL remains available as a mesh export

Turn natural-language prompts into quick CAD studies, test the interaction with real users, and learn what deserves to become a bigger product.

<p align="center">
  <img src="docs/assets/naturalcad-hero-reference.jpg" alt="NaturalCAD example output" width="680" />
</p>

## Current app path

- `app.py` - Hugging Face Space entrypoint
- `requirements.txt` - Space runtime dependencies
- `apps/gradio-demo` - primary MVP app

## Other repo areas

- `apps/backend-api` - later-phase backend scaffold if we outgrow a Space-only MVP
- `apps/web-visualizer` - earlier React/Vite prototype
- `docs/` - product and deployment planning
- `archive/` - older or superseded material kept for reference

## Local run

Simplest path:

```bash
npm run backend:local
npm run frontend:local
```

That uses the repo helper scripts:
- `scripts/run-local-backend.sh`
- `scripts/run-local-frontend.sh`

Notes:
- frontend local dev needs Python 3.10-3.13 because `build123d` does not currently publish wheels for Python 3.14+
- by default the frontend helper uses `~/.openclaw/workspace/.venvs/cadrender312`
- the frontend helper defaults `NATURALCAD_BACKEND_URL` to `http://127.0.0.1:8010`
- if `apps/backend-api/.env` exists, the frontend helper also reuses `API_SHARED_SECRET` as `NATURALCAD_API_KEY`
- if you want a different frontend venv, set `NATURALCAD_FRONTEND_VENV=/path/to/venv`

Manual fallback:

```bash
pip install -r requirements.txt
python app.py
```

## Deployment posture

Right now the priority is a lean Hugging Face Space MVP with a separate hosted backend.

Current recommended shape:
- Hugging Face Space = public UI + local preview/runtime
- Fly.io backend = API, auth, rate limiting, job/spec logging, Supabase writes
- Supabase = Postgres + artifact storage
- managed inference endpoint later = swappable model layer behind the backend

If the CAD dependency stack or runtime limits become painful, the frontend can stay on Hugging Face while execution moves further toward a worker/container architecture later.

### Hosted env wiring

Hugging Face Space:
- variable: `NATURALCAD_BACKEND_URL`
- secret: `NATURALCAD_API_KEY`

Backend:
- `DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_BUCKET`
- `API_SHARED_SECRET`

## Key docs

- `docs/hf-space-mvp.md`
- `docs/hf-space-deploy-checklist.md`
- `docs/publish-checklist.md`
- `docs/backend-v0.md`
- `docs/security-policy-v0.md`
