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
        css="""
        #model-viewer {height: 620px !important; border-radius: 18px; overflow: hidden;}
        .log-box textarea {font-family: 'JetBrains Mono', monospace; font-size: 13px;}
        .gradio-container {max-width: 1380px !important;}
        button.primary {font-weight: 700;}
        """,
    )
