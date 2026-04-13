#!/usr/bin/env python3
"""Gradio app for live build123d geometry execution and export."""

from __future__ import annotations

import json
import mimetypes
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
import trimesh

BUILD123D_PYTHON = os.getenv("BUILD123D_PYTHON", sys.executable)
BACKEND_URL = os.getenv("NATURALCAD_BACKEND_URL", os.getenv("NL_CAD_BACKEND_URL", "")).strip()
BACKEND_API_KEY = os.getenv("NATURALCAD_API_KEY", os.getenv("NL_CAD_API_KEY", ""))
BACKEND_TIMEOUT_SECONDS = float(os.getenv("NATURALCAD_BACKEND_TIMEOUT", "60"))
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


def _legacy_spec_from_semantic(spec: dict) -> dict:
    if "geometry_family" in spec and "parameters" in spec:
        return spec

    family_hint = spec.get("family_hint") or {}
    geometry = spec.get("geometry") or {}
    semantic_part = spec.get("semantic_part") or {}
    dimensions = dict(spec.get("dimensions") or {})
    output_type = spec.get("output_type", "3d_solid")

    geometry_family = family_hint.get("name")
    if not geometry_family:
        topology = " ".join(semantic_part.get("topology") or []).lower()
        feature_types = " ".join((f.get("feature_type", "") for f in geometry.get("features") or [] if isinstance(f, dict))).lower()
        if "truss" in topology or "truss" in feature_types or "span" in dimensions and "panel_count" in dimensions:
            geometry_family = "truss_beam" if output_type != "2d_vector" else "truss_elevation"
        elif output_type == "surface":
            geometry_family = "canopy_surface"
        elif "tower" in topology or "mass" in topology or "notch" in feature_types:
            geometry_family = "tower_block"
        else:
            geometry_family = "bracket_plate"

    params = dict(dimensions)
    if output_type == "2d_vector":
        params.setdefault("preview_thickness", 1)
    if geometry_family == "bracket_plate":
        params.setdefault("width", 80)
        params.setdefault("height", 50)
        params.setdefault("thickness", 6)
        params.setdefault("hole_count", 4)
        params.setdefault("hole_diameter", 10)
    elif geometry_family == "truss_beam":
        params.setdefault("span", 140)
        params.setdefault("height", 24)
        params.setdefault("panel_count", 7)
        params.setdefault("member_size", 3)
    elif geometry_family == "truss_elevation":
        params.setdefault("span", 140)
        params.setdefault("height", 24)
        params.setdefault("panel_count", 7)
        params.setdefault("member_size", 3)
        params.setdefault("preview_thickness", 1)
    elif geometry_family == "tower_block":
        params.setdefault("width", 30)
        params.setdefault("length", 30)
        params.setdefault("height", 120)
        params.setdefault("notch", 10)
    elif geometry_family == "canopy_surface":
        params.setdefault("span", 160)
        params.setdefault("depth", 90)
        params.setdefault("peak_height", 38)
        params.setdefault("thickness", 2)
    elif geometry_family == "lofted_panel":
        params.setdefault("width", 80)
        params.setdefault("depth", 50)
        params.setdefault("rise", 18)
        params.setdefault("thickness", 2)

    return {
        "geometry_family": geometry_family,
        "output_type": output_type,
        "parameters": params,
    }


def render_code_from_spec(spec: dict) -> str:
    spec = _legacy_spec_from_semantic(spec)
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


def upload_job_artifact(job_id: str, kind: str, path: str) -> tuple[dict | None, str]:
    if not BACKEND_URL or not job_id:
        return None, ""

    file_path = Path(path)
    if not file_path.exists():
        return None, json.dumps({"error": f"artifact path missing: {path}"}, indent=2)

    boundary = f"----naturalcad-{uuid.uuid4().hex}"
    content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
    file_bytes = file_path.read_bytes()

    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode())
    body.extend(b'Content-Disposition: form-data; name="kind"\r\n\r\n')
    body.extend(kind.encode())
    body.extend(b"\r\n")

    body.extend(f"--{boundary}\r\n".encode())
    body.extend(
        f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'.encode()
    )
    body.extend(f"Content-Type: {content_type}\r\n\r\n".encode())
    body.extend(file_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode())

    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    if BACKEND_API_KEY:
        headers["x-api-key"] = BACKEND_API_KEY

    req = request.Request(
        f"{BACKEND_URL.rstrip('/')}/v1/jobs/{job_id}/artifacts",
        data=bytes(body),
        headers=headers,
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=BACKEND_TIMEOUT_SECONDS) as response:
            data = json.loads(response.read().decode())
            return data, json.dumps(data, indent=2)
    except error.HTTPError as exc:
        detail = exc.read().decode() if exc.fp else str(exc)
        return None, json.dumps({"error": f"artifact upload http {exc.code}", "detail": detail}, indent=2)
    except Exception as exc:  # noqa: BLE001
        return None, json.dumps({"error": f"artifact upload failed: {exc}"}, indent=2)


def _append_run_log(entry: dict) -> None:
    with RUN_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


def run_build123d_mock(code: str, prompt: str = "") -> tuple[str | None, str | None, str | None, str, str, str | None, float]:
    return None, None, None, "Mock execution.", "Mock mode.", "mock_id", 0.0


