# NaturalCAD Hugging Face Space Deploy Checklist

## Minimum checklist

- [ ] Gradio app runs cleanly from `apps/gradio-demo/app/main.py`
- [ ] `requirements.txt` contains everything needed for Space runtime for the 2D lane
- [ ] prompt/image-to-model flow works without requiring local-only paths that break in Space
- [ ] example prompts produce valid outputs
- [ ] timeouts are in place
- [ ] artifacts are bounded and not unbounded temp junk (still open)
- [ ] lightweight run logging is enabled
- [ ] README explains local run and Space intent clearly

## MVP notes

For public testing, the demo should degrade gracefully.
If the model call is unavailable, the app should still be able to produce a simple local fallback drawing rather than fully dying.

For the lean MVP, backend use should be optional, not assumed.
If the Hugging Face Space runtime cannot support the eventual model path cleanly, keep the Space as the frontend and offload only the model call.

## Current hosted setup

Runtime note:
- current branch uses a lighter pure Python 2D stack instead of the older `build123d` Space path
- keep the Space runtime as simple as possible: `gradio`, `ezdxf`, `pillow`, `httpx`
- avoid hidden dependencies on local backend env or CAD-native desktop tooling

Space envs to set:
- `OPENROUTER_API_KEY` as a secret when live model calls should be enabled
- `NATURALCAD_2D_MODEL` as an optional public env override for the 2D drafting model
- `NATURALCAD_2D_MAX_PASSES=2` for a cost-bounded repair pass on shallow creative concepts
- `OPENROUTER_TITLE=NaturalCAD 2D`

## Data to capture

- timestamp
- run id
- prompt length (do not log full private prompt text by default)
- sketch image present or not
- units
- entity counts
- fallback or model-assisted
- success source: model, local demo fallback, or preserved prior scene
- total and model runtime milliseconds
- error string if any

## Security checks before publish

- [ ] any remote model endpoint secret is set on Space
- [ ] any remote model endpoint rejects unauthenticated requests
- [ ] rate limiting is active if/when a remote model path is added
- [x] prompt length caps enforced
- [x] image upload capped at 10 MB
- [x] Gradio queue bounded and concurrency limited
- [ ] no tracked `artifacts/logs/*.jsonl`
