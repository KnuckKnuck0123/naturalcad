# Hugging Face Space Build Log

**Space URL:** https://huggingface.co/spaces/noahtheboa/naturalcad  
**GitHub:** https://github.com/KnuckKnuck0123/naturalcad  
**Started:** 2026-04-10 21:33 PDT

---

## Build Attempts

### Attempt 1 - Initial push
**Commit:** `5955d34`  
**Error:** `RUNTIME_ERROR`  
**Cause:** Python 3.13 incompatibility with `pydub`/`audioop`  
**Fix:** Pinned `python_version: "3.10"` in README.md metadata

---

### Attempt 2 - Python version parse error
**Commit:** `1d01b63`  
**Error:** `BUILD_ERROR` - `docker.io/library/python:3.1: not found`  
**Cause:** YAML parsed `python_version: 3.10` as float `3.1`  
**Fix:** Quoted the version: `python_version: "3.10"`

---

### Attempt 3 - huggingface_hub import error
**Commit:** `9b05b0f`  
**Error:** `RUNTIME_ERROR` - `ImportError: cannot import name 'HfFolder' from 'huggingface_hub'`  
**Cause:** Gradio and `huggingface_hub` version mismatch  
**Fix:** Pinned `huggingface_hub<1.0` in requirements.txt

---

### Attempt 4 - Gradio launch css error
**Commit:** `f8903b8`  
**Error:** `RUNTIME_ERROR` - `TypeError: Blocks.launch() got an unexpected keyword argument 'css'`  
**Cause:** Passing `css=` to `demo.launch()` unsupported in this Gradio version  
**Fix:** Removed the `css` kwarg from `demo.launch()`

---

### Attempt 5 - gradio_client schema error
**Commit:** `61d9330`  
**Error:** `RUNTIME_ERROR` - `TypeError: argument of type 'bool' is not iterable` in `gradio_client/utils.py`  
**Cause:** Gradio and `gradio_client` version mismatch  
**Fix:** Pinned both to known-compatible versions:
- `gradio==4.44.1`
- `gradio_client==1.0.3`
- `huggingface_hub==0.25.0`

---

### Attempt 6 - localhost launch error
**Commit:** `109b3cb`  
**Error:** `RUNTIME_ERROR` - `ValueError: When localhost is not accessible, a shareable link must be created`  
**Cause:** Calling `demo.launch()` directly in HF Space  
**Fix:** Removed `if __name__ == '__main__': demo.launch(...)` block - HF runs the demo object itself

---

### Attempt 7 - build123d/cadquery-ocp build failure
**Commit:** `109b3cb` (current)  
**Error:** `BUILD_ERROR` - pip install fails during `build123d` dependency resolution  
**Cause:** `cadquery-ocp` lacks compatible manylinux wheels for HF's Docker runtime  
**Status:** BLOCKED  
**Proposed fix:** Switch to Docker SDK with custom Dockerfile for full environment control

---

## Root Cause Analysis

The Gradio SDK runtime on Hugging Face Spaces:
- Uses a pre-built Docker image
- Has limited control over system dependencies
- Cannot easily install heavy native libraries like OpenCascade (`cadquery-ocp`)

`build123d` depends on:
- `cadquery-ocp>=7.8,<7.9` - OpenCascade bindings (heavy native deps)
- `lib3mf>=2.4.1` - 3MF file format support
- `scipy`, `numpy`, `trimesh`, etc.

These require:
- Compiled C++ libraries
- Specific manylinux wheel availability
- System-level packages that HF's default Gradio image doesn't provide

---

## Recommended Path Forward

**Switch to Docker SDK:**
- Create a `Dockerfile` that:
  - Uses `python:3.10-slim` or similar as base
  - Installs system dependencies for OpenCascade
  - Pins all Python deps in one controlled environment
  - Runs the Gradio app with proper configuration
- Change Space SDK from `gradio` to `docker`
- This gives full control over the build environment

---

## Files Modified During Debugging

- `README.md` - Added `python_version: "3.10"` and fixed metadata
- `requirements.txt` - Pinned Gradio, gradio_client, huggingface_hub versions
- `apps/gradio-demo/requirements.txt` - Same version pins
- `app.py` - Removed `demo.launch()` call for HF compatibility
- `.hfignore` - Created for Space-specific ignores
- `docs/hf-space-build-log.md` - This file

---

## Timeline

| Time (PDT) | Event |
|------------|-------|
| 21:33 | Space created, first push |
| 21:34 | Runtime error: Python 3.13 / pydub |
| 21:37 | Pinned Python 3.10, push rejected (version parse) |
| 21:38 | Quoted Python version, new build |
| 21:38 | Runtime error: huggingface_hub import |
| 21:39 | Pinned huggingface_hub, new build |
| 21:40 | Runtime error: Gradio css kwarg |
| 21:43 | Removed css kwarg, new build |
| 21:43 | Runtime error: gradio_client schema |
| 21:44 | Pinned gradio + gradio_client, new build |
| 21:46 | Runtime error: localhost launch |
| 21:47 | Removed demo.launch(), new build |
| 21:48 | Build error: cadquery-ocp / build123d deps |
| 21:49 | Switching to Docker SDK (proposed) |

---

## Next Steps

1. Create `Dockerfile` for NaturalCAD
2. Update Space SDK from `gradio` to `docker`
3. Push and rebuild with full environment control
4. Verify build123d imports correctly
5. Test end-to-end prompt → geometry flow