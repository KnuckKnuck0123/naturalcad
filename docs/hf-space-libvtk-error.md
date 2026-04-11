# OpenCascade (OCP) Missing Shared Library Error

**Issue:**
The HF Space Docker container builds correctly and the Gradio app runs, but the actual geometry generation subprocess fails with:
`ImportError: libvtkWrappingPythonCore3.10-9.3.so: cannot open shared object file: No such file or directory`

**Root Cause:**
`cadquery-ocp` (OpenCascade) from conda-forge has implicit C++ dependencies that aren't being satisfied by the base `continuumio/miniconda3:latest` (Debian-based) Docker image. Specifically, `libvtk` (Visualization Toolkit) components are missing at runtime.

**Why this happened:**
When installing `ocp` via `conda install -c conda-forge ocp`, Conda usually resolves and installs all required C++ shared libraries (like vtk, xorg, qt, etc). However, sometimes `conda-forge` packages assume the host system has certain graphical/X11 or VTK libraries pre-installed, or the conda environment path isn't exposing the `libvtk` binaries correctly to the subprocess `LD_LIBRARY_PATH`.

**Next Steps to Fix (Next Session):**
1. We need to identify exactly which system package provides `libvtkWrappingPythonCore3.10-9.3.so`. It might require installing VTK via conda explicitly (`conda install -c conda-forge vtk`), or installing it via `apt-get` in the Dockerfile.
2. Alternatively, using a different base image like `condaforge/miniforge3` instead of `continuumio/miniconda3` often resolves these hidden `conda-forge` shared library linking issues.
3. Once the VTK library issue is patched in the Dockerfile, the CAD engine will successfully render.

**Current Status:**
- UI: Working
- Docker Build: Passing
- Fallback Prompt Routing: Working
- CAD Execution: Failing on `libvtk` import

(Logged at 2026-04-10 22:25 PDT)