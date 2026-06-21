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
  <img src="docs/assets/naturalcad-logo-current.jpg" alt="NaturalCAD logo" width="220" />
</p>

**NaturalCAD** is a conversational CAD product built around build123d, with the main product lane now centered on the website frontend in `apps/web`.

The current product direction is:
- a hosted web app with a simple loop: prompt, generate, iterate, export
- a broad text-to-CAD entry point
- growing toward stronger replacement-part reconstruction and fit-driven refinement

## Use it

- Main website/app frontend lives in `apps/web`
- Legacy public Hugging Face demo still exists at: https://huggingface.co/spaces/kNOWare/naturalcad
- Use this repo if you want to run locally, self-host, or continue product development

Current output posture:
- browser preview uses GLB when available
- STEP remains the main CAD handoff artifact
- STL remains available as a mesh export

NaturalCAD is still early, but the real work is no longer just a text-to-CAD toy. The product is being shaped toward useful multi-turn CAD generation and, over time, replacement-part reconstruction.

<p align="center">
  <img src="docs/assets/naturalcad-hero-reference.jpg" alt="NaturalCAD example output" width="680" />
</p>

## Current app path

- `apps/web` - main website + app frontend for the hosted product lane
- `apps/backend-api` - control-plane API for sessions, projects, versions, and iteration
- `apps/cad-worker` - CAD execution worker for LLM + build123d generation

Legacy / older lanes still in the repo:
- `app.py` - Hugging Face Space entrypoint
- `apps/gradio-demo` - older demo-first UI lane
- `apps/web-visualizer` - earlier React/Vite prototype
- `archive/` - older or superseded material kept for reference

## Local run

### Website/frontend lane

1. Verify the website app builds:
   ```bash
   npm run web:typecheck
   npm run web:build
   ```
2. Run local website development:
   ```bash
   npm run web:dev
   ```
3. Point the frontend at the backend with:
   - `NATURALCAD_BACKEND_URL`
4. If the backend is protected, also set:
   - `NATURALCAD_API_KEY`
5. On the backend side, provide:
   - `OPENROUTER_API_KEY`
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
   - `SUPABASE_BUCKET`
   - `NATURALCAD_API_KEY`

### Legacy Gradio demo lane

If you need to run the older Hugging Face/demo-oriented app:

```bash
npm run frontend:local
```

Optional local backend contract test:

```bash
npm run backend:local
```

That uses the helper scripts:
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

The current deployment direction is:
- Vercel for the website/frontend lane
- Modal or equivalent hosted worker for CAD execution
- Supabase for project/session/version data and artifact storage
- Cloudflare in front of the public domain setup

Current recommended shape:
- `apps/web` = public product frontend
- backend API = session/project/version control plane
- CAD worker = build123d generation and artifact production
- Supabase = state + storage
- OpenRouter or equivalent = model provider layer

The Hugging Face app still exists as a legacy demo lane, but it is no longer the main product framing for this repo.

### Hosted env wiring

Frontend:
- `NATURALCAD_BACKEND_URL`
- `NATURALCAD_API_KEY` if the backend is protected

Backend / worker:
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

- `docs/naturalcad-remaining-work.md`
- `docs/sprint-v1-domain-app.md`
- `docs/spec-3d-viewer-v1.md`
- `docs/backend-api-v1.md`
- `docs/startup-shutdown-playbook.md`
- `docs/publish-checklist.md`
- `docs/backend-v0.md`
- `docs/security-policy-v0.md`
- `docs/engine-assembly-milestone.md`

