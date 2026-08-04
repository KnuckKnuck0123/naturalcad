/**
 * DrawingScene 1.0 — TypeScript mirror of the portable NaturalCAD 2D contract.
 *
 * The authoritative implementation lives in `apps/gradio-demo/app/drawing_core.py`.
 * This module mirrors its validation + normalization semantics so the web app can
 * consume the same `<run_id>.scene.json` artifacts (and future 2D dispatch output)
 * without trusting raw model JSON.
 *
 * Boundary: the scene carries only validated drawing intent (schema, title, units,
 * layers, typed entities). Prompts, images, usage, run IDs, logs and storage stay
 * outside the scene.
 */

export const SCHEMA_VERSION = "1.0";
export const COORDINATE_SYSTEM = "XY_RIGHT_HANDED";

export const UNITS = ["mm", "cm", "m", "in", "ft"] as const;
export type Unit = (typeof UNITS)[number];

export const ALLOWED_LINETYPES = new Set([
  "CONTINUOUS",
  "CENTER",
  "CENTER2",
  "DASHED",
  "DASHED2",
  "HIDDEN",
]);

export const ALLOWED_HATCH_PATTERNS = new Set(["SOLID", "ANSI31"]);

export const REFERENCE_NOTE = "More reference dimensions = more accurate output.";

/** Bounds that mirror the Python hard caps per collection. */
export const LIMITS = {
  layers: 12,
  polylines: 32,
  circles: 32,
  arcs: 32,
  slots: 24,
  hatches: 16,
  texts: 24,
  dimensions: 24,
  leaders: 24,
  points: 64,
  titleChars: 120,
  textChars: 500,
  dimTextChars: 120,
} as const;

export type Point = [number, number];

export interface LayerStyle {
  name: string;
  color: number;
  linetype: string;
}

export interface PolylineEntity {
  id: string;
  points: Point[];
  layer: string;
  closed: boolean;
}

export interface CircleEntity {
  id: string;
  center: Point;
  radius: number;
  layer: string;
}

export interface ArcEntity {
  id: string;
  center: Point;
  radius: number;
  startAngle: number;
  endAngle: number;
  layer: string;
}

export interface SlotEntity {
  id: string;
  center: Point;
  length: number;
  width: number;
  angle: number;
  layer: string;
}

export interface HatchEntity {
  id: string;
  boundary: Point[];
  layer: string;
  pattern: string;
}

export interface TextEntity {
  id: string;
  text: string;
  insert: Point;
  height: number;
  layer: string;
}

export interface LinearDimensionEntity {
  id: string;
  start: Point;
  end: Point;
  offset: number;
  layer: string;
  angle: number;
  text: string | null;
}

export interface LeaderEntity {
  id: string;
  points: Point[];
  text: string;
  textHeight: number;
  layer: string;
}

/**
 * Normalized portable scene. All entity collections are arrays; entity IDs are
 * unique across the whole scene. `schemaVersion`/`coordinateSystem` are always
 * the known constants after validation.
 */
export interface DrawingScene {
  title: string;
  units: Unit;
  schemaVersion: string;
  coordinateSystem: string;
  layers: LayerStyle[];
  polylines: PolylineEntity[];
  circles: CircleEntity[];
  arcs: ArcEntity[];
  slots: SlotEntity[];
  hatches: HatchEntity[];
  texts: TextEntity[];
  dimensions: LinearDimensionEntity[];
  leaders: LeaderEntity[];
}

/** A single human-checkable validity problem. */
export interface DraftingValidationIssue {
  path: string;
  message: string;
}

export type ParseResult =
  | { ok: true; scene: DrawingScene }
  | { ok: false; issues: DraftingValidationIssue[] };

export class DrawingSceneValidationError extends Error {
  readonly issues: DraftingValidationIssue[];
  constructor(issues: DraftingValidationIssue[]) {
    super(`DrawingScene is invalid (${issues.length} issue${issues.length === 1 ? "" : "s"}).`);
    this.name = "DrawingSceneValidationError";
    this.issues = issues;
  }
}

function isPlainObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function strictNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value))) {
    return Number(value);
  }
  return null;
}

function coerceFloat(value: unknown, fallback: number): number {
  const parsed = strictNumber(value);
  if (parsed === null) return fallback;
  return Number.isFinite(parsed) ? parsed : fallback;
}

function coerceBool(value: unknown, fallback = false): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") return ["1", "true", "yes", "on"].includes(value.trim().toLowerCase());
  return fallback;
}

