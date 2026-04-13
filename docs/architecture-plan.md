# NaturalCAD Architecture Plan

## Current State (2026-04-12)

We successfully pivoted away from a complex (and broken) Fly.io worker and Hugging Face Docker setup, replacing the backend engine entirely with **Modal**.

### What's Working
- ✅ **LLM Code Generation**: Using `Qwen/Qwen2.5-Coder-32B-Instruct` via Hugging Face Serverless Inference API inside Modal.
- ✅ **CAD Execution Engine**: Modal spins up a `python:3.10-slim` container with proper Linux OpenGL libraries (`libgl1`, `libglib2.0-0`, etc). `build123d` runs locally on the T4 GPU container.
- ✅ **Artifact Upload**: Modal container runs CAD, creates STL, STEP, and a browser-ready GLB using `trimesh`, and uploads directly to Supabase Storage, returning public URLs.
- ✅ **HF Spaces UI**: Front-end UI remains on Hugging Face Spaces.

### What's Deprecated
- ❌ Fly.io backend routing and worker loops (too much complexity/overhead for MVP).
- ❌ Hugging Face native Docker CAD execution (lacks host graphics libs for VTK).

---

## Target Architecture

```
┌─────────────┐
│   User      │────▶ HF Spaces (Gradio UI)
│  Prompt    │
└─────────────┘
      │
      ▼
┌───────────────────────────────────────┐
│              Modal Web Endpoint        │
│                                       │
│ 1. Calls HF Inference API (Qwen 2.5)  │
│ 2. LLM writes build123d Python script │
│ 3. Executes script on Modal Container │
│ 4. Generates STL + STEP + GLB preview │
│ 5. Uploads files to Supabase          │
│ 6. Returns 3 URLs back to HF Space    │
└───────────────────────────────────────┘
      │
      ▼
┌──────────────┐
│  Supabase    │
│  Storage     │
└──────────────┘
```

## Services

| Service | Role | Cost | Status |
|---------|------|-----|--------|
| **HF Spaces** | UI/Frontend | Free tier | ✅ Ready |
| **Modal** | Web API + LLM call + CAD Execution | Pay-per-use GPU | ✅ Ready |
| **HF Inference API**| LLM (text→code) | Free within limits | ✅ Ready |
| **Supabase** | DB + Storage | Free tier | ✅ Ready |

---

## Implementation Order

1. ✅ **Create Modal function** for CAD execution
2. ✅ **Add LLM generation via HF** to the Modal container
3. ✅ **Add Supabase Artifact Upload** returning public URL
4. 🔲 **Deploy Modal Web Endpoint** to get a live URL
5. 🔲 **Wire HF Spaces** to hit the Modal endpoint, parsing out the STL, STEP, and GLB urls into the Gradio UI.

---

*Updated: 2026-04-12*