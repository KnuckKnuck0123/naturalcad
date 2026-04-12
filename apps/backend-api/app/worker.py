from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import uuid
from pathlib import Path
from typing import cast

import trimesh

from .config import settings
from .models import JobRecord, JobStatus
from .repository import get_database_state, save_job, create_artifact
from .store import _JOBS, _ARTIFACTS
from .main import _upload_bytes_to_supabase_storage, _artifact_to_record
from .main import render_code_from_spec  # We will move this from frontend to backend

# We'll use the same execution approach but wrapped in a safe runner
BUILD123D_PYTHON = sys.executable
ARTIFACTS_DIR = Path("/tmp/naturalcad-worker-artifacts")
RUNS_DIR = ARTIFACTS_DIR / "runs"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)

def _run_build123d(code: str, prompt: str, job_id: str) -> tuple[str | None, str | None, str | None, str]:
    logs: list[str] = []
    glb_path: str | None = None
    stl_path: str | None = None
    step_path: str | None = None

    if not code or not code.strip():
        return None, None, None, "No code provided."

    with tempfile.TemporaryDirectory() as tmpdir:
        source_file = Path(tmpdir) / "user_script.py"
        source_file.write_text(code)
        
        # Unique run prefix
        run_id = uuid.uuid4().hex[:8]
        stl_file = RUNS_DIR / f"{run_id}.stl"
        step_file = RUNS_DIR / f"{run_id}.step"
        glb_file = RUNS_DIR / f"{run_id}.glb"

        logs.append(f"Worker Run ID: {run_id}")
        logs.append(f"Job ID: {job_id}")
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
                stl_path = str(stl_file)
                step_path = str(step_file)
                try:
                    preview_mesh = trimesh.load_mesh(stl_file, force="mesh")
                    # Match frontend rotation logic
                    preview_mesh.apply_transform(
                        trimesh.transformations.rotation_matrix(-1.5707963267948966, [1, 0, 0])
                    )
                    preview_mesh.export(glb_file)
                    glb_path = str(glb_file)
                    logs.append(f"GLB preview generated.")
                except Exception as exc:
                    logs.append(f"GLB conversion failed: {exc}")
                logs.append("Geometry export successful.")
            else:
                logs.append(f"Runner exited with code {result.returncode}.")
        except subprocess.TimeoutExpired:
            logs.append("Execution timed out after 60 seconds.")
        except Exception as exc:
            logs.append(f"Execution error: {exc}")
            logs.append(traceback.format_exc())

    return glb_path, stl_path, step_path, "\n".join(logs)


def process_job(job: JobRecord) -> None:
    job.status = cast(JobStatus, "running")
    save_job(job)
    
    logs = []
    try:
        if not job.spec:
            raise ValueError("No spec available for execution")
        
        # We need the spec renderer locally
        code = render_code_from_spec(job.spec.model_dump())
        glb_path, stl_path, step_path, run_logs = _run_build123d(code, job.prompt, job.id)
        
        logs.append(run_logs)
        
        success = False
        if step_path and (glb_path or stl_path):
            success = True
            # Upload artifacts
            for kind, path in [("glb", glb_path), ("stl", stl_path), ("step", step_path)]:
                if not path or not Path(path).exists():
                    continue
                try:
                    blob = Path(path).read_bytes()
                    suffix = os.path.splitext(path)[1].lower()
                    storage_key = f"jobs/{job.id}/{kind}{suffix}"
                    content_type = "model/gltf-binary" if kind == "glb" else "application/octet-stream"
                    _upload_bytes_to_supabase_storage(storage_key, blob, content_type)
                    
                    from .repository import create_artifact
                    saved = create_artifact(job.id, kind, storage_key, len(blob))
                    logs.append(f"Uploaded {kind} artifact.")
                except Exception as e:
                    logs.append(f"Failed to upload {kind}: {e}")
                    success = False
        
        if success:
            job.status = cast(JobStatus, "completed")
            job.notes.append("Execution and upload complete.")
        else:
            job.status = cast(JobStatus, "failed")
            job.error = "Geometry generation or upload failed."
            job.notes.append("Execution failed.")
            
    except Exception as e:
        job.status = cast(JobStatus, "failed")
        job.error = str(e)
        job.notes.append(traceback.format_exc())
    
    job.notes.append("--- Worker Logs ---")
    job.notes.extend(logs)
    save_job(job)

def run_worker_loop():
    print("Worker started. Polling for 'queued' jobs...")
    while True:
        try:
            from .repository import get_database_state, connect, get_job, save_job
            db_state = get_database_state()
            
            job_to_run = None
            if db_state.enabled:
                with connect() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            select id from jobs 
                            where status = 'queued' 
                            order by created_at asc limit 1 
                            for update skip locked
                        """)
                        row = cur.fetchone()
                        if row:
                            # Mark running immediately
                            cur.execute("update jobs set status = 'running' where id = %s", (row[0],))
                            conn.commit()
                            
                            job_dict = get_job(row[0])
                            if job_dict:
                                job_to_run = JobRecord(**job_dict)
            else:
                # Memory fallback
                from .store import _JOBS
                for jid, jdata in list(_JOBS.items()):
                    if jdata.get("status") == "queued":
                        jdata["status"] = "running"
                        job_to_run = JobRecord(**jdata)
                        break
            
            if job_to_run:
                print(f"Processing job {job_to_run.id}...")
                process_job(job_to_run)
                print(f"Finished job {job_to_run.id}")
            else:
                time.sleep(2)
                
        except Exception as e:
            print(f"Worker error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    run_worker_loop()
