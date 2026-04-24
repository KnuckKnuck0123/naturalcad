"""
NaturalCAD Modal Worker — CAD generation endpoint.

API CONTRACT
------------
POST /  (Modal fastapi_endpoint)

Request JSON:
    prompt       str  required  — natural-language description of the model
    mode         str  optional  — "part" (default) | "assembly" | "sketch"
    output_type  str  optional  — "3d_solid" (default) | "surface" | "2d_vector"
    output_format str optional  — legacy alias for output_type; ignored if output_type is present

Response JSON (success):
    job_id          str   — full UUID for this run (matches Supabase row and storage key prefix)
    generated_code  str   — the build123d Python script that was executed
    urls            dict  — keys: "glb", "stl", "step" (any subset may be absent on export error)
    prompt          str   — echoed input prompt
    success         bool  — always True on this path

Response JSON (error):
    error  str  — human-readable failure reason
    code   str  — last generated Python script (present only on execution failure)

Auth: x-api-key header must match NATURALCAD_API_KEY secret when that secret is set.
"""

import modal
import ast
import secrets
import signal
import threading
import time
from collections import defaultdict, deque
from contextlib import contextmanager
from pathlib import Path
import tempfile
import os
import httpx
from fastapi import Request, HTTPException
from pydantic import BaseModel, model_validator

app = modal.App("naturalcad")

# Container image — Python 3.10 + OpenCASCADE graphics libs
image = (
    modal.Image.from_registry("python:3.10-slim")
    .apt_install(
        "libgl1",
        "libglib2.0-0",
        "libxrender1",
        "libxext6",
        "libxkbcommon0",
    )
    .pip_install("build123d==0.10.0", "trimesh", "httpx", "fastapi", "pydantic")
)


# ---------------------------------------------------------------------------
# Request model
# ---------------------------------------------------------------------------

_VALID_MODES = {"part", "assembly", "sketch"}
_VALID_OUTPUTS = {"3d_solid", "surface", "2d_vector", "1d_path"}
_MAX_PROMPT_CHARS = int(os.environ.get("NATURALCAD_MAX_PROMPT_CHARS", "1200"))

_RATE_WINDOW_SECONDS = int(os.environ.get("NATURALCAD_RATE_WINDOW_SECONDS", "60"))
_RATE_LIMIT_PER_IP = int(os.environ.get("NATURALCAD_RATE_LIMIT_PER_IP", "20"))
_RATE_LIMIT_PER_KEY = int(os.environ.get("NATURALCAD_RATE_LIMIT_PER_KEY", "60"))
_MAX_CONCURRENT_RUNS = max(1, int(os.environ.get("NATURALCAD_MAX_CONCURRENT_RUNS", "3")))
_MAX_QUEUE_DEPTH = max(0, int(os.environ.get("NATURALCAD_MAX_QUEUE_DEPTH", "10")))
_QUEUE_WAIT_SECONDS = max(0, int(os.environ.get("NATURALCAD_QUEUE_WAIT_SECONDS", "15")))

_RUN_SLOT_SEMAPHORE = threading.BoundedSemaphore(_MAX_CONCURRENT_RUNS)
_STATE_LOCK = threading.Lock()
_ACTIVE_RUNS = 0
_QUEUED_RUNS = 0
_REQUESTS_BY_IP = defaultdict(deque)
_REQUESTS_BY_KEY = defaultdict(deque)

_BLOCKED_NAMES = {
    "open", "exec", "eval", "compile", "__import__", "input", "breakpoint",
    "globals", "locals", "vars", "getattr", "setattr", "delattr", "help",
    "os", "sys", "subprocess", "socket", "httpx", "requests", "urllib",
    "pathlib", "shutil", "tempfile", "ctypes", "multiprocessing", "threading",
    "asyncio", "importlib", "builtins",
}
_BLOCKED_ATTRS = {
    "system", "popen", "run", "Popen", "call", "check_output", "check_call",
    "urlopen", "request", "get", "post", "put", "delete", "patch", "connect",
    "remove", "unlink", "rmdir", "rmtree", "rename", "replace",
}
_SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "print": print,
    "range": range,
    "round": round,
    "set": set,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
    "Exception": Exception,
    "ValueError": ValueError,
}

_VERBOSE_LOGS = os.environ.get("NATURALCAD_VERBOSE_LOGS", "false").strip().lower() in {"1", "true", "yes", "on"}


def _log_info(message: str) -> None:
    if _VERBOSE_LOGS:
        print(message)


def _log_error(message: str) -> None:
    print(message)


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "").strip()
    if xff:
        return xff.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _allow_request(bucket: dict, key: str, limit: int, window_seconds: int) -> bool:
    now = time.time()
    cutoff = now - window_seconds
    with _STATE_LOCK:
        q = bucket[key]
        while q and q[0] < cutoff:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True


@contextmanager
def _acquire_run_slot():
    global _ACTIVE_RUNS, _QUEUED_RUNS
    joined_queue = False

    with _STATE_LOCK:
        if _ACTIVE_RUNS >= _MAX_CONCURRENT_RUNS:
            if _QUEUED_RUNS >= _MAX_QUEUE_DEPTH:
                raise HTTPException(status_code=429, detail={"error": "Server busy, please retry."})
            _QUEUED_RUNS += 1
            joined_queue = True

    acquired = _RUN_SLOT_SEMAPHORE.acquire(timeout=_QUEUE_WAIT_SECONDS if joined_queue else 1)

    if joined_queue:
        with _STATE_LOCK:
            _QUEUED_RUNS = max(0, _QUEUED_RUNS - 1)

    if not acquired:
        raise HTTPException(status_code=429, detail={"error": "Server busy, please retry."})

    with _STATE_LOCK:
        _ACTIVE_RUNS += 1

    try:
        yield
    finally:
        with _STATE_LOCK:
            _ACTIVE_RUNS = max(0, _ACTIVE_RUNS - 1)
        _RUN_SLOT_SEMAPHORE.release()


def _strip_build123d_imports(code: str) -> str:
    lines = []
    for line in code.splitlines():
        if line.strip() == "from build123d import *":
            continue
        lines.append(line)
    return "\n".join(lines).strip() + "\n"


def _validate_generated_code(code: str) -> tuple[bool, str | None]:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, f"SyntaxError: {exc}"

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            return False, "Import statements are not allowed in generated code."
        if isinstance(node, ast.Name) and (node.id in _BLOCKED_NAMES or node.id.startswith("__")):
            return False, f"Blocked identifier: {node.id}"
        if isinstance(node, ast.Attribute) and node.attr in _BLOCKED_ATTRS:
            return False, f"Blocked attribute access: {node.attr}"
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _BLOCKED_NAMES:
                return False, f"Blocked function call: {node.func.id}"
            if isinstance(node.func, ast.Attribute) and node.func.attr in _BLOCKED_ATTRS:
                return False, f"Blocked function call: {node.func.attr}"

    return True, None


def _exec_with_timeout(code: str, script_path: Path, exec_globals: dict) -> None:
    timeout_seconds = max(1, int(os.environ.get("NATURALCAD_EXEC_TIMEOUT_SECONDS", "60")))

    # SIGALRM only works on the main thread. Modal may invoke this handler on
    # a worker thread, so fall back to direct exec in that case.
    if threading.current_thread() is not threading.main_thread():
        exec(compile(code, str(script_path), "exec"), exec_globals)
        return

    def _timeout_handler(signum, frame):
        raise TimeoutError(f"Execution exceeded {timeout_seconds}s")

    old_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(timeout_seconds)
    try:
        exec(compile(code, str(script_path), "exec"), exec_globals)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


class GenerateRequest(BaseModel):
    prompt: str
    mode: str = "part"
    output_type: str = "3d_solid"
    # Legacy alias — accepted silently, mapped below
    output_format: str | None = None

    @model_validator(mode="after")
    def _resolve_aliases_and_validate(self) -> "GenerateRequest":
        # Map legacy output_format → output_type when output_type was not supplied
        if self.output_type == "3d_solid" and self.output_format and self.output_format != "3d_solid":
            self.output_type = self.output_format
        if self.mode not in _VALID_MODES:
            raise ValueError(f"mode must be one of {sorted(_VALID_MODES)}")
        if self.output_type not in _VALID_OUTPUTS:
            raise ValueError(f"output_type must be one of {sorted(_VALID_OUTPUTS)}")
        prompt_text = self.prompt.strip()
        if not prompt_text:
            raise ValueError("prompt must not be empty")
        if len(prompt_text) > _MAX_PROMPT_CHARS:
            raise ValueError(f"prompt too long (max {_MAX_PROMPT_CHARS} chars)")
        return self


# ---------------------------------------------------------------------------
# Supabase helpers
# ---------------------------------------------------------------------------

def _upload_to_supabase(storage_key: str, file_data: bytes, content_type: str = "application/octet-stream") -> str:
    import urllib.parse

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
        "x-upsert": "true",
    }

    with httpx.Client() as client:
        resp = client.post(endpoint, content=file_data, headers=headers)
        if resp.status_code >= 400:
            raise Exception(f"Supabase upload failed {resp.status_code}: {resp.text}")

    return f"{url}/storage/v1/object/public/{bucket}/{encoded_key}"


def _log_job_to_supabase(
    job_id: str,
    prompt: str,
    mode: str,
    output_type: str,
    generated_code: str,
    status: str,
    error: str = None,
) -> None:
    """Write a job row to the Supabase jobs table (best-effort; never raises)."""
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

    if not url or not key:
        _log_info("Skipping DB logging: SUPABASE_URL or key not set")
        return

    endpoint = f"{url}/rest/v1/jobs"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }
    payload = {
        "id": job_id,
        "prompt": prompt,
        "status": status,
        "mode": mode,
        "output_type": output_type,
    }
    store_code = os.environ.get("NATURALCAD_STORE_CODE", "true").strip().lower() in {"1", "true", "yes", "on"}
    if store_code and generated_code:
        payload["generated_code"] = generated_code
    if error:
        payload["error_text"] = error

    try:
        with httpx.Client() as client:
            resp = client.post(endpoint, json=payload, headers=headers)
            if resp.status_code >= 400 and "generated_code" in payload:
                # Backward-compat fallback for schemas that do not yet have generated_code.
                payload.pop("generated_code", None)
                resp = client.post(endpoint, json=payload, headers=headers)
            if resp.status_code >= 400:
                _log_error(f"DB log failed for job {job_id}: {resp.text}")
            else:
                _log_info(f"DB log OK for job {job_id} (status={status})")
    except Exception as e:
        _log_error(f"DB log error for job {job_id}: {e}")


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@app.function(
    image=image,
    gpu="T4",
    timeout=300,
    secrets=[
        modal.Secret.from_name("openrouter-secret"),
        modal.Secret.from_name("supabase-secret"),
        modal.Secret.from_name("naturalcad-api-key"),
    ],
)
@modal.fastapi_endpoint(method="POST")
def generate_cad_endpoint(payload: dict, request: Request):
    import os

    # Auth
    expected_key = os.environ.get("NATURALCAD_API_KEY")
    if not expected_key:
        raise HTTPException(status_code=503, detail={"error": "Service auth is not configured."})

    provided_key = request.headers.get("x-api-key", "")
    if not provided_key or not secrets.compare_digest(provided_key, expected_key):
        raise HTTPException(status_code=401, detail={"error": "Unauthorized"})

    client_ip = _client_ip(request)
    if not _allow_request(_REQUESTS_BY_IP, client_ip, _RATE_LIMIT_PER_IP, _RATE_WINDOW_SECONDS):
        raise HTTPException(status_code=429, detail={"error": "Rate limit exceeded for IP."})
    if not _allow_request(_REQUESTS_BY_KEY, provided_key, _RATE_LIMIT_PER_KEY, _RATE_WINDOW_SECONDS):
        raise HTTPException(status_code=429, detail={"error": "Rate limit exceeded for API key."})

    # Validate and normalise
    try:
        req = GenerateRequest(**payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"error": str(exc)})

    with _acquire_run_slot():
        return generate_cad.local(req.prompt, req.mode, req.output_type)


# ---------------------------------------------------------------------------
# Core generation function
# ---------------------------------------------------------------------------

_OUTPUT_RULES = {
    "3d_solid": (
        "Output goal: a solid 3D part. Use BuildPart, extrusions, and solid boolean operations. "
        "result must be a solid Shape (e.g. bp.part)."
    ),
    "surface": (
        "Output goal: a thin surface or shell, not a chunky solid. Prefer thin extrusions (1–2 mm) "
        "or surface constructs over solid primitives. result must be a valid exportable Shape."
    ),
    "2d_vector": (
        "Output goal: a 2D sketch profile (e.g. for laser cutting or DXF export). Use BuildSketch on Plane.XY. "
        "Extrude with a minimal thickness of 1 mm so the geometry exports as STL/STEP. "
        "result must be a Part (bp.part)."
    ),
    "1d_path": (
        "Output goal: a 1D path-style layout (linework/centerlines). Build the geometry from lines/arcs on Plane.XY. "
        "For compatibility with STL/STEP preview, give the path a minimal thickness (about 1 mm) by using a thin profile. "
        "result must be a Part (bp.part)."
    ),
}