function safeName(value: unknown, fallback: string): string {
  const candidate = String(value ?? "")
    .trim()
    .replace(/[^A-Za-z0-9_-]+/g, "_")
    .slice(0, 48);
  return candidate || fallback;
}

function layerName(value: unknown, fallback: string): string {
  return safeName(value, fallback).toUpperCase();
}

function entityId(prefix: string, index: number, value: unknown): string {
  return safeName(value, `${prefix}_${String(index + 1).padStart(3, "0")}`);
}

function coercePoint(value: unknown): Point | null {
  if (!Array.isArray(value) || value.length !== 2) return null;
  const x = strictNumber(value[0]);
  const y = strictNumber(value[1]);
  if (x === null || y === null) return null;
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
  return [x, y];
}

function coercePoints(value: unknown, minimum: number): Point[] {
  if (!Array.isArray(value)) return [];
  const points: Point[] = [];
  for (const item of value.slice(0, LIMITS.points)) {
    const point = coercePoint(item);
    if (point) points.push(point);
  }
  return points.length >= minimum ? points : [];
}

const DEFAULT_LAYERS: LayerStyle[] = [
  { name: "GEOMETRY", color: 7, linetype: "CONTINUOUS" },
  { name: "CENTER", color: 4, linetype: "CENTER" },
  { name: "HATCH", color: 8, linetype: "CONTINUOUS" },
  { name: "DIMENSIONS", color: 2, linetype: "CONTINUOUS" },
  { name: "TEXT", color: 3, linetype: "CONTINUOUS" },
  { name: "ANNOTATION", color: 6, linetype: "CONTINUOUS" },
];

function normalizeLayers(value: unknown): LayerStyle[] {
  if (!Array.isArray(value) || value.length === 0) return [...DEFAULT_LAYERS];
  const layers: LayerStyle[] = [];
  for (const item of value.slice(0, LIMITS.layers)) {
    if (!isPlainObject(item)) continue;
    const name = layerName(item.name, "");
    if (!name) continue;
    const rawColor = strictNumber(item.color) ?? 7;
    const color = Math.max(1, Math.min(255, Math.trunc(rawColor)));
    const rawLinetype = String(item.linetype ?? "CONTINUOUS").trim().toUpperCase();
    const linetype = ALLOWED_LINETYPES.has(rawLinetype) ? rawLinetype : "CONTINUOUS";
    layers.push({ name, color, linetype });
  }
  return layers.length > 0 ? layers : [...DEFAULT_LAYERS];
}

function normalizeUnits(value: unknown, fallback: Unit): Unit {
  const candidate = String(value ?? fallback).trim().toLowerCase();
  return (UNITS as readonly string[]).includes(candidate) ? (candidate as Unit) : fallback;
}

/** Normalize an arc angle into [0, 360) (matches Python's `% 360`). */
function normalizeAngleDegrees(value: number): number {
  return ((value % 360) + 360) % 360;
}

/**
 * Validate + normalize an arbitrary payload into a `DrawingScene`.
 *
 * Returns a `ParseResult`. Use `validateDrawingScene` for the throwing variant.
 * Mirrors `drawing_core.scene_from_payload`: bad entities are dropped, fields are
 * coerced to safe values, layers are normalized/backfilled, and the scene must
 * contain at least one supported *geometry* entity (polyline / circle / arc / slot).
 */
