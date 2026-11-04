# NaturalCAD 2D HF App

Gradio MVP for the Hugging Face 2D drafting lane.

## Product promise

- text prompt, sketch image, or both
- generate a validated, structured 2D drafting scene
- refine the current drawing while preserving stable entity IDs
- preview in-browser
- download DXF and the portable DrawingScene JSON

Short UI note:

> More reference dimensions = more accurate output.

## Current stack

- Gradio for the HF-facing UI
- versioned, UI-free DrawingScene contract in `app/drawing_core.py`
- `ezdxf` for DXF authoring/export
- direct OpenRouter model calls with one selective depth-repair pass for shallow complex concepts
- QCAD as the target validation environment for output quality

## Current MVP behavior

- accepts text prompt
- accepts optional sketch image
- accepts optional reference notes/dimensions
- generates a simple drafting scene with:
  - polylines, circles, arcs, and true obround slots
  - hatch
  - centerline
  - dimensions
  - text
  - leader note
- applies the `NOAH_URIU_2D_V1` layer hierarchy while presenting disciplined white-on-black CAD linework by default
- preserves working colors and black plot styles in the portable scene and DXF metadata
- renders exact deterministic `ezdxf` hatch patterns in the SVG preview, including nested holes
- reports a depth check when a creative concept is too sparse for the requested intent
- limits annotation density and renders aligned dimension bands, CAD ticks, leader arrowheads/landings, and monospaced text knockouts
- writes DXF, SVG, and DrawingScene JSON into `artifacts/runs/`
- logs timestamped run/source/runtime metadata into `artifacts/logs/runs.jsonl`
- visibly labels model output, local demo fallback, and preserved-scene refinement states
- falls back to a local deterministic scene builder if the model call is unavailable
- preserves the prior validated scene when a refinement model call cannot run

## Portable contract

`DrawingScene 1.2` is intentionally independent of Gradio, OpenRouter, and the filesystem. Both the SVG preview and DXF exporter consume the same validated scene.

This is the seam that will later move into the main product:

- main app shared shell: conversation, attachments, history, projects
- 2D workspace: DrawingScene JSON -> 2D preview + DXF/SVG export
- 3D workspace: current part spec -> GLB/STEP/STL pipeline

See `docs/drawing-scene-v1.md`.

## Environment

- `OPENROUTER_API_KEY` - required for live model calls
- `NATURALCAD_2D_MODEL` - optional model override for this app
- `OPENROUTER_MODEL` - fallback model id if `NATURALCAD_2D_MODEL` is unset
- `OPENROUTER_REFERER` - optional OpenRouter header
- `OPENROUTER_TITLE` - optional OpenRouter header/title
- `NATURALCAD_2D_MAX_PASSES` - `1` or `2`; defaults to `2`, but the second pass runs only when an initial creative concept fails the depth gate

This branch is intentionally narrower than the main NaturalCAD 3D product lane.

## Run locally

From the repo root:

```bash
npm run frontend:local
```

The helper script prefers a repo-local `.venv`, creates it automatically if needed, and still accepts `NATURALCAD_FRONTEND_VENV=/path/to/venv` if you want to override the environment path.

Manual fallback:

```bash
pip install -r requirements.txt
python app.py
```

Open `http://localhost:7860`.

## Next implementation targets

- exercise live text/image/refinement calls with `OPENROUTER_API_KEY`
- run the three fixture prompts through QCAD and record output issues
- add feedback controls and artifact-retention cleanup before public traffic
- add the backend 2D worker adapter, then merge a 2D/3D workspace switcher into `apps/web`
