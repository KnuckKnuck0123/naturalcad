"""
NaturalCAD Modal Function
Takes user prompt, generates build123d code, runs it, returns STL.
"""

import modal
from pathlib import Path
import tempfile
import os
import json
import uuid
import httpx
from fastapi import Request, HTTPException

app = modal.App("naturalcad")

# Base image with Python 3.10 and graphics libraries
image = (
    modal.Image.from_registry("python:3.10-slim")
    .apt_install(
        "libgl1",
        "libglib2.0-0", 
        "libxrender1",
        "libxext6",
        "libxkbcommon0"
    )
    .pip_install("build123d==0.10.0", "trimesh", "huggingface_hub", "httpx", "fastapi", "pydantic")
)


def _upload_to_supabase(storage_key: str, file_data: bytes, content_type: str = "application/octet-stream") -> str:
    import httpx
    import urllib.parse
    import os
    
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    bucket = os.environ.get("SUPABASE_BUCKET", "naturalCAD-artifacts")
    
    if not url or not key:
        raise ValueError("Missing Supabase credentials in environment")
        
    encoded_key = urllib.parse.quote(storage_key, safe="/")
    endpoint = f"{url}/storage/v1/object/{bucket}/{encoded_key}"
    
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": content_type,
        "x-upsert": "true"
    }
    
    with httpx.Client() as client:
        resp = client.post(endpoint, content=file_data, headers=headers)
        if resp.status_code >= 400:
            raise Exception(f"Supabase upload failed {resp.status_code}: {resp.text}")
            
    return f"{url}/storage/v1/object/public/{bucket}/{encoded_key}"


def _log_job_to_supabase(job_id: str, prompt: str, generated_code: str, status: str, error: str = None) -> None:
    """Log the job and its code/status to the Supabase database via REST API."""
    import httpx
    import json
    import os
    
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    
    if not url or not key:
        print("Skipping DB logging: No Supabase URL/Key")
        return
        
    endpoint = f"{url}/rest/v1/jobs"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates"
    }
    
    payload = {
        "id": job_id,
        "prompt": prompt,
        "status": status,
        "mode": "part",
        "output_type": "3d_solid"
    }
    
    try:
        with httpx.Client() as client:
            resp = client.post(endpoint, json=payload, headers=headers)
            if resp.status_code >= 400:
                print(f"Failed to log job {job_id} to DB: {resp.text}")
            else:
                print(f"Successfully logged job {job_id} to DB.")
    except Exception as e:
        print(f"Error logging to Supabase DB: {e}")


@app.function(
    image=image, 
    gpu="T4", 
    timeout=300,
    secrets=[
        modal.Secret.from_name("huggingface-secret"),
        modal.Secret.from_name("supabase-secret"),
        modal.Secret.from_name("naturalcad-api-key") # We will add this secret
    ]
)
@modal.fastapi_endpoint(method="POST")
def generate_cad_endpoint(payload: dict, request: Request):
    # API Key check
    import os
    expected_key = os.environ.get("NATURALCAD_API_KEY")
    provided_key = request.headers.get("x-api-key")
    
    if expected_key and provided_key != expected_key:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    prompt = payload.get("prompt", "")
    output_format = payload.get("output_format", "stl")
    return generate_cad.local(prompt, output_format)


@app.function(
    image=image, 
    gpu="T4", 
    timeout=300,
    secrets=[
        modal.Secret.from_name("huggingface-secret"),
        modal.Secret.from_name("supabase-secret")
    ]
)
def generate_cad(prompt: str, output_format: str = "stl"):
    """Main function: prompt -> LLM -> code -> build123d -> Supabase STL URL"""
    import os
    import uuid
    from huggingface_hub import InferenceClient
    
    # 1. LLM Code Generation
    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        return {"error": "HF_TOKEN not found in environment secrets"}
        
    client = InferenceClient(
        model="deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct", 
        token=hf_token
    )
    
    system_prompt = """You are an expert Python developer for CAD code generation using the build123d library.
Write Python code to create the 3D model requested by the user.

Rules:
1. ONLY return valid Python code. No markdown formatting, no explanations.
2. ALWAYS import build123d using: `from build123d import *`
3. ALWAYS store the final resulting Shape/Part in a variable named `result`.
4. Use standard primitives like Box, Cylinder, Rectangle, Circle, etc.
5. Make sure the code is simple, correct and uses the modern builder API (with BuildPart() as bp, etc.).
6. Do NOT use the `points=` keyword argument in `Polygon()`. Use positional: `Polygon([ (0,0), (10,0) ])`.
7. `PolarLocations` and `GridLocations` ARE context managers. Use `with PolarLocations(radius, count):` or `with GridLocations(x_spacing, y_spacing, x_count, y_count):`. Do NOT wrap them in `Locations()`.
8. NEVER use standalone `rotate()` or `translate()`. They do not exist in build123d. To move or rotate, use `with Locations((x, y, z)):` or `my_obj.rotate(Axis.Z, 45)`.
9. `extrude()` takes `amount` (e.g. `extrude(amount=10)`), or `both=True`. Do NOT use `start=` or `distance=`.
10. `extrude()` MUST be called immediately after a `with BuildSketch():` block. You cannot extrude without a sketch!

Refer to the 'build123d KNOWLEDGE BASE' below for accurate syntax and common operations. Adapt and combine these patterns to generate the requested 3D model.

Example:
from build123d import *
with BuildPart() as bp:
    with BuildSketch(Plane.XY) as base:
        Rectangle(60, 40)
    extrude(amount=10)
    with BuildSketch(bp.faces().sort_by(Axis.Z)[-1]):
        Circle(10)
    extrude(amount=20)
result = bp.part

# build123d KNOWLEDGE BASE - Copy these patterns exactly:

# PATTERN 1: Simple Box
with BuildPart() as p:
    Box(80, 60, 10)
result = p.part

# PATTERN 2: Box with Hole
with BuildPart() as p:
    Box(80, 60, 10)
    Cylinder(radius=11, height=10, mode=Mode.SUBTRACT)
result = p.part

# PATTERN 3: Extruded Sketch with Hole
with BuildPart() as p:
    with BuildSketch():
        Circle(60)
        Rectangle(20, 20, mode=Mode.SUBTRACT)
    extrude(amount=10)
result = p.part

# PATTERN 4: Multiple Holes using Locations
with BuildPart() as p:
    with BuildSketch():
        Circle(80)
    extrude(amount=10)
    with BuildSketch(p.faces().sort_by(Axis.Z)[-1]):
        with Locations((20, 0), (-20, 0), (0, 20), (0, -20)):
            Cylinder(radius=5, height=10, mode=Mode.SUBTRACT)
result = p.part

# PATTERN 5: PolarLocations for holes in a circle
with BuildPart() as p:
    with BuildSketch():
        Circle(50)
    extrude(amount=10)
    with BuildSketch(p.faces().sort_by(Axis.Z)[-1]):
        with PolarLocations(20, 6):
            Cylinder(radius=3, height=10, mode=Mode.SUBTRACT)
result = p.part

# PATTERN 6: Fillet edges
with BuildPart() as p:
    Box(60, 40, 10)
    fillet(p.edges(), radius=2)
result = p.part

# PATTERN 7: Chamfer
with BuildPart() as p:
    Box(60, 40, 10)
    chamfer(p.edges(), radius=1)
result = p.part

# PATTERN 8: Cylinder
with BuildPart() as p:
    Cylinder(radius=20, height=50)
result = p.part

# PATTERN 9: Rounded Rectangle
with BuildPart() as p:
    RectangleRounded(60, 40, 5)
    extrude(amount=10)
result = p.part

# PATTERN 10: Pyramid (using Cone)
with BuildPart() as p:
    Cone(radius=50, height=100)
result = p.part

# PATTERN 11: Lofting two sketches
with BuildPart() as p:
    with BuildSketch(Plane.XY.offset(0)) as s1:
        Circle(30)
    with BuildSketch(Plane.XY.offset(50)) as s2:
        Rectangle(20, 20)
    loft(s1.sketch, s2.sketch)
result = p.part

# PATTERN 12: Mirroring a part
with BuildPart() as p:
    Box(30, 20, 10)
    mirror(p.part, Plane.YZ)
result = p.part

# PATTERN 13: Union of two shapes
with BuildPart() as p:
    Box(30, 30, 30)
    with Locations((20, 0, 0)):
        Sphere(15)
    add()
result = p.part

# PATTERN 14: Difference (Subtract) of two shapes
with BuildPart() as p:
    Box(30, 30, 30)
    with Locations((10, 0, 0)):
        Cylinder(radius=5, height=40)
    subtract()
result = p.part

# PATTERN 15: Intersection of two shapes
with BuildPart() as p:
    Box(30, 30, 30)
    with Locations((15, 0, 0)):
        Sphere(20)
    intersect()
result = p.part
"""

    # Retry loop
    max_attempts = 3
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt}
    ]
    
    for attempt in range(max_attempts):
        print(f"Calling LLM for prompt (Attempt {attempt+1}): {prompt}")
        try:
            response = client.chat.completions.create(
                messages=messages,
                max_tokens=1024,
                temperature=0.2,
            )
            generated_code = response.choices[0].message.content.strip()
            
            # Clean up markdown
            if generated_code.startswith("```python"):
                generated_code = generated_code[9:]
            elif generated_code.startswith("```"):
                generated_code = generated_code[3:]
            if generated_code.endswith("```"):
                generated_code = generated_code[:-3]
                
            generated_code = generated_code.strip()
        except Exception as e:
            return {"error": f"LLM code generation failed: {e}"}

        print(f"Generated Code:\n{generated_code}")

        # Run build123d
        from build123d import export_stl, export_step
        
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.py"
            script_path.write_text(generated_code)
            
            # Execute
            exec_globals = {}
            run_id = str(uuid.uuid4())  # Full UUID for Supabase
            
            # Security: Scrub environment variables
            original_env = os.environ.copy()
            os.environ.pop("HF_TOKEN", None)
            os.environ.pop("SUPABASE_URL", None)
            os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)
            os.environ.pop("NATURALCAD_API_KEY", None)
            
            exec_success = False
            err = ""
            try:
                exec(compile(generated_code, str(script_path), "exec"), exec_globals)
                exec_success = True
            except Exception as e:
                import traceback
                err = f"{type(e).__name__}: {e}"
                print(f"Execution failed: {err}")
                
            # Restore env
            os.environ.clear()
            os.environ.update(original_env)
            
            if exec_success:
                result_shape = exec_globals.get("result")
                if not result_shape:
                    err = "No 'result' variable found."
                    exec_success = False
            
            if not exec_success:
                if attempt < max_attempts - 1:
                    print("Retrying with error message...")
                    messages.append({"role": "assistant", "content": generated_code})
                    messages.append({"role": "user", "content": f"That code failed with error:\n{err}\nFix the code and return only the fixed Python script."})
                    continue
                else:
                    _log_job_to_supabase(run_id, prompt, generated_code, "failed", err)
                    return {"error": err, "code": generated_code}
            
            # Success! Export and upload inside tmpdir context
            shape = result_shape
            
            # Export all formats
            urls = {}
            stl_path = Path(tmpdir) / "output.stl"
            step_path = Path(tmpdir) / "output.step"
            glb_path = Path(tmpdir) / "output.glb"
            
            # Make STL
            try:
                export_stl(shape, str(stl_path))
                print(f"STL exported: {stl_path.exists()}, size: {stl_path.stat().st_size if stl_path.exists() else 0}")
            except Exception as e:
                print(f"Failed to export STL: {e}")
                stl_path = None
                
            # Make STEP
            try:
                export_step(shape, str(step_path))
                print(f"STEP exported: {step_path.exists()}")
            except Exception as e:
                print(f"Failed to export STEP: {e}")
                step_path = None
            
            # Make GLB preview from STL
            try:
                if stl_path and stl_path.exists():
                    from trimesh import load_mesh
                    import trimesh.transformations as tf
                    import math
                    
                    mesh = load_mesh(str(stl_path), force="mesh")
                    mesh.apply_transform(tf.rotation_matrix(-math.pi/2, [1, 0, 0]))
                    mesh.export(str(glb_path))
                    print(f"GLB exported: {glb_path.exists()}")
                else:
                    print("Cannot create GLB - no STL file")
            except Exception as e:
                print(f"Failed to export GLB: {e}")
            
            # Upload existing files to Supabase
            file_pairs = [
                ("stl", stl_path, "model/stl"),
                ("step", step_path, "application/octet-stream"),
                ("glb", glb_path, "model/gltf-binary"),
            ]
            
            for fmt, file_path, content_type in file_pairs:
                if not file_path or not file_path.exists():
                    continue
                    
                storage_key = f"runs/{run_id[:8]}/model.{fmt}"
                
                print(f"Uploading {fmt} artifact to Supabase...")
                file_bytes = file_path.read_bytes()
                print(f"DEBUG: {fmt} file size: {len(file_bytes)} bytes")
                
                try:
                    public_url = _upload_to_supabase(storage_key, file_bytes, content_type)
                    urls[fmt] = public_url
                except Exception as e:
                    print(f"Upload error for {fmt}: {e}")
            
            _log_job_to_supabase(run_id, prompt, generated_code, "completed")
            return {
                "success": True,
                "urls": urls,
                "prompt": prompt,
                "generated_code": generated_code
            }


@app.function(image=image)
def health_check():
    """Verify build123d works"""
    from build123d import Box
    return {"status": "ok", "build123d": "working"}


if __name__ == "__main__":
    # Test locally in the container
    result = generate_cad.call("a simple bracket plate")
    print(result)