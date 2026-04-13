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
        "output_type": "3d_solid",
        "spec": {"generated_code": generated_code},
        "error": error
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


from pydantic import BaseModel

@app.function(
    image=image, 
    gpu="T4", 
    timeout=300,
    secrets=[
        modal.Secret.from_name("huggingface-secret"),
        modal.Secret.from_name("supabase-secret")
    ]
)
@modal.fastapi_endpoint(method="POST")
def generate_cad_endpoint(payload: dict):
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
        model="Qwen/Qwen2.5-Coder-32B-Instruct", 
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

Example:
from build123d import *
width = 60
height = 40
thickness = 6
with BuildPart() as bp:
    with BuildSketch(Plane.XY) as base:
        Rectangle(width, height)
    extrude(amount=thickness)
result = bp.part
"""

    print(f"Calling LLM for prompt: {prompt}")
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
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
        
        output_file = Path(tmpdir) / f"output.{output_format}"
        
        # Execute
        exec_globals = {}
        run_id = uuid.uuid4().hex[:8]
        try:
            exec(compile(generated_code, str(script_path), "exec"), exec_globals)
        except Exception as e:
            import traceback
            err = f"Python execution failed: {e}\n{traceback.format_exc()}"
            _log_job_to_supabase(run_id, prompt, generated_code, "failed", err)
            return {"error": err, "code": generated_code}
            
        result_shape = exec_globals.get("result")
        
        if not result_shape:
            _log_job_to_supabase(run_id, prompt, generated_code, "failed", "No geometry generated")
            return {"error": "No geometry generated"}
        
        # Get shape
        shape = result_shape
        # In newer build123d, parts don't need wrapping extracted for export
        # We just pass the Part or Shape object directly
        
        # Export and upload all formats
        urls = {}
        
        # Make STL and STEP
        export_stl(shape, str(Path(tmpdir) / "output.stl"))
        export_step(shape, str(Path(tmpdir) / "output.step"))
        
        # Make GLB preview
        from trimesh import load_mesh
        import trimesh.transformations as tf
        import math
        
        mesh = load_mesh(str(Path(tmpdir) / "output.stl"), force="mesh")
        # Rotate -90 degrees around X axis so Z is up in the browser
        mesh.apply_transform(tf.rotation_matrix(-math.pi/2, [1, 0, 0]))
        mesh.export(str(Path(tmpdir) / "output.glb"))
        
        for fmt in ["stl", "step", "glb"]:
            out_file = Path(tmpdir) / f"output.{fmt}"
            
            if fmt == "stl":
                content_type = "model/stl"
            elif fmt == "step":
                content_type = "application/octet-stream"
            else:
                content_type = "model/gltf-binary"
                
            storage_key = f"runs/{run_id}/model.{fmt}"
            
            print(f"Uploading {fmt} artifact to Supabase...")
            file_bytes = out_file.read_bytes()
            
            try:
                public_url = _upload_to_supabase(storage_key, file_bytes, content_type)
                urls[fmt] = public_url
            except Exception as e:
                _log_job_to_supabase(run_id, prompt, generated_code, "failed", f"Supabase upload failed for {fmt}: {e}")
                return {"error": f"Supabase upload failed for {fmt}: {e}", "code": generated_code}
        
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