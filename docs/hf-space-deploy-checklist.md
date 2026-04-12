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
- current recommended host: Fly.io
- current recommended backend port: `8000`
- backend should expose `GET /v1/health`, `POST /v1/generate-spec`, `POST /v1/jobs`, and `POST /v1/jobs/{job_id}/artifacts`

Runtime note:
- the Space Docker image must include the native stack needed by `build123d` / `OCP`
- current Dockerfile uses a conda-forge-native base image (`condaforge/miniforge3`) and strict `conda-forge` channel priority to avoid ABI mismatches between `defaults` and `conda-forge`
- current Dockerfile installs `ocp=7.8.1` in the Conda env and avoids a separate explicit `vtk` pin, because that introduced ABI mismatch symptoms in the Space runtime
- current Dockerfile also exports `LD_LIBRARY_PATH=/opt/conda/envs/cad/lib:$LD_LIBRARY_PATH` so the runtime can actually find the native shared libraries during `build123d` execution
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