def run_build123d(code: str, prompt: str = "") -> tuple[str | None, str | None, str | None, str, str, str | None, float]:
    """Run build123d code locally."""
    with tempfile.TemporaryDirectory() as tmpdir:
        source_file = Path(tmpdir) / "user_script.py"
        source_file.write_text(code)
        
        run_id = uuid.uuid4().hex[:8]
        stl_file = Path(tmpdir) / f"{run_id}.stl"
        step_file = Path(tmpdir) / f"{run_id}.step"
        glb_file = Path(tmpdir) / f"{run_id}.glb"
        
        logs = [f"Run ID: {run_id}"]
        
        runner_code = f'''
import sys
from pathlib import Path
from build123d import export_stl, export_step
from trimesh import load_mesh

source = Path(r"{source_file}").read_text()
g = {{}}
exec(compile(source, str(source), g))
result = g.get("result")
if result is None:
    sys.exit("No `result` geometry")

shape = result
if hasattr(result, "wrapped"): shape = result.wrapped
if hasattr(result, "part"): shape = result.part
if hasattr(result, "shape"): shape = result.shape

if shape is None:
    sys.exit("Could not extract shape")

export_stl(shape, r"{stl_file}")
export_step(shape, r"{step_file}")

# Make GLB preview
mesh = load_mesh(str(stl_file), force="mesh")
mesh.apply_transform([
    [1,0,0,0], [0,0,1,0], [0,-1,0,0], [0,0,0,1]], False)
mesh.export(str(glb_file))
'''
        runner_file = Path(tmpdir) / "_runner.py"
        runner_file.write_text(runner_code)
        
        result = subprocess.run(
            [sys.executable, str(runner_file)],
            capture_output=True, text=True, timeout=60
        )
        logs.append(result.stdout or "")
        if result.stderr:
            logs.append(f"[stderr] {result.stderr[:500]}")
        
        if result.returncode != 0:
            return None, None, None, "\n".join(logs), f"Error: {result.returncode}", run_id, 0.0
        
        # Copy files to persistent location
        run_dir = Path("artifacts/runs")
        run_dir.mkdir(parents=True, exist_ok=True)
        final_stl = run_dir / f"{run_id}.stl"
        final_step = run_dir / f"{run_id}.step"
        final_glb = run_dir / f"{run_id}.glb"
        shutil.copy(stl_file, final_stl)
        shutil.copy(step_file, final_step)
        if glb_file.exists():
            shutil.copy(glb_file, final_glb)
        
        logs.append(f"Generated: {run_id}")
        return str(final_glb), str(final_stl), str(final_step), "\n".join(logs), "Success", run_id, 0.0


def generate_from_prompt(prompt: str, mode: str, output_type: str):
    started_at = time.time()
    
    if BACKEND_URL:
        # We are now hitting a Modal Web Endpoint
        # It expects a JSON payload matching the function arguments
        payload = json.dumps({"prompt": prompt, "output_format": output_type}).encode()
        headers = {"Content-Type": "application/json"}
        
        if BACKEND_API_KEY:
            headers["x-api-key"] = BACKEND_API_KEY
        
        req = request.Request(
            BACKEND_URL,
            data=payload,
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=BACKEND_TIMEOUT_SECONDS) as response:
                result = json.loads(response.read().decode())
                
                if "error" in result:
                    return None, None, None, f"Error from backend:\n{result['error']}", "Backend generation failed."
                    
                urls = result.get("urls", {})
                code = result.get("generated_code", "")
                
                glb_url = urls.get("glb")
                stl_url = urls.get("stl")
                step_url = urls.get("step")
                
                # Download files to artifacts directory (same as local mode)
                # so Gradio can serve them properly
                run_dir = Path("artifacts/runs")
                run_dir.mkdir(parents=True, exist_ok=True)
                run_id = uuid.uuid4().hex[:8]
                
                glb_file = None
                stl_file = None
                step_file = None
                
                if glb_url:
                    glb_path = run_dir / f"{run_id}.glb"
                    print(f"DEBUG: Downloading GLB from {glb_url}")
                    with request.urlopen(glb_url) as r:
                        data = r.read()
                        print(f"DEBUG: Downloaded {len(data)} bytes")
                        with open(glb_path, "wb") as f:
                            f.write(data)
                    glb_file = str(glb_path)
                    print(f"DEBUG: GLB saved to {glb_file}")
                    
                if stl_url:
                    stl_path = run_dir / f"{run_id}.stl"
                    print(f"DEBUG: Downloading STL from {stl_url}")
                    with request.urlopen(stl_url) as r:
                        data = r.read()
                        print(f"DEBUG: Downloaded {len(data)} bytes")
                        with open(stl_path, "wb") as f:
                            f.write(data)
                    stl_file = str(stl_path)
                    print(f"DEBUG: STL saved to {stl_file}")
                    
                if step_url:
                    step_path = run_dir / f"{run_id}.step"
                    print(f"DEBUG: Downloading STEP from {step_url}")
                    with request.urlopen(step_url) as r:
                        data = r.read()
                        print(f"DEBUG: Downloaded {len(data)} bytes")
                        with open(step_path, "wb") as f:
                            f.write(data)
                    step_file = str(step_path)
                    print(f"DEBUG: STEP saved to {step_file}")
                
                combined_logs = f"Generated build123d code:\n\n{code}\n\n"
                combined_logs += "Execution complete. Artifacts uploaded to Supabase."
                final_summary = "Model ready!"
                
                return glb_file, stl_file, step_file, combined_logs, final_summary
        except error.HTTPError as exc:
            detail = exc.read().decode() if exc.fp else str(exc)
            return None, None, None, f"Backend HTTP {exc.code}: {detail}", "Generation failed."
        except Exception as exc:
            return None, None, None, f"Backend error: {exc}", "Generation failed."
    
    # Fallback to local code stub if backend is missing
    spec = {
        "output_type": output_type,
        "geometry_family": "bracket_plate",
        "parameters": {"width": 60, "height": 40, "thickness": 6},
    }
    code = render_code_from_spec(spec)
    combined_logs = f"Local fallback:\n{code}"
    final_summary = "Code generated."
    return None, None, None, combined_logs, final_summary


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
