---
title: NaturalCAD
emoji: 🍃
colorFrom: gray
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

## Open-source alpha (BYO APIs)

This repo is open so anyone can run the alpha with their own API keys and backend endpoint.

- Bring your own model/API keys
- Run locally or self-host
- Swap providers without changing the frontend UX

If you just want the hosted demo, use the public Space below. If you want control, fork this repo and wire your own secrets.

## Use it

- Try the public alpha app: https://huggingface.co/spaces/kNOWare/naturalcad
- Use this repo if you want to run locally, self-host, or modify the stack

Quick BYO setup:

1. Run frontend locally:
   ```bash
   npm run frontend:local
   ```
2. Point it to your backend:
   - `NATURALCAD_BACKEND_URL`
3. If your backend is protected, set:
   - `NATURALCAD_API_KEY`
4. On the backend side, provide your own:
   - `OPENROUTER_API_KEY` (or your chosen model provider key)
   - Supabase credentials for storage/logging (optional but recommended)

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

- `apps/cad-worker` - Modal worker for LLM + build123d execution
- `apps/web-visualizer` - earlier React/Vite prototype
- `docs/` - product and deployment planning
- `archive/` - older or superseded material kept for reference (includes legacy backend)

## Local run

Simplest path:

```bash
npm run frontend:local
```

That runs the Gradio app and points to `NATURALCAD_BACKEND_URL`.

Optional local backend (legacy) for contract testing:

```bash
npm run backend:local
```

That uses the repo helper scripts:
- `scripts/run-local-backend.sh`
- `scripts/run-local-frontend.sh`

Notes:
- frontend local dev needs Python 3.10-3.13 because `build123d` does not currently publish wheels for Python 3.14+
- the frontend helper expects a working Python venv; default path is `~/.openclaw/workspace/.venvs/cadrender312`
- for hosted testing, set `NATURALCAD_BACKEND_URL` to the Modal endpoint
- if `NATURALCAD_BACKEND_URL` is unset, the helper defaults to `http://127.0.0.1:8010`
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
- Modal worker = prompt validation, auth/rate-limit gates, OpenRouter inference, build123d execution
- Supabase = Postgres + artifact storage
- OpenRouter = swappable model provider layer

If the CAD dependency stack or runtime limits become painful, the frontend can stay on Hugging Face while execution moves further toward a worker/container architecture later.

### Hosted env wiring

Hugging Face Space:
- variable: `NATURALCAD_BACKEND_URL`
- secret: `NATURALCAD_API_KEY`

Backend:
- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL` (optional, default set in worker)
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_BUCKET`
- `NATURALCAD_API_KEY`

## Safer GitHub push workflow

Before any push, run:

```bash
./scripts/prepush-check.sh
```

See `docs/github-push-safety.md` for the full branch and review policy.

## Key docs

- `docs/hf-space-mvp.md`
- `docs/hf-space-deploy-checklist.md`
- `docs/startup-shutdown-playbook.md`
- `docs/publish-checklist.md`
- `docs/backend-v0.md`
- `docs/security-policy-v0.md`
- `docs/engine-assembly-milestone.md`
