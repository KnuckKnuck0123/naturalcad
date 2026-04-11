#!/usr/bin/env python3
"""Gradio app for live build123d geometry execution and export."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, request

import gradio as gr

BUILD123D_PYTHON = os.getenv("BUILD123D_PYTHON", sys.executable)
BACKEND_URL = os.getenv("NATURALCAD_BACKEND_URL", os.getenv("NL_CAD_BACKEND_URL", "")).strip()
BACKEND_API_KEY = os.getenv("NATURALCAD_API_KEY", os.getenv("NL_CAD_API_KEY", ""))
BACKEND_TIMEOUT_SECONDS = float(os.getenv("NATURALCAD_BACKEND_TIMEOUT", "4"))
ARTIFACTS_DIR = Path(__file__).parent.parent / "artifacts"
RUNS_DIR = ARTIFACTS_DIR / "runs"
LOGS_DIR = ARTIFACTS_DIR / "logs"
RUN_LOG_PATH = LOGS_DIR / "runs.jsonl"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

EXAMPLE_PROMPTS = [
    ["Heavy steel bracket with 4 bolt holes, 90 mm wide, 8 mm thick", "part", "3d_solid"],
    ["Light structural truss beam with 9 panels and a 180 mm span", "part", "3d_solid"],
    ["Industrial notched tower block, 140 mm tall", "part", "3d_solid"],
    ["Smooth roof canopy surface, 200 mm span, shallow rise", "part", "surface"],
    ["Bracket plate profile with 6 holes for a laser-cut sketch", "sketch", "2d_vector"],
]

DEFAULT_CODE = '''from build123d import *

width = 80
height = 50
thickness = 6
hole_diameter = 10

with BuildPart() as bp:
    with BuildSketch(Plane.XY) as base:
        Rectangle(width, height)
        with GridLocations(width * 0.6, height * 0.6, 2, 2):
            Circle(hole_diameter / 2)
    extrude(amount=thickness)

result = bp.part
'''


def render_code_from_spec(spec: dict) -> str:
    geometry_family = spec.get("geometry_family", "bracket_plate")
    output_type = spec.get("output_type", "3d_solid")
    params = spec.get("parameters", {})

    if geometry_family == "tower_block":
        width = params.get("width", 30)
        length = params.get("length", 30)
        height = params.get("height", 120)
        notch = params.get("notch", 10)
        return f'''from build123d import *

width = {width}
length = {length}
height = {height}
notch = {notch}

with BuildPart() as bp:
    Box(width, length, height)
    with Locations((0, 0, height / 4), (0, 0, -height / 4)):
        Box(width + 2, notch, notch, mode=Mode.SUBTRACT)
        Box(notch, length + 2, notch, mode=Mode.SUBTRACT)

result = bp.part
'''

    if geometry_family == "truss_beam":
        span = params.get("span", 140)
        height = params.get("height", 24)
        panel_count = max(3, int(params.get("panel_count", 7)))
        member_size = params.get("member_size", 3)
        return f'''from build123d import *

span = {span}
height = {height}
chord = {member_size}
post = {member_size}
panel_count = {panel_count}

with BuildPart() as bp:
    with Locations((0, 0, chord / 2)):
        Box(span, chord, chord)
    with Locations((0, 0, height - chord / 2)):
        Box(span, chord, chord)

    panel = span / panel_count
    post_locations = [(-span / 2 + i * panel, 0, height / 2) for i in range(panel_count + 1)]
    with Locations(*post_locations):
        Box(post, chord, height)

result = bp.part
'''

    if geometry_family == "truss_elevation":
        span = params.get("span", 140)
        height = params.get("height", 24)
        panel_count = max(3, int(params.get("panel_count", 7)))
        member_size = params.get("member_size", 3)
        preview_thickness = params.get("preview_thickness", 1)
        return f'''from build123d import *

span = {span}
height = {height}
panel_count = {panel_count}
member_size = {member_size}
preview_thickness = {preview_thickness}

with BuildPart() as bp:
    with BuildSketch(Plane.XY) as sk:
        Rectangle(span, member_size, align=(Align.CENTER, Align.CENTER))
        with Locations((0, height)):
            Rectangle(span, member_size, align=(Align.CENTER, Align.CENTER))
        panel = span / panel_count
        for i in range(panel_count + 1):
            x = -span / 2 + i * panel
            with Locations((x, height / 2)):
                Rectangle(member_size, height, align=(Align.CENTER, Align.CENTER))
    extrude(amount=preview_thickness)

result = bp.part
'''

    if geometry_family in {"canopy_surface", "lofted_panel"} or output_type == "surface":
        if geometry_family == "canopy_surface":
            span = params.get("span", 160)
            depth = params.get("depth", 90)
            peak_height = params.get("peak_height", 38)
            thickness = params.get("thickness", 2)
            return f'''from build123d import *

span = {span}
depth = {depth}
peak_height = {peak_height}
thickness = {thickness}

with BuildPart() as bp:
    with BuildSketch(Plane.XY.offset(0)) as s1:
        Rectangle(span, depth)
    with BuildSketch(Plane.XY.offset(peak_height)) as s2:
        Rectangle(span * 0.65, depth * 0.65)
    loft()
    offset(amount=thickness)

result = bp.part
'''
        width = params.get("width", 80)
        depth = params.get("depth", 50)
        rise = params.get("rise", 18)
        thickness = params.get("thickness", 2)
        return f'''from build123d import *

width = {width}
depth = {depth}
rise = {rise}
thickness = {thickness}

with BuildPart() as bp:
    with BuildSketch(Plane.XY.offset(0)) as s1:
        Rectangle(width, depth)
    with BuildSketch(Plane.XY.offset(rise)) as s2:
        Rectangle(width * 0.55, depth * 0.55)
    loft()
    offset(amount=thickness)

result = bp.part
'''

    width = params.get("width", 80)
    height = params.get("height", 50)
    hole_count = max(1, int(params.get("hole_count", 4)))
    hole_diameter = params.get("hole_diameter", 10)
    x_count = max(1, round(hole_count ** 0.5))
    y_count = max(1, (hole_count + x_count - 1) // x_count)

    if output_type == "2d_vector":
        preview_thickness = params.get("preview_thickness", 1)
        return f'''from build123d import *

width = {width}
height = {height}
hole_diameter = {hole_diameter}
preview_thickness = {preview_thickness}

with BuildPart() as bp:
    with BuildSketch(Plane.XY) as base:
        Rectangle(width, height)
        with GridLocations(width * 0.6, height * 0.6, {x_count}, {y_count}):
            Circle(hole_diameter / 2, mode=Mode.SUBTRACT)
    extrude(amount=preview_thickness)

result = bp.part
'''

    thickness = params.get("thickness", 6)
    return f'''from build123d import *

width = {width}
height = {height}
thickness = {thickness}
hole_diameter = {hole_diameter}

with BuildPart() as bp:
    with BuildSketch(Plane.XY) as base:
        Rectangle(width, height)
        with GridLocations(width * 0.6, height * 0.6, {x_count}, {y_count}):
            Circle(hole_diameter / 2, mode=Mode.SUBTRACT)
    extrude(amount=thickness)

result = bp.part
'''


def create_job(prompt: str, mode: str, output_type: str) -> tuple[dict | None, str]:
    if not prompt.strip():
        return None, ""

    if not BACKEND_URL:
        return None, json.dumps({"info": "backend disabled", "detail": "No NATURALCAD_BACKEND_URL configured."}, indent=2)

    payload = json.dumps({"prompt": prompt, "mode": mode, "output_type": output_type}).encode()
    headers = {"Content-Type": "application/json"}
    if BACKEND_API_KEY:
        headers["x-api-key"] = BACKEND_API_KEY

    req = request.Request(
        f"{BACKEND_URL.rstrip('/')}/v1/jobs",
        data=payload,
        headers=headers,
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=BACKEND_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode())
            return data, json.dumps(data, indent=2)
    except error.HTTPError as exc:
        detail = exc.read().decode() if exc.fp else str(exc)
        return None, json.dumps({"error": f"backend http {exc.code}", "detail": detail}, indent=2)
    except Exception as exc:  # noqa: BLE001
        return None, json.dumps({"error": f"backend unavailable: {exc}"}, indent=2)


def _append_run_log(entry: dict) -> None:
    with RUN_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def run_build123d(code: str, prompt: str = "") -> tuple[str | None, str | None, str, str, str | None, float]:
    if not code or not code.strip():
        return None, None, "No code provided.", "No geometry was generated.", None, 0.0

    logs: list[str] = []
    stl_path: str | None = None
    step_path: str | None = None
    started_at = time.time()
    run_id = uuid.uuid4().hex[:8]

    with tempfile.TemporaryDirectory() as tmpdir:
        source_file = Path(tmpdir) / "user_script.py"
        source_file.write_text(code)
        stl_file = RUNS_DIR / f"{run_id}.stl"
        step_file = RUNS_DIR / f"{run_id}.step"

        logs.append(f"Run ID: {run_id}")
        if prompt.strip():
            logs.append(f"Prompt: {prompt.strip()}")
        logs.append("Running build123d script...")

        runner_code = f'''
import sys
from pathlib import Path
from build123d import export_stl, export_step

source_path = Path(r"{source_file}")
user_globals = {{}}
exec(compile(source_path.read_text(), str(source_path), "exec"), user_globals)

candidate = user_globals.get("result")
if candidate is None:
    sys.exit("No `result` geometry found after execution.")

def coerce_shape(obj):
    if obj is None:
        return None
    if hasattr(obj, "wrapped"):
        return obj
    for attr in ("part", "shape", "solid", "obj"):
        value = getattr(obj, attr, None)
        if value is not None and not callable(value):
            obj = value
            if hasattr(obj, "wrapped"):
                return obj
    return obj

shape = coerce_shape(candidate)
if shape is None:
    sys.exit("Could not extract exportable shape from `result`.")

export_stl(shape, r"{stl_file}")
export_step(shape, r"{step_file}")
print("STL exported to {stl_file}")
print("STEP exported to {step_file}")
'''

        runner_file = Path(tmpdir) / "_runner.py"
        runner_file.write_text(runner_code)

        try:
            result = subprocess.run(
                [BUILD123D_PYTHON, str(runner_file)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.stdout:
                logs.append(result.stdout.strip())
            if result.stderr:
                logs.append(f"[stderr] {result.stderr.strip()}")
            if result.returncode == 0 and stl_file.exists() and step_file.exists():
                latest_stl = ARTIFACTS_DIR / "model.stl"
                latest_step = ARTIFACTS_DIR / "model.step"
                shutil.copy2(stl_file, latest_stl)
                shutil.copy2(step_file, latest_step)
                stl_path = str(latest_stl)
                step_path = str(latest_step)
                logs.append(f"Export successful. Archived artifacts at runs/{run_id}.*")
            else:
                logs.append(f"Runner exited with code {result.returncode}.")
        except subprocess.TimeoutExpired:
            logs.append("Execution timed out after 60 seconds.")
        except Exception as exc:  # noqa: BLE001
            logs.append(f"Execution error: {exc}")
            logs.append(traceback.format_exc())

    duration = time.time() - started_at
    summary = f"Model ready in {duration:.2f}s."
    return stl_path, step_path, "\n".join(logs), summary, run_id, duration


def generate_from_prompt(prompt: str, mode: str, output_type: str):
    started_at = time.time()
    backend_ok = True
    client_notice = None
    fallback_level = "normal"
    suspicious_input = False
    job_data, backend_log = create_job(prompt, mode, output_type)
    if job_data is None:
        backend_ok = False
        backend_log = backend_log or "Backend request failed."
        spec = {
            "output_type": output_type,
            "geometry_family": "bracket_plate",
            "parameters": {},
        }
        client_notice = "Backend was unavailable or disabled, so NaturalCAD used a simple local fallback."
        fallback_level = "backend_unavailable"
    else:
        spec = job_data.get("spec")
        suspicious_input = bool(job_data.get("suspicious_input", False))
        fallback_level = job_data.get("fallback_level", "normal")
        if suspicious_input:
            client_notice = "Your prompt looked partly like code or unsafe instructions, so NaturalCAD used a safer interpretation for this run."
        elif fallback_level == "underspecified":
            client_notice = "Your prompt was pretty open-ended, so NaturalCAD filled in conservative defaults for this run."

        if not spec:
            _append_run_log({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "prompt": prompt,
                "mode": mode,
                "output_type": output_type,
                "backend_ok": backend_ok,
                "success": False,
                "error": "Backend created no CAD spec.",
            })
            return None, None, None, backend_log, "Backend created no CAD spec."

    code = render_code_from_spec(spec)
    stl_path, step_path, logs, summary, run_id, execution_seconds = run_build123d(code, prompt)
    combined_logs = "\n\n".join([
        "Backend job created:" if backend_ok else "Backend unavailable, using local fallback:",
        backend_log,
        "Local execution log:",
        logs,
    ])
    success = bool(stl_path)
    _append_run_log({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "prompt": prompt,
        "mode": mode,
        "output_type": output_type,
        "geometry_family": spec.get("geometry_family"),
        "backend_ok": backend_ok,
        "suspicious_input": suspicious_input,
        "fallback_level": fallback_level,
        "success": success,
        "runtime_seconds": round(time.time() - started_at, 3),
        "execution_seconds": round(execution_seconds, 3),
        "error": None if success else "Generation failed.",
    })
    if not stl_path:
        return None, None, None, combined_logs, "Generation failed. Try a simpler prompt or an example."

    final_summary = summary if not client_notice else f"{summary}\n\n⚠️ {client_notice}"
    return stl_path, stl_path, step_path, combined_logs, final_summary


def use_example(prompt: str, mode: str, output_type: str):
    return prompt, mode, output_type


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="NaturalCAD", theme=gr.themes.Base()) as demo:
        gr.Markdown(
            "# NaturalCAD\n"
            "Turn a natural-language prompt into a downloadable CAD result."
        )
        gr.Markdown(
            "**Best for demo:** one-shot parts, frames, blocks, canopies, and simple profiles."
        )

        with gr.Row(equal_height=True):
            with gr.Column(scale=1, min_width=360):
                prompt_input = gr.Textbox(
                    label="Describe what you want",
                    placeholder="A heavy steel bracket with 4 bolt holes, 90 mm wide and 8 mm thick",
                    lines=6,
                )
                with gr.Row():
                    mode_picker = gr.Dropdown(choices=["part", "assembly", "sketch"], value="part", label="Mode")
                    output_picker = gr.Dropdown(choices=["3d_solid", "surface", "2d_vector"], value="3d_solid", label="Output")
                generate_btn = gr.Button("Generate Model", variant="primary")
                gr.Markdown("### Try one of these")
                gr.Examples(
                    examples=EXAMPLE_PROMPTS,
                    inputs=[prompt_input, mode_picker, output_picker],
                    fn=use_example,
                    outputs=[prompt_input, mode_picker, output_picker],
                    cache_examples=False,
                )

            with gr.Column(scale=2, min_width=520):
                model_viewer = gr.Model3D(label="Preview", elem_id="model-viewer", display_mode="solid")
                with gr.Row():
                    stl_download = gr.File(label="Download STL")
                    step_download = gr.File(label="Download STEP")
                status_output = gr.Markdown("Ready. Use the mouse to orbit, pan, and zoom the model.")

        log_output = gr.Textbox(
            label="Run log",
            lines=7,
            max_lines=20,
            interactive=False,
            elem_classes=["log-box"],
        )

        generate_btn.click(
            fn=generate_from_prompt,
            inputs=[prompt_input, mode_picker, output_picker],
            outputs=[model_viewer, stl_download, step_download, log_output, status_output],
        )

    return demo


if __name__ == "__main__":
    app = build_ui()
    app.launch(
        server_name="0.0.0.0",
        server_port=7860,
        css="""
        #model-viewer {height: 620px !important; border-radius: 18px; overflow: hidden;}
        .log-box textarea {font-family: 'JetBrains Mono', monospace; font-size: 13px;}
        .gradio-container {max-width: 1380px !important;}
        button.primary {font-weight: 700;}
        """,
    )
