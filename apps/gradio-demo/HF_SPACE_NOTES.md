# NaturalCAD HF Space Notes

## Current intent
- Public-facing NaturalCAD 2D app
- sketch/image/text to editable DXF
- lightweight Hugging Face test lane before deeper website integration

## Current prototype state
- Gradio UI
- text prompt, sketch image, or both
- validated SVG preview
- DXF and DrawingScene JSON downloads
- versioned, portable DrawingScene 1.0 contract
- stable entity IDs for refinement
- polylines, circles, arcs, true obround slots, hatches, text, dimensions, and leaders
- live OpenRouter model generation and refinement with explicit local fallback state
- starter sample picker
- archived per-run artifacts under `artifacts/runs/`

## Deployment target
- Space: `noahtheboa/naturalcad-2d`
- Host: https://noahtheboa-naturalcad-2d.hf.space
- Required Space secret: `OPENROUTER_API_KEY`
- Space variable: `NATURALCAD_2D_MODEL=anthropic/claude-opus-4.8`

## Verified locally
- live text generation through `openai/gpt-4.1-mini`
- live scene-aware refinement that preserved unchanged entity IDs
- DXF reopen/audit with zero errors
- contract and exporter regression tests

## Next likely steps
- deploy this prototype revision to the dedicated 2D Space
- test one live sketch-image generation in the hosted environment
- validate representative outputs in QCAD
- add feedback controls and bounded artifact retention before broader public testing
