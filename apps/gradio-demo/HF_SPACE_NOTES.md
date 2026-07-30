# NaturalCAD HF Space Notes

## Current intent
- Public-facing NaturalCAD 2D app
- sketch/image/text to editable DXF
- lightweight Hugging Face test lane before deeper website integration

## Current prototype state
- Gradio UI
- text prompt, sketch image, or both
- SVG preview
- DXF download
- lightweight internal drafting scene model
- first real OpenRouter model-call path with local fallback
- starter sample picker
- archived per-run artifacts under `artifacts/runs/`

## Next likely steps
- wire a real model call into the drafting scene schema
- improve public-facing examples and test sketches
- expand drafting coverage: hatches, linetypes, dimensions, leaders, text
- validate outputs in QCAD before shifting the lane back toward the main website
