from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'apps' / 'gradio-demo' / 'app' / 'main.py'

spec = importlib.util.spec_from_file_location('naturalcad_gradio_main', SOURCE)
if spec is None or spec.loader is None:
    raise RuntimeError(f'Could not load NaturalCAD app from {SOURCE}')

module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

demo = module.build_ui()

if __name__ == '__main__':
    demo.launch(
        server_name='0.0.0.0',
        server_port=7860,
    )
