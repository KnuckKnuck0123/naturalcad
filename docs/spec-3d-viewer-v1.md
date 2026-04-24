# NaturalCAD 3D Viewer — Product Spec (v1)

Status: Draft
Owner: NaturalCAD
Date: 2026-04-23

## 1) Product Intent
Build a first-party 3D viewer optimized for AI-generated CAD iteration, not a generic model viewer.

## 2) Goals
1. Fast preview of generated outputs (GLB first, STL fallback).
2. Clear iteration workflow (compare versions, inspect changes, keep context in conversation).
3. Production-ready CAD handoff confidence (visual QA before STEP download).
4. Consistent UX across guest and signed-in users.

## 3) Non-Goals (v1)
- Full parametric CAD editing in viewer.
- Native STEP B-Rep rendering in-browser (defer to v2).
- Multi-user live collaboration.
- Plugin ecosystem.

## 4) Primary User Flows
1. Generate part → auto-open in viewer → orbit/pan/zoom → download STEP/STL.
2. Continue iteration from prior version and visually verify delta.
3. Tune slider params and see near-real-time geometry refresh.
4. Upload reference image, generate result, inspect against target intent.

## 5) Functional Requirements (v1)

### A. Viewport Core
- Perspective + orthographic camera toggle.
- Orbit, pan, zoom, fit-to-model.
- Grid + axis gizmo toggle.
- Background presets (light/dark/studio black).

### B. Model Handling
- Input priority: `glb` → `stl` fallback.
- Async loading with progress + failure state.
- Auto-recenter and scale normalization.
- Version switcher loads prior generated artifacts.

### C. Inspection Tools
- Wireframe toggle.
- Flat/smooth shading toggle.
- Section clip plane (single plane v1).
- Bounding box dimensions readout.

### D. Iteration UX
- Left panel: prompt + conversation history + model profile (Fast/Balanced/Quality).
- Version timeline with parent/child lineage.
- “Compare mode” (A/B quick swap, not side-by-side in v1).

### E. Parameter Controls
- Slider panel fed by backend `parameters` payload.
- Apply updates triggers param-version patch route.
- Show changed parameter badges per version.

### F. Export Actions
- Primary CTA: Download STEP.
- Secondary: Download STL / GLB when available.
- Disabled states when artifact missing.

## 6) UX Requirements
- First interactive frame target: < 2s for typical GLB.
- Viewer interactions should remain smooth (> 30 FPS on common laptop hardware).
- Clear empty/loading/error states (no silent failures).
- Mobile is view-only in v1 (generation allowed, advanced inspect tools hidden).

## 7) Technical Architecture (v1)
- Frontend stack: React + Three.js (React Three Fiber recommended).
- Viewer module boundary:
  - `viewer-core` (scene/camera/lights/loaders)
  - `viewer-ui` (toolbars, toggles, overlays)
  - `viewer-data` (version/artifact/session wiring)
- API dependencies:
  - `GET /v1/projects/{id}`
  - `POST /v1/projects/{id}/generate`
  - `PATCH /v1/projects/{id}/versions/{version_id}/parameters`
  - `GET /v1/models`

## 8) Telemetry / Product Signals
Track:
- time-to-first-render
- render errors by file type
- export clicks by format
- compare-mode usage
- slider update success/failure

## 9) Security / Abuse Considerations
- Only load trusted artifact URLs from our storage domain list.
- File size caps and timeout on loaders.
- Sanitized error messages to user.

## 10) Milestones

### Milestone V1-A (Core Viewer)
- Load GLB/STL, camera controls, fit, shading toggles, export buttons.

### Milestone V1-B (Iteration Integration)
- Version switcher, conversation-linked view updates, model profile selector.

### Milestone V1-C (Param + Inspect)
- Slider panel integration, clip plane, dimensions readout, A/B quick compare.

## 11) Acceptance Criteria (Release Gate)
- User can generate and inspect at least 5 consecutive versions without reload breakage.
- STEP export remains accessible and accurate from every completed version.
- Parameter update creates a new version and reflects in viewer.
- Error states are visible and recoverable.
