# NaturalCAD HF Space Notes

## Current intent
- Public-facing NaturalCAD app
- Modal-hosted build123d execution loop
- OpenRouter-backed model generation

## Current prototype state
- Gradio UI
- Modal endpoint execution with API-key gate
- GLB viewer preview (server GLB when available, local STL→GLB fallback otherwise)
- STL + STEP downloads
- starter sample picker
- runtime logs default to error-only
- generated code hidden from UI logs by default
- archived per-run artifacts under `artifacts/runs/`

## Next likely steps
- add 1D/line output mode (DXF/SVG)
- improve assembly reliability (multi-stage planning)
- wire custom domain for public staging
- finalize org Space workflow for team collaboration
