# NaturalCAD HF Space Notes

## Current intent
- Public-facing NaturalCAD app
- build123d-backed execution loop
- Noah will wire a service endpoint for LLM generation later

## Current prototype state
- Gradio UI
- real build123d execution
- STL preview
- STL + STEP downloads
- starter sample picker
- prompt note field for future LLM integration
- archived per-run artifacts under `artifacts/runs/`

## Next likely steps
- add endpoint config pattern for external LLM service
- convert prompt note into real prompt-to-code flow
- improve public-facing examples
- add safe execution constraints for Spaces
