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
