"""Modal deploy test for the 2D DrawingScene emission.

Imports the cad-worker app and invokes execute_generated_cad with a hardcoded
build123d 2D script (rectangle + hole) against output_type="2d_vector". Asserts
the returned artifacts dict contains a "scene" key whose bytes parse as a valid
DrawingScene 1.0 payload.

No OpenRouter/LLM spend — this exercises only the execution + scene-converter path.
Run from the repo root:
    python apps/cad-worker/scripts/deploy_test_2d.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKER_DIR = REPO_ROOT / "apps" / "cad-worker"
sys.path.insert(0, str(WORKER_DIR))

import main as worker  # noqa: E402

# A minimal build123d 2D sketch extruded 1mm — the pattern the worker expects
# for output_type="2d_vector". Produces a 100x60 rectangle with a 10-radius hole.
TWO_D_SCRIPT = """
from build123d import *

with BuildPart() as p:
    with BuildSketch(Plane.XY) as s:
        Rectangle(100, 60)
        with Locations((50, 25)):
            Circle(10, mode=Mode.SUBTRACT)
    extrude(amount=1)
result = p.part
"""


def main() -> int:
    print("[*] Deploying naturalcad app to Modal (image build may take a few minutes)...")
    print("[*] Invoking execute_generated_cad(output_type='2d_vector') with a 2D rectangle+hole script")

    with worker.app.run():
        result = worker.execute_generated_cad.remote(TWO_D_SCRIPT, "2d_vector")

    if not result.get("success"):
        print("[!] execute_generated_cad failed:")
        print(json.dumps(result, indent=2)[:800])
        return 1

    artifacts = result.get("artifacts", {})
    print(f"[+] execution succeeded. artifact keys: {sorted(artifacts.keys())}")

    if "scene" not in artifacts:
        print("[!] No scene artifact emitted for 2d_vector run.")
        print("    artifacts:", {k: f"{len(v)} bytes" for k, v in artifacts.items()})
        return 1

    scene_bytes = artifacts["scene"]
    scene = json.loads(scene_bytes.decode("utf-8"))
    print(f"[+] scene.json emitted: {len(scene_bytes)} bytes")
    print(f"    title:   {scene.get('title')}")
    print(f"    units:   {scene.get('units')}")
    print(f"    schema:  {scene.get('schema_version')}")
    print(f"    polylines: {len(scene.get('polylines', []))}")
    print(f"    circles:   {len(scene.get('circles', []))}")
    print(f"    arcs:      {len(scene.get('arcs', []))}")

    polys = scene.get("polylines", [])
    if not polys:
        print("[!] FAIL: no polylines in emitted scene")
        return 1
    circs = scene.get("circles", [])
    if len(circs) != 1:
        print(f"[!] FAIL: expected exactly 1 circle (the hole), got {len(circs)}")
        return 1
    # Circle center should be at (50, 25) within tolerance — the hole location.
    cx, cy = circs[0]["center"]
    if abs(cx - 50.0) > 0.01 or abs(cy - 25.0) > 0.01:
        print(f"[!] FAIL: circle center ({cx}, {cy}) != expected (50, 25)")
        return 1
    if abs(circs[0]["radius"] - 10.0) > 0.001:
        print(f"[!] FAIL: circle radius {circs[0]['radius']} != expected 10.0")
        return 1

    print("[✓] Modal deploy test PASSED — scene converter emits a valid DrawingScene end-to-end.")
    print(f"    polyline points: {len(polys[0]['points'])}, closed: {polys[0]['closed']}")
    print(f"    circle: center=({cx}, {cy}), radius={circs[0]['radius']}")
    print("    artifact sizes:",
          ", ".join(f"{k}={len(v)}B" for k, v in artifacts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())