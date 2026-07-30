---
title: NaturalCAD 2D
emoji: 🍃
colorFrom: gray
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# NaturalCAD 2D

**NaturalCAD 2D** is the Hugging Face drafting lane for sketch/text to DXF, split apart from the main 3D product work.

The current product direction is:
- a hosted web app with a simple loop: prompt, generate, iterate, export
- a broad text-to-CAD entry point
- growing toward stronger replacement-part reconstruction and fit-driven refinement

## Use it

- Main website/app frontend lives in `apps/web`
- Legacy public Hugging Face demo still exists at: https://huggingface.co/spaces/kNOWare/naturalcad
- Use this repo if you want to run locally, self-host, or continue product development

Current branch split posture:
- `NaturalCAD 3D` stays focused on 3D generation/export in the website lane
- the Hugging Face lane can be narrower and faster
- this branch repurposes the HF app toward `text/sketch -> 2D DXF`

NaturalCAD is still early, but the real work is no longer just a text-to-CAD toy. The product is being shaped toward useful multi-turn CAD generation and, over time, replacement-part reconstruction.

## Current app path

- `apps/web` - main website + app frontend for the hosted product lane
- `apps/backend-api` - control-plane API for sessions, projects, versions, and iteration
- `apps/cad-worker` - CAD execution worker for LLM + build123d generation

Secondary / alternate lanes still in the repo:
- `app.py` - Hugging Face Space entrypoint
- `apps/gradio-demo` - Hugging Face 2D drafting lane on this branch
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

### Hugging Face 2D lane

If you need to run the Hugging Face 2D drafting app:

```bash
npm run frontend:local
```

Helper script:
- `scripts/run-local-frontend.sh`

Notes:
- the frontend helper expects a working Python venv; default path is `~/.openclaw/workspace/.venvs/cadrender312`
- if you want a different frontend venv, set `NATURALCAD_FRONTEND_VENV=/path/to/venv`
- this branch's HF app currently runs as a local DXF generator and previewer without needing the 3D backend path

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

The Hugging Face app is intentionally separate from the main 3D product framing for this repo.

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
