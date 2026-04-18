# NaturalCAD Hugging Face Space Deploy Checklist

## Minimum checklist

- [ ] Gradio app runs cleanly from `apps/gradio-demo/app/main.py`
- [ ] `requirements.txt` contains everything needed for Space runtime, including `build123d`
- [ ] prompt-to-model flow works without requiring local-only paths that break in Space
- [ ] example prompts produce valid outputs
- [ ] timeouts are in place
- [ ] artifacts are bounded and not unbounded temp junk
- [ ] lightweight run logging is enabled
- [ ] README explains local run and Space intent clearly

## MVP notes

For public testing, the demo should degrade gracefully.
If the backend is unavailable, the app should still be able to produce a simple local fallback result rather than fully dying.

For the lean MVP, backend use should be optional, not assumed. If `NATURALCAD_BACKEND_URL` is unset, the Space should stay usable without waiting on a dead localhost request.

If the Hugging Face Space runtime cannot support the CAD dependency stack cleanly, keep the Space as the frontend and offload execution to a container or VM.

## Current hosted setup

Space env:
- variable: `NATURALCAD_BACKEND_URL`
- secret: `NATURALCAD_API_KEY`

Backend host:
- current recommended host: Modal web endpoint (`generate_cad_endpoint`)
- endpoint method: `POST /`
- backend requires header `x-api-key: <NATURALCAD_API_KEY>`
- response should include `job_id`, `generated_code`, and artifact `urls`

Worker env/secrets:
- `OPENROUTER_API_KEY`
- `OPENROUTER_MODEL` (optional)
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_BUCKET`
- `NATURALCAD_API_KEY`

Runtime note:
- the Space Docker image must include the native stack needed by `build123d` / `OCP`
- final stabilization attempt uses a pure `python:3.10-slim` + `pip` runtime instead of the mixed Conda/OCP path
- the goal is to let `build123d` resolve one coherent wheel stack directly, instead of mixing `conda` native packages with `pip` Python packages
- current Dockerfile includes a `build123d` import smoke test during image build so broken native combinations fail earlier

## Data to capture

- timestamp
- run id
- prompt
- mode
- output type
- geometry family
- backend available or not
- success or failure
- runtime seconds
- error string if any

## Security checks before publish

- [ ] `NATURALCAD_API_KEY` is set on Space and Modal
- [ ] backend endpoint rejects requests without `x-api-key`
- [ ] rate limiting is active (IP + key)
- [ ] prompt length caps enforced
- [ ] generated code safety guard enabled
- [ ] no tracked `artifacts/logs/*.jsonl`
