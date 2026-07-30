# NaturalCAD 2D HF App

Gradio MVP for the Hugging Face 2D drafting lane.

## Product promise

- text prompt, sketch image, or both
- generate a simple 2D drafting study
- preview in-browser
- download DXF

Short UI note:

> More reference dimensions = more accurate output.

## Current stack

- Gradio for the HF-facing UI
- internal drafting scene model in `app/main.py`
- `shapely` for geometry-oriented helpers and bounds logic
- `ezdxf` for DXF authoring/export
- direct OpenRouter model calls for the first real drafting pass
- QCAD as the target validation environment for output quality

## Current MVP behavior

- accepts text prompt
- accepts optional sketch image
- accepts optional reference notes/dimensions
- generates a simple drafting scene with:
  - geometry
  - hatch
  - centerline
  - dimensions
  - text
  - leader note
- writes DXF into `artifacts/runs/`
- logs lightweight run metadata into `artifacts/logs/runs.jsonl`
- falls back to a local deterministic scene builder if the model call is unavailable

## Environment

- `OPENROUTER_API_KEY` - required for live model calls
- `NATURALCAD_2D_MODEL` - optional model override for this app
- `OPENROUTER_MODEL` - fallback model id if `NATURALCAD_2D_MODEL` is unset
- `OPENROUTER_REFERER` - optional OpenRouter header
- `OPENROUTER_TITLE` - optional OpenRouter header/title

This branch is intentionally narrower than the main NaturalCAD 3D product lane.

## Run locally

From the repo root:

```bash
npm run frontend:local
```

Manual fallback:

```bash
pip install -r requirements.txt
python app.py
```

Open `http://localhost:7860`.

## Next implementation targets

- replace the current deterministic scene builder with a real model call
- move prompt/image interpretation into a structured drafting scene schema
- improve entity coverage and QCAD validation
- remove DXF positioning from the main 3D product lane