export function parseDrawingScene(input: unknown, requestedUnits: Unit = "mm"): ParseResult {
  if (!isPlainObject(input)) {
    return {
      ok: false,
      issues: [{ path: "$", message: "Drawing scene must be a JSON object" }],
    };
  }

  const issues: DraftingValidationIssue[] = [];
  const report = (path: string, message: string) => issues.push({ path, message });

  const title = String(input.title ?? "NaturalCAD 2D Draft").slice(0, LIMITS.titleChars);
  const units = normalizeUnits(input.units, requestedUnits);

  const scene: DrawingScene = {
    title,
    units,
    schemaVersion: SCHEMA_VERSION,
    coordinateSystem: COORDINATE_SYSTEM,
    layers: normalizeLayers(input.layers),
    polylines: [],
    circles: [],
    arcs: [],
    slots: [],
    hatches: [],
    texts: [],
    dimensions: [],
    leaders: [],
  };

  const listOf = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);

  listOf(input.polylines)
    .slice(0, LIMITS.polylines)
    .forEach((raw, index) => {
      if (!isPlainObject(raw)) return;
      const points = coercePoints(raw.points, 2);
      if (!points.length) return;
      scene.polylines.push({
        id: entityId("polyline", index, raw.id),
        points,
        layer: layerName(raw.layer, "GEOMETRY"),
        closed: coerceBool(raw.closed),
      });
    });

  listOf(input.circles)
    .slice(0, LIMITS.circles)
    .forEach((raw, index) => {
      if (!isPlainObject(raw)) return;
      const center = coercePoint(raw.center);
      const radius = coerceFloat(raw.radius, 0);
      if (!center || radius <= 0) {
        if (center && !strictNumber(raw.radius) && raw.radius !== undefined) {
          report(`$.circles[${index}].radius`, "radius must be a positive finite number");
        }
        return;
      }
      scene.circles.push({
        id: entityId("circle", index, raw.id),
        center,
        radius,
        layer: layerName(raw.layer, "GEOMETRY"),
      });
    });

  listOf(input.arcs)
    .slice(0, LIMITS.arcs)
    .forEach((raw, index) => {
      if (!isPlainObject(raw)) return;
      const center = coercePoint(raw.center);
      const radius = coerceFloat(raw.radius, 0);
      if (!center || radius <= 0) return;
      scene.arcs.push({
        id: entityId("arc", index, raw.id),
        center,
        radius,
        startAngle: normalizeAngleDegrees(coerceFloat(raw.start_angle, 0)),
        endAngle: normalizeAngleDegrees(coerceFloat(raw.end_angle, 90)),
        layer: layerName(raw.layer, "GEOMETRY"),
      });
    });

  listOf(input.slots)
    .slice(0, LIMITS.slots)
    .forEach((raw, index) => {
      if (!isPlainObject(raw)) return;
      const center = coercePoint(raw.center);
      const length = coerceFloat(raw.length, 0);
      const width = coerceFloat(raw.width, 0);
      if (!center || !(length >= width && width > 0)) return;
      scene.slots.push({
        id: entityId("slot", index, raw.id),
        center,
        length,
        width,
        angle: coerceFloat(raw.angle, 0),
        layer: layerName(raw.layer, "GEOMETRY"),
      });
    });

  listOf(input.hatches)
    .slice(0, LIMITS.hatches)
    .forEach((raw, index) => {
      if (!isPlainObject(raw)) return;
      const boundary = coercePoints(raw.boundary, 3);
      if (!boundary.length) return;
      const pattern = String(raw.pattern ?? "SOLID").trim().toUpperCase();
      scene.hatches.push({
        id: entityId("hatch", index, raw.id),
        boundary,
        layer: layerName(raw.layer, "HATCH"),
        pattern: ALLOWED_HATCH_PATTERNS.has(pattern) ? pattern : "SOLID",
      });
    });

  listOf(input.texts)
    .slice(0, LIMITS.texts)
    .forEach((raw, index) => {
      if (!isPlainObject(raw)) return;
      const insert = coercePoint(raw.insert);
      if (!insert) return;
      scene.texts.push({
        id: entityId("text", index, raw.id),
        text: String(raw.text ?? "").slice(0, LIMITS.textChars),
        insert,
        height: Math.max(0.1, coerceFloat(raw.height, 3)),
        layer: layerName(raw.layer, "TEXT"),
      });
    });

  listOf(input.dimensions)
    .slice(0, LIMITS.dimensions)
    .forEach((raw, index) => {
      if (!isPlainObject(raw)) return;
      const start = coercePoint(raw.start);
      const end = coercePoint(raw.end);
      if (!start || !end || (start[0] === end[0] && start[1] === end[1])) return;
      const text = raw.text === undefined || raw.text === null ? null : String(raw.text).slice(0, LIMITS.dimTextChars);
      scene.dimensions.push({
        id: entityId("dimension", index, raw.id),
        start,
        end,
        offset: Math.max(0.1, coerceFloat(raw.offset ?? 10, 10)),
        angle: coerceFloat(raw.angle ?? 0, 0),
        text,
        layer: layerName(raw.layer, "DIMENSIONS"),
      });
    });

  listOf(input.leaders)
    .slice(0, LIMITS.leaders)
    .forEach((raw, index) => {
      if (!isPlainObject(raw)) return;
      const points = coercePoints(raw.points, 2);
      if (!points.length) return;
      scene.leaders.push({
        id: entityId("leader", index, raw.id),
        points,
        text: String(raw.text ?? REFERENCE_NOTE).slice(0, LIMITS.textChars),
        textHeight: Math.max(0.1, coerceFloat(raw.text_height, 2.5)),
        layer: layerName(raw.layer, "ANNOTATION"),
      });
    });

  const hasGeometry = Boolean(
    scene.polylines.length || scene.circles.length || scene.arcs.length || scene.slots.length,
  );
  if (!hasGeometry) {
    report("$", "Drawing scene contains no supported geometry (polyline, circle, arc, or slot)");
  }

  // Preserve stable IDs and make them unique across the whole scene (matches Python).
  const seen = new Set<string>();
  for (const collection of [
    scene.polylines,
    scene.circles,
    scene.arcs,
    scene.slots,
    scene.hatches,
    scene.texts,
    scene.dimensions,
    scene.leaders,
  ]) {
    for (const entity of collection) {
      const base = entity.id;
      let suffix = 2;
      while (seen.has(entity.id)) {
        entity.id = `${base}_${suffix}`;
        suffix += 1;
      }
      seen.add(entity.id);
    }
  }

  // Backfill any referenced layer names that were not declared.
  const existing = new Set(scene.layers.map((layer) => layer.name));
  const referenced = new Set<string>();
  for (const collection of [
    scene.polylines,
    scene.circles,
    scene.arcs,
    scene.slots,
    scene.hatches,
    scene.texts,
    scene.dimensions,
    scene.leaders,
  ]) {
    for (const entity of collection) referenced.add(entity.layer);
  }
  for (const name of [...referenced].filter((name) => !existing.has(name)).sort()) {
    scene.layers.push({ name, color: 7, linetype: "CONTINUOUS" });
  }

  if (issues.length) return { ok: false, issues };
  return { ok: true, scene };
}

/** Throwing variant of `parseDrawingScene`. */
export function validateDrawingScene(input: unknown, units?: Unit): DrawingScene {
  const result = parseDrawingScene(input, units);
  if (!result.ok) throw new DrawingSceneValidationError(result.issues);
  return result.scene;
}

/**
 * Serialize a normalized scene back to the portable wire shape. Emits the same
 * snake_case keys and field order as the Python `scene_to_dict`/`asdict` so a
 * validated scene round-trips to the identical `<run_id>.scene.json` artifact.
 */
export function sceneToDict(scene: DrawingScene): Record<string, unknown> {
  return {
    title: scene.title,
    units: scene.units,
    schema_version: scene.schemaVersion,
    coordinate_system: scene.coordinateSystem,
    layers: scene.layers.map((layer) => ({
      name: layer.name,
      color: layer.color,
      linetype: layer.linetype,
    })),
    polylines: scene.polylines.map((entity) => ({
      id: entity.id,
      points: entity.points,
      layer: entity.layer,
      closed: entity.closed,
    })),
    circles: scene.circles.map((entity) => ({
      id: entity.id,
      center: entity.center,
      radius: entity.radius,
      layer: entity.layer,
    })),
    arcs: scene.arcs.map((entity) => ({
      id: entity.id,
      center: entity.center,
      radius: entity.radius,
      start_angle: entity.startAngle,
      end_angle: entity.endAngle,
      layer: entity.layer,
    })),
    slots: scene.slots.map((entity) => ({
      id: entity.id,
      center: entity.center,
      length: entity.length,
      width: entity.width,
      angle: entity.angle,
      layer: entity.layer,
    })),
    hatches: scene.hatches.map((entity) => ({
      id: entity.id,
      boundary: entity.boundary,
      layer: entity.layer,
      pattern: entity.pattern,
    })),
    texts: scene.texts.map((entity) => ({
      id: entity.id,
      text: entity.text,
      insert: entity.insert,
      height: entity.height,
      layer: entity.layer,
    })),
    dimensions: scene.dimensions.map((entity) => ({
      id: entity.id,
      start: entity.start,
      end: entity.end,
      offset: entity.offset,
      layer: entity.layer,
      angle: entity.angle,
      text: entity.text,
    })),
    leaders: scene.leaders.map((entity) => ({
      id: entity.id,
      points: entity.points,
      text: entity.text,
      text_height: entity.textHeight,
      layer: entity.layer,
    })),
  };
}

export function sceneToJson(scene: DrawingScene): string {
  return JSON.stringify(sceneToDict(scene), null, 2);
}