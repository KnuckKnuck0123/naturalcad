# NaturalCAD Space Runtime Notes

## Intention

The Hugging Face Space should run the leanest useful version of NaturalCAD.

## What the Space really needs

- `app.py`
- root `requirements.txt`
- `apps/gradio-demo/app/main.py`
- selected branding assets used by the README
- lightweight artifacts directories with `.gitkeep`

## What the Space does not need for MVP runtime

- `apps/backend-api/`
- `apps/web-visualizer/`
- legacy archive material
- local generated runs/log files

## Why `.hfignore` exists

The repository can still hold planning material and future infrastructure, while the Space runtime stays lighter and less confusing.
