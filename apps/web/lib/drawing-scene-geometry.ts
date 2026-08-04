/**
 * Pure geometry + rendering math for DrawingScene, mirroring the Python
 * implementation in `apps/gradio-demo/app/drawing_core.py` (render_svg path).
 *
 * Kept separate from React so it is unit-testable without a DOM and so it can be
 * reused by any future exporter (SVG string, canvas, print layout).
 */

import type { DrawingScene, Point, SlotEntity } from "./drawing-scene.ts";

export interface Bounds {
  minX: number;
  minY: number;
  maxX: number;
  maxY: number;
}

/** Slot marching-corner points in world units, matching Python `_slot_points`. */
export function slotExtents(slot: SlotEntity): {
  topLeft: Point;
  topRight: Point;
  bottomRight: Point;
  bottomLeft: Point;
  leftCenter: Point;
  rightCenter: Point;
} {
  const angle = (slot.angle * Math.PI) / 180;
  const ux = Math.cos(angle);
  const uy = Math.sin(angle);
  const px = -uy;
  const py = ux;
  const radius = slot.width / 2;
  const centerDistance = Math.max(0, slot.length - slot.width) / 2;
  const [cx, cy] = slot.center;
  const left: Point = [cx - ux * centerDistance, cy - uy * centerDistance];
  const right: Point = [cx + ux * centerDistance, cy + uy * centerDistance];
  return {
    topLeft: [left[0] + px * radius, left[1] + py * radius],
    topRight: [right[0] + px * radius, right[1] + py * radius],
    bottomRight: [right[0] - px * radius, right[1] - py * radius],
    bottomLeft: [left[0] - px * radius, left[1] - py * radius],
    leftCenter: left,
    rightCenter: right,
  };
}

/** World-space bounding box of the whole scene, matching Python `scene_bounds`. */
export function sceneBounds(scene: DrawingScene): Bounds {
  const xs: number[] = [];
  const ys: number[] = [];
  const push = (x: number, y: number) => {
    xs.push(x);
    ys.push(y);
  };
  for (const entity of scene.polylines) for (const [x, y] of entity.points) push(x, y);
  for (const entity of scene.hatches) for (const [x, y] of entity.boundary) push(x, y);
  for (const entity of scene.leaders) for (const [x, y] of entity.points) push(x, y);
  for (const entity of scene.texts) push(...entity.insert);
  for (const entity of scene.dimensions) {
    push(...entity.start);
    push(...entity.end);
  }
  for (const entity of [...scene.circles, ...scene.arcs]) {
    push(entity.center[0] - entity.radius, entity.center[1] - entity.radius);
    push(entity.center[0] + entity.radius, entity.center[1] + entity.radius);
  }
  for (const slot of scene.slots) {
    const { topLeft, topRight, bottomRight, bottomLeft } = slotExtents(slot);
    for (const [x, y] of [topLeft, topRight, bottomRight, bottomLeft]) push(x, y);
  }
  if (xs.length === 0) return { minX: -100, minY: -100, maxX: 100, maxY: 100 };
  return {
    minX: Math.min(...xs),
    minY: Math.min(...ys),
    maxX: Math.max(...xs),
    maxY: Math.max(...ys),
  };
}

export interface ViewportMapping {
  /** fit-equal scale so the drawing does not distort */
  scale: number;
  /** projected coordinates (SVG y-down) for a world-space point */
  project: (point: Point) => Point;
}

/**
 * Build a fit-to-viewport projection. `size` = square pixel canvas; `padding`
 * keeps the drawing clear of the edge (matches Python `_svg_point`).
 */
export function fitViewport(bounds: Bounds, size: number, padding: number): ViewportMapping {
  const spanX = Math.max(bounds.maxX - bounds.minX, 1);
  const spanY = Math.max(bounds.maxY - bounds.minY, 1);
  const scale = Math.min((size - 2 * padding) / spanX, (size - 2 * padding) / spanY);
  const project = (point: Point): Point => [
    padding + (point[0] - bounds.minX) * scale,
    size - padding - (point[1] - bounds.minY) * scale,
  ];
  return { scale, project };
}

/** Format a number like Python's f-strings for stable, compact SVG output. */
export function num(value: number): string {
  return value.toFixed(2);
}

/** SVG path data for an arc (mirrors the Python renderer). */
export function arcPath(
  center: Point,
  radius: number,
  startAngle: number,
  endAngle: number,
  project: (point: Point) => Point,
): string {
  const rad = (deg: number) => (deg * Math.PI) / 180;
  const start = project([
    center[0] + radius * Math.cos(rad(startAngle)),
    center[1] + radius * Math.sin(rad(startAngle)),
  ]);
  const end = project([
    center[0] + radius * Math.cos(rad(endAngle)),
    center[1] + radius * Math.sin(rad(endAngle)),
  ]);
  const delta = ((endAngle - startAngle) % 360 + 360) % 360;
  const large = delta > 180 ? 1 : 0;
  return `M ${num(start[0])},${num(start[1])} A ${num(radius)} ${num(radius)} 0 ${large} 0 ${num(end[0])},${num(end[1])}`;
}

/** SVG path string for an obround slot (mirrors Python's slot rendering). */
export function slotPath(slot: SlotEntity, scale: number, project: (point: Point) => Point): string {
  const { topLeft, topRight, bottomRight, bottomLeft } = slotExtents(slot);
  const tl = project(topLeft);
  const tr = project(topRight);
  const br = project(bottomRight);
  const bl = project(bottomLeft);
  const radius = num((slot.width / 2) * scale);
  return (
    `M ${num(tl[0])},${num(tl[1])} L ${num(tr[0])},${num(tr[1])} ` +
    `A ${radius},${radius} 0 0 1 ${num(br[0])},${num(br[1])} ` +
    `L ${num(bl[0])},${num(bl[1])} ` +
    `A ${radius},${radius} 0 0 1 ${num(tl[0])},${num(tl[1])} Z`
  );
}