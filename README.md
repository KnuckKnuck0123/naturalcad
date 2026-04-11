---
title: NaturalCAD
emoji: 🧱
colorFrom: slate
colorTo: blue
sdk: gradio
sdk_version: 4.44.1
app_file: app.py
pinned: false
---

# NaturalCAD

NaturalCAD is a public prompt-to-CAD demo built around build123d.

The immediate goal is simple: get it in front of people fast, learn from real prompts, and improve from actual usage instead of guessing in a vacuum.

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

```bash
pip install -r requirements.txt
python app.py
```

## Deployment posture

Right now the priority is a lean Hugging Face Space MVP.
If the CAD dependency stack or runtime limits become painful, the frontend can stay on Hugging Face while execution moves to a container or VM later.

## Key docs

- `docs/hf-space-mvp.md`
- `docs/hf-space-deploy-checklist.md`
- `docs/publish-checklist.md`
- `docs/backend-v0.md`
- `docs/security-policy-v0.md`