_MODE_HINTS = {
    "part": "Mode: single continuous solid part.",
    "assembly": "Mode: assembly of multiple sub-parts. Combine with add() or position using Locations.",
    "sketch": "Mode: sketch/profile. Focus on the 2D outline; extrude minimally (1 mm) if a 3D export is needed.",
}

# Static system rules + knowledge base (build123d 0.10.0)
_SYSTEM_RULES = """\
Rules:
1. ONLY return valid Python code. No markdown formatting, no explanations.
2. ALWAYS import build123d using: from build123d import *
3. ALWAYS store the final Shape/Part in a variable named result.
4. ALWAYS specify the plane explicitly: with BuildSketch(Plane.XY):
5. Use the modern builder API: with BuildPart() as bp:
6. Do NOT use points= in Polygon(). Use positional args: Polygon([(0,0), (10,0), (5,8)]).
7. PolarLocations and GridLocations ARE context managers: with PolarLocations(radius, count):
   Do NOT wrap them inside Locations().
8. NEVER use standalone rotate() or translate(). Use with Locations((x, y, z)): or obj.rotate(Axis.Z, angle).
9. extrude() takes amount= (e.g. extrude(amount=10)) or both=True. Do NOT use start= or distance=.
10. extrude() must be called inside a BuildPart context, immediately after a BuildSketch block.
11. Keep geometry complexity bounded. Prefer a simplified form over many tiny repeated features.

Canonical skeleton (adapt dimensions and features to the request):
from build123d import *
with BuildPart() as bp:
    with BuildSketch(Plane.XY):
        Rectangle(60, 40)
    extrude(amount=10)
    with BuildSketch(bp.faces().sort_by(Axis.Z)[-1]):
        with PolarLocations(12, 4):
            Circle(4)
    extrude(amount=-8, mode=Mode.SUBTRACT)
result = bp.part

# KNOWLEDGE BASE — build123d 0.10.0 patterns:

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
    with BuildSketch(Plane.XY):
        Circle(60)
        Rectangle(20, 20, mode=Mode.SUBTRACT)
    extrude(amount=10)
result = p.part

# PATTERN 4: Multiple Holes using Locations
with BuildPart() as p:
    with BuildSketch(Plane.XY):
        Circle(80)
    extrude(amount=10)
    with BuildSketch(p.faces().sort_by(Axis.Z)[-1]):
        with Locations((20, 0), (-20, 0), (0, 20), (0, -20)):
            Cylinder(radius=5, height=10, mode=Mode.SUBTRACT)
result = p.part

# PATTERN 5: PolarLocations for holes in a circle
with BuildPart() as p:
    with BuildSketch(Plane.XY):
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
    with BuildSketch(Plane.XY):
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


@app.function(
    image=image,
    gpu="T4",
    timeout=300,
    secrets=[
        modal.Secret.from_name("openrouter-secret"),
        modal.Secret.from_name("supabase-secret"),
    ],
)
def generate_cad(prompt: str, mode: str = "part", output_type: str = "3d_solid"):
    """
    Core generation: prompt + mode + output_type -> LLM -> build123d exec -> Supabase upload.

    Returns a dict matching the API contract in the module docstring.
    """
    import os
    import uuid

    openrouter_api_key = os.environ.get("OPENROUTER_API_KEY")
    if not openrouter_api_key:
        return {"error": "OPENROUTER_API_KEY not found in environment secrets"}

    openrouter_api_url = os.environ.get("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions")
    openrouter_model = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-opus-4.7")
    log_generated_code = os.environ.get("NATURALCAD_LOG_CODE", "false").strip().lower() in {"1", "true", "yes", "on"}
    include_code_in_response = os.environ.get("NATURALCAD_INCLUDE_CODE_IN_RESPONSE", "false").strip().lower() in {"1", "true", "yes", "on"}
    store_glb = os.environ.get("NATURALCAD_STORE_GLB", "false").strip().lower() in {"1", "true", "yes", "on"}

    mode_hint = _MODE_HINTS.get(mode, _MODE_HINTS["part"])
    output_rule = _OUTPUT_RULES.get(output_type, _OUTPUT_RULES["3d_solid"])

    system_prompt = (
        "You are an expert Python developer for CAD code generation using the build123d library (version 0.10.0).\n"
        "Write Python code to create the 3D model requested by the user.\n\n"
        f"{mode_hint}\n"
        f"{output_rule}\n\n"
        + _SYSTEM_RULES
    )

    # First user turn: structured context block + raw request
    user_message = f"Mode: {mode}\nOutput: {output_type}\n\nUser request:\n{prompt}"

    run_id = str(uuid.uuid4())
    max_attempts = 3
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    for attempt in range(max_attempts):
        _log_info(f"LLM call {attempt + 1}/{max_attempts} | mode={mode} output_type={output_type}")
        try:
            headers = {
                "Authorization": f"Bearer {openrouter_api_key}",
                "Content-Type": "application/json",
            }
            referer = os.environ.get("OPENROUTER_REFERER", "")
            title = os.environ.get("OPENROUTER_TITLE", "NaturalCAD")
            if referer:
                headers["HTTP-Referer"] = referer
            if title:
                headers["X-Title"] = title

            payload = {
                "model": openrouter_model,
                "messages": messages,
                "max_tokens": 2048,  # 1024 could truncate assemblies or multi-step parts
                "temperature": 0.2,
            }

            with httpx.Client(timeout=180.0) as client:
                response = client.post(openrouter_api_url, headers=headers, json=payload)

            if response.status_code >= 400:
                _log_error(f"OpenRouter error {response.status_code}: {response.text[:500]}")
                return {"error": f"LLM provider unavailable ({response.status_code}). Please retry."}

            data = response.json()
            generated_code = (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
            if not generated_code:
                _log_error(f"OpenRouter empty content response: {str(data)[:500]}")
                return {"error": "LLM returned empty output. Please retry."}

            # Strip markdown fences (model sometimes ignores rule 1)
            if generated_code.startswith("```python"):
                generated_code = generated_code[9:]
            elif generated_code.startswith("```"):
                generated_code = generated_code[3:]
            if generated_code.endswith("```"):
                generated_code = generated_code[:-3]
            generated_code = generated_code.strip()
        except Exception as e:
            _log_error(f"LLM call failed: {e}")
            return {"error": "LLM call failed. Please retry."}

        if log_generated_code:
            _log_info(f"Generated code:\n{generated_code}")

        from build123d import Axis, ExportDXF, Unit, export_step, export_stl

        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "script.py"
            sanitized_code = _strip_build123d_imports(generated_code)
            script_path.write_text(sanitized_code)

            is_safe, safety_error = _validate_generated_code(sanitized_code)
            if not is_safe:
                err_short = f"Rejected by AST guard: {safety_error}"
                _log_error(err_short)
                if attempt < max_attempts - 1:
                    messages.append({"role": "assistant", "content": generated_code})
                    messages.append({
                        "role": "user",
                        "content": (
                            f"That code was blocked by safety guard ({safety_error}).\n"
                            "Return a safe build123d-only script with no imports and no filesystem/network/system calls."
                        ),
                    })
                    continue
                _log_job_to_supabase(run_id, prompt, mode, output_type, generated_code, "failed", err_short)
                return {"error": "Generated code was unsafe and was blocked."}

            exec_globals = {"__builtins__": _SAFE_BUILTINS.copy()}
            import build123d as _b3d
            for _name in dir(_b3d):
                if not _name.startswith("_"):
                    exec_globals[_name] = getattr(_b3d, _name)

            # Scrub secrets before exec so generated code cannot read them
            original_env = os.environ.copy()
            os.environ.pop("OPENROUTER_API_KEY", None)
            os.environ.pop("SUPABASE_URL", None)
            os.environ.pop("SUPABASE_SERVICE_ROLE_KEY", None)
            os.environ.pop("NATURALCAD_API_KEY", None)

            exec_success = False
            err_short = ""
            err_trace = ""
            try:
                _exec_with_timeout(sanitized_code, script_path, exec_globals)
                exec_success = True
            except Exception as e:
                import traceback as _tb
                err_short = f"{type(e).__name__}: {e}"
                err_trace = _tb.format_exc()
                _log_error(f"Execution failed: {err_short}")
            finally:
                os.environ.clear()
                os.environ.update(original_env)

            if exec_success:
                result_shape = exec_globals.get("result")
                if not result_shape:
                    err_short = "No 'result' variable found in generated code."
                    err_trace = err_short
                    exec_success = False

            if not exec_success:
                if attempt < max_attempts - 1:
                    _log_info("Retrying with error context...")
                    # Cap traceback to avoid blowing the context window
                    trace_snippet = err_trace[-2000:] if len(err_trace) > 2000 else err_trace
                    messages.append({"role": "assistant", "content": generated_code})
                    messages.append({
                        "role": "user",
                        "content": (
                            f"That code failed with the following error:\n{trace_snippet}\n\n"
                            "Fix the code and return only the corrected Python script, no markdown."
                        ),
                    })
                    continue
                else:
                    _log_job_to_supabase(run_id, prompt, mode, output_type, generated_code, "failed", err_short)
                    return {
                        "error": "Generation failed during CAD execution. Please refine your prompt and retry.",
                        "code": generated_code,
                    }

            # ----------------------------------------------------------------
            # Export: STL, STEP, GLB, DXF
            # ----------------------------------------------------------------
            shape = result_shape
            urls = {}
            stl_path = Path(tmpdir) / "output.stl"
            step_path = Path(tmpdir) / "output.step"
            glb_path = Path(tmpdir) / "output.glb"
            dxf_path = Path(tmpdir) / "output.dxf"

            try:
                export_stl(shape, str(stl_path))
                _log_info(f"STL exported: {stl_path.stat().st_size} bytes")
            except Exception as e:
                _log_error(f"STL export failed: {e}")
                stl_path = None

            try:
                export_step(shape, str(step_path))
                _log_info(f"STEP exported: {step_path.exists()}")
            except Exception as e:
                _log_error(f"STEP export failed: {e}")
                step_path = None

            try:
                if stl_path and stl_path.exists():
                    from trimesh import load_mesh
                    import trimesh.transformations as tf
                    import math

                    mesh = load_mesh(str(stl_path), force="mesh")
                    # Rotate to glTF Y-up convention
                    mesh.apply_transform(tf.rotation_matrix(-math.pi / 2, [1, 0, 0]))
                    mesh.export(str(glb_path))
                    _log_info(f"GLB exported: {glb_path.exists()}")
                else:
                    _log_info("Skipping GLB: no STL file")
            except Exception as e:
                _log_error(f"GLB export failed: {e}")

            try:
                if output_type in {"2d_vector", "1d_path"}:
                    exporter = ExportDXF(unit=Unit.MM)
                    if output_type == "1d_path":
                        exporter.add_shape(shape.edges())
                    else:
                        faces = shape.faces()
                        if faces:
                            top_face = faces.sort_by(Axis.Z)[-1]
                            wires = [top_face.outer_wire(), *list(top_face.inner_wires())]
                            exporter.add_shape(wires)
                        else:
                            exporter.add_shape(shape.edges())
                    exporter.write(str(dxf_path))
                    _log_info(f"DXF exported: {dxf_path.exists()}")
            except Exception as e:
                _log_error(f"DXF export failed: {e}")

            # ----------------------------------------------------------------
            # Upload to Supabase storage
            # ----------------------------------------------------------------
            file_pairs = [
                ("stl", stl_path, "model/stl"),
                ("step", step_path, "application/octet-stream"),
            ]
            if dxf_path.exists():
                file_pairs.append(("dxf", dxf_path, "application/dxf"))
            if store_glb:
                file_pairs.append(("glb", glb_path, "model/gltf-binary"))
            for fmt, file_path, content_type in file_pairs:
                if not file_path or not file_path.exists():
                    continue
                storage_key = f"runs/{run_id}/model.{fmt}"
                file_bytes = file_path.read_bytes()
                _log_info(f"Uploading {fmt}: {len(file_bytes)} bytes")
                try:
                    urls[fmt] = _upload_to_supabase(storage_key, file_bytes, content_type)
                except Exception as e:
                    _log_error(f"Upload error for {fmt}: {e}")

            _log_job_to_supabase(run_id, prompt, mode, output_type, generated_code, "completed")
            return {
                "job_id": run_id,
                "success": True,
                "model": openrouter_model,
                "urls": urls,
                "prompt": prompt,
                "generated_code": generated_code if include_code_in_response else "",
            }


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.function(image=image)
def health_check():
    """Verify build123d imports correctly."""
    from build123d import Box
    return {"status": "ok", "build123d": "0.10.0"}


if __name__ == "__main__":
    result = generate_cad.call("a simple bracket plate")
    print(result)
