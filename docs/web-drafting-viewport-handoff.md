# Web 2D Drafting Viewport — Foundation Handoff

## Status: 2026-08-03

Delivered a self-contained TypeScript mirror of the `DrawingScene 1.0` contract plus
a React SVG drafting viewport. Nothing is wired into the running app yet — this is
the foundation for routing `2d_vector` projects into a drafting workspace.

## What was added (all under `apps/web`)

| File | Purpose |
| --- | --- |
| `lib/drawing-scene.ts` | TS types + runtime validator (`parseDrawingScene`, `validateDrawingScene`, `sceneToDict`, `sceneToJson`). Mirrors `apps/gradio-demo/app/drawing_core.py` validation + normalization semantics 1:1. |
| `lib/drawing-scene-geometry.ts` | Pure geometry/rendering math mirroring the Python renderer: `sceneBounds`, `fitViewport`, `slotExtents`, `arcPath`, `slotPath`. DOM-free, unit-testable. |
| `lib/drawing-scene.fixtures.ts` | Two golden wire payloads captured from the Python `build_fallback_scene` output (plate scene + slot scene), plus the re-generation command in the header. |
| `lib/drawing-scene.test.ts` | 10 focused tests (validator, dedupe, normalization, round-trip, bounds, slot extents, arc path). Runs on Node 25's native TS runner: `npm run web:test`. |
| `components/workspace/drafting-viewport-2d.tsx` | `DraftingViewport2D` — renders a validated scene as React SVG elements (polylines, circles, arcs, slots, hatches, text, linear dimensions, leaders). Validates defensively at render time; never injects raw model SVG. |

Verified:
- `npm run web:typecheck` — clean
- `npm run web:build` — clean (6/6 static routes)
- `npm run web:test` — 10/10 pass
- SSR smoke render confirmed plate + slot scenes produce correct `data-entity-id`-tagged SVG, invalid payloads render a safe "INVALID DRAWING SCENE" state, and `null` renders "NO DRAWING SCENE".
- TS `sceneToDict` round-trips byte-for-byte against the Python `scene_to_json` output for the golden fixtures.

## Contract boundary

The validator accepts the exact wire shape the backend emits (snake_case keys:
`schema_version`, `start_angle`, `text_height`, etc.). The normalized in-memory
`DrawingScene` uses camelCase; `sceneToDict`/`sceneToJson` convert back to the
snake_case wire shape. Only validated drawing intent lives in the scene.

## Integration seam (for the future 2D workspace)

Per `docs/drawing-scene-v1.md`, the main app will route by project `output_type`:

- `2d_vector` → DrawingScene + `DraftingViewport2D` + DXF/SVG/JSON exports
- `3d_solid` → current spec + `CADViewport` (GLB) + STEP/STL/GLB exports

Exact wiring point: `apps/web/components/workspace/workspace-page.tsx` currently
renders `<CADViewport url={viewportUrl} .../>` at line ~307. To switch the viewport
by output type, add a branch such as:

```tsx
{project.output_type === "2d_vector"
  ? <DraftingViewport2D scene={scenePayload} />
  : <CADViewport url={viewportUrl} autoRotate={autoRotate} tone={viewerTone} resetToken={viewerResetToken} />}
```

Where `scenePayload` comes from the version's DrawingScene JSON (the worker must
expose the `<run_id>.scene.json` artifact or the spec's `geometry` payload, not the
`glb` artifact).

Deliberately NOT done (per task scope):
- not wired into `WorkspacePage` / any page
- no raw model SVG path (`dangerouslySetInnerHTML`) — never add one
- no HF prototype changes
- no backend dispatch changes
- 3D app behavior untouched

## Files intentionally left untouched

`apps/gradio-demo/*` (HF prototype), `apps/web/app/*` routes, `apps/web/components/workspace/workspace-page.tsx`,
`apps/web/components/workspace/cad-viewport.tsx`, backend worker dispatch.

## Runbook

```bash
npm run web:typecheck   # tsc --noEmit over apps/web
npm run web:test        # node --test (Node 25+, no extra deps)
npm run web:build       # next build
```

Regenerate fixtures:

```bash
.venv/bin/python -c 'import sys; sys.path.insert(0,"apps/gradio-demo/app");
from drawing_core import build_fallback_scene, scene_to_json;
print(scene_to_json(build_fallback_scene(PROMPT, "mm")))'
```

## Next steps (owner: web-side)

1. Backend: expose the validated DrawingScene (scene JSON) on the version artifact
   or spec for `2d_vector` projects.
2. Wire the output-type branch in `workspace-page.tsx`.
3. Add pan/zoom + layer visibility to `DraftingViewport2D` once it's live.
