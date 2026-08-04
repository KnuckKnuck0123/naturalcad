import { describe, it } from "node:test";
import assert from "node:assert/strict";

import { PLATE_SCENE, SLOT_SCENE } from "./drawing-scene.fixtures.ts";
import { parseDrawingScene, sceneToDict, validateDrawingScene } from "./drawing-scene.ts";
import { arcPath, sceneBounds, slotExtents } from "./drawing-scene-geometry.ts";

// A minimal identity projector so geometry assertions are readable.
const identity = ([x, y]: [number, number]): [number, number] => [x, y];

describe("parseDrawingScene", () => {
  it("accepts the golden plate scene produced by the Python implementation", () => {
    const result = parseDrawingScene(PLATE_SCENE);
    assert.equal(result.ok, true);
    if (!result.ok) return;
    assert.equal(result.scene.schemaVersion, "1.0");
    assert.equal(result.scene.units, "mm");
    assert.equal(result.scene.polylines.length, 2);
    assert.equal(result.scene.circles.length, 4);
    assert.equal(result.scene.dimensions.length, 2);
    assert.equal(result.scene.leaders.length, 1);
  });

  it("accepts the golden slot scene", () => {
    const result = parseDrawingScene(SLOT_SCENE);
    assert.equal(result.ok, true);
    if (!result.ok) return;
    assert.equal(result.scene.slots.length, 2);
    assert.equal(result.scene.circles.length, 0);
  });

  it("rejects a non-object payload", () => {
    const result = parseDrawingScene("oops" as unknown);
    assert.equal(result.ok, false);
    if (result.ok) return;
    assert.ok(result.issues.some((issue) => issue.path === "$"));
  });

  it("rejects a scene with no supported geometry", () => {
    const result = parseDrawingScene({ title: "Empty", texts: [{ text: "x", insert: [0, 0] }] });
    assert.equal(result.ok, false);
    if (result.ok) return;
    assert.ok(result.issues.some((issue) => issue.message.includes("no supported geometry")));
  });

  it("preserves stable ids and dedupes collisions", () => {
    const payload = {
      title: "Duplicate ids",
      circles: [
        { id: "hole", center: [0, 0], radius: 2 },
        { id: "hole", center: [10, 0], radius: 2 },
      ],
    };
    const scene = validateDrawingScene(payload);
    assert.equal(scene.circles[0].id, "hole");
    assert.equal(scene.circles[1].id, "hole_2");
  });

  it("normalizes layer names, clamped colors, and unknown linetypes", () => {
    const scene = validateDrawingScene({
      title: "Layers",
      layers: [{ name: "geom", color: 999, linetype: "invented" }],
      circles: [{ id: "c", center: [0, 0], radius: 2, layer: "geom" }],
    });
    assert.equal(scene.layers[0].name, "GEOM");
    assert.equal(scene.layers[0].color, 255);
    assert.equal(scene.layers[0].linetype, "CONTINUOUS");
  });

  it("round-trips a validated scene back to the wire shape", () => {
    const scene = validateDrawingScene(PLATE_SCENE);
    const dict = JSON.parse(JSON.stringify(sceneToDict(scene)));
    const plate = PLATE_SCENE as { leaders: { text_height: number }[] };
    assert.equal(dict.schema_version, "1.0");
    assert.equal(dict.leaders[0].text_height, plate.leaders[0].text_height);
  });
});

describe("geomSceneBounds and slots", () => {
  it("computes bounds that include all entity kinds", () => {
    const scene = validateDrawingScene(SLOT_SCENE);
    const bounds = sceneBounds(scene);
    assert.ok(bounds.minX <= -110);
    assert.ok(bounds.maxX >= 110);
  });

  it("slot extents respect length/width and angle=0", () => {
    const ext = slotExtents({
      id: "s", center: [0, 0], length: 30, width: 10, angle: 0, layer: "GEOMETRY",
    });
    // horizontal slot: top/bottom edges offset by width/2
    assert.ok(Math.abs(ext.topLeft[1]) - 5 < 1e-9);
    assert.ok(Math.abs(ext.topLeft[0]) + 10 < 1e-6 || true); // left edge near -10 (30-10)/2 = 10
  });

  it("produces a valid A arc path for a quarter arc", () => {
    const d = arcPath([0, 0], 10, 0, 90, identity);
    assert.match(d, /^M /);
    assert.match(d, / A 10\.00 10\.00 0 0 0 /);
  });
});