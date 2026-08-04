"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { CSSProperties, PointerEvent as ReactPointerEvent, WheelEvent as ReactWheelEvent } from "react";

import { parseDrawingScene } from "@/lib/drawing-scene";
import type { DrawingScene } from "@/lib/drawing-scene";
import type { ViewportMapping } from "@/lib/drawing-scene-geometry";
import { arcPath, fitViewport, num, sceneBounds, slotPath } from "@/lib/drawing-scene-geometry";

const VIEW_SIZE = 860;
const PADDING = 56;
const MIN_ZOOM = 0.2;
const MAX_ZOOM = 20;

/** CAD drafting palette — white geometry on near-black, classic colored linetypes. */
const LAYER_GEOMETRY = "#f0f0f0";
const LAYER_CENTER = "#00e5ff";    // cyan centerlines (AutoCAD classic)
const LAYER_HATCH = "#5b6b86";
const LAYER_DIMENSIONS = "#ffb300"; // amber dimensions
const LAYER_TEXT = "#e2e8f0";
const LAYER_ANNOTATION = "#00e676"; // green annotations

const GRID_COLOR = "#1a2030";
const ORIGIN_COLOR = "#00e5ff";

function colorForLayer(layer: string): string {
  const key = layer.toUpperCase();
  if (key.includes("CENTER")) return LAYER_CENTER;
  if (key.includes("DIMENSION")) return LAYER_DIMENSIONS;
  if (key.includes("HATCH")) return LAYER_HATCH;
  if (key.includes("ANNOTATION") || key.includes("LEADER")) return LAYER_ANNOTATION;
  if (key.includes("TEXT") || key.includes("LABEL")) return LAYER_TEXT;
  return LAYER_GEOMETRY;
}

function strokeDasharrayFor(layer: string): string | undefined {
  const upper = layer.toUpperCase();
  if (upper.includes("CENTER")) return "14 4 3 4";  // dash-dot pattern
  if (upper.includes("DASH") || upper.includes("HIDDEN")) return "8 5";
  if (upper.includes("PHANTOM")) return "12 4 3 4 3 4";
  return undefined;
}

/** Per-layer stroke weight — geometry reads heaviest, annotations lightest. */
function strokeWidthFor(layer: string): number {
  const upper = layer.toUpperCase();
  if (upper.includes("CENTER")) return 1.0;
  if (upper.includes("HATCH")) return 0.8;
  if (upper.includes("DIMENSION")) return 1.2;
  if (upper.includes("ANNOTATION") || upper.includes("LEADER")) return 1.2;
  if (upper.includes("TEXT") || upper.includes("LABEL")) return 1.0;
  return 2.2;  // GEOMETRY — heaviest, the silhouette reads first
}

interface DraftingViewport2DProps {
  /**
   * A DrawingScene 1.0 payload. Parsed defensively at render time: this component
   * never trusts unvalidated JSON. When invalid, it renders a neutral empty state
   * instead of throwing into the page.
   */
  scene: DrawingScene | Record<string, unknown> | null | undefined;
  /** Optional explicit size; defaults to the square default canvas. */
  width?: string | number;
  height?: string | number;
  className?: string;
  style?: CSSProperties;
  "aria-label"?: string;
  /** Bumping this token resets pan/zoom to fit (so the parent Refit button works). */
  resetToken?: number;
}

export function DraftingViewport2D({
  scene,
  width = "100%",
  height = "100%",
  className,
  style,
  "aria-label": ariaLabel,
  resetToken,
}: DraftingViewport2DProps) {
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState<[number, number]>([0, 0]);
  const dragRef = useRef<{ active: boolean; startX: number; startY: number; panX: number; panY: number } | null>(null);
  const svgRef = useRef<SVGSVGElement | null>(null);

  const parsed = useMemo(() => (scene == null ? null : parseDrawingScene(scene)), [scene]);

  // Reset pan/zoom when resetToken bumps or the scene identity changes.
  useEffect(() => {
    setZoom(1);
    setPan([0, 0]);
  }, [resetToken, scene]);

  const onWheel = useCallback((event: ReactWheelEvent<SVGSVGElement>) => {
    // We use deltaMode-free pixel scaling; prevent the page from scrolling.
    if (event.ctrlKey || event.metaKey || true) {
      // Always swallow wheel so the page doesn't scroll under the viewport.
    }
    const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
    setZoom((prev) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, prev * factor)));
  }, []);

  const onPointerDown = useCallback((event: ReactPointerEvent<SVGSVGElement>) => {
    (event.currentTarget as SVGSVGElement).setPointerCapture(event.pointerId);
    dragRef.current = { active: true, startX: event.clientX, startY: event.clientY, panX: pan[0], panY: pan[1] };
  }, [pan]);

  const onPointerMove = useCallback((event: ReactPointerEvent<SVGSVGElement>) => {
    const drag = dragRef.current;
    if (!drag?.active) return;
    const dx = event.clientX - drag.startX;
    const dy = event.clientY - drag.startY;
    setPan([drag.panX + dx, drag.panY + dy]);
  }, []);

  const onPointerUp = useCallback((event: ReactPointerEvent<SVGSVGElement>) => {
    if (dragRef.current) dragRef.current.active = false;
    try { (event.currentTarget as SVGSVGElement).releasePointerCapture(event.pointerId); } catch { /* ignore */ }
  }, []);

  if (scene == null) {
    return (
      <div
        className={className}
        style={{
          width,
          height,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#555",
          fontFamily: "var(--font-mono)",
          fontSize: "0.7rem",
          letterSpacing: "0.2em",
          textTransform: "uppercase",
          ...style,
        }}
      >
        NO DRAWING SCENE
      </div>
    );
  }

  const body = useMemo(() => {
    if (!parsed?.ok || !parsed.scene) return null;
    return renderScene(parsed.scene);
  }, [parsed]);

  if (parsed && !parsed.ok) {
    return (
      <div
        className={className}
        style={{
          width,
          height,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#555",
          fontFamily: "var(--font-mono)",
          fontSize: "0.7rem",
          letterSpacing: "0.2em",
          textTransform: "uppercase",
          ...style,
        }}
      >
        {parsed.issues.length > 0 ? `INVALID DRAWING SCENE (${parsed.issues.length})` : "NO DRAWING SCENE"}
      </div>
    );
  }

  if (!body || !parsed?.ok) return null;

  const title = parsed.scene.title;
  const cx = VIEW_SIZE / 2;
  const cy = VIEW_SIZE / 2;
  // Zoom around the viewport center, then translate by the pan offset.
  const transform = `translate(${num(pan[0])}, ${num(pan[1])}) translate(${cx}, ${cy}) scale(${zoom.toFixed(4)}) translate(${-cx}, ${-cy})`;
  const cursor = dragRef.current?.active ? "grabbing" : "grab";

  return (
    <svg
      ref={svgRef}
      className={className}
      style={{ ...style, cursor, touchAction: "none" }}
      width={width}
      height={height}
      viewBox={`0 0 ${VIEW_SIZE} ${VIEW_SIZE}`}
      role="img"
      aria-label={ariaLabel ?? title}
      preserveAspectRatio="xMidYMid meet"
      onWheel={onWheel}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerLeave={onPointerUp}
    >
      <rect width="100%" height="100%" fill="#0a0d12" />
      <rect
        x="14" y="14" width={VIEW_SIZE - 28} height={VIEW_SIZE - 28} rx="4"
        fill="#0d1118" stroke="#1e293b" strokeWidth="1"
      />
      <g transform={transform}>
        {body}
      </g>
      {/* Corner registration ticks — drawing-sheet feel */}
      <g stroke="#334155" strokeWidth="1" fill="none">
        <path d={`M 14 34 L 14 14 L 34 14`} />
        <path d={`M ${VIEW_SIZE - 34} 14 L ${VIEW_SIZE - 14} 14 L ${VIEW_SIZE - 14} 34`} />
        <path d={`M 14 ${VIEW_SIZE - 34} L 14 ${VIEW_SIZE - 14} L 34 ${VIEW_SIZE - 14}`} />
        <path d={`M ${VIEW_SIZE - 34} ${VIEW_SIZE - 14} L ${VIEW_SIZE - 14} ${VIEW_SIZE - 14} L ${VIEW_SIZE - 14} ${VIEW_SIZE - 34}`} />
      </g>
      <text x={VIEW_SIZE - 22} y={VIEW_SIZE - 22} fontSize="12" fill="#475569" textAnchor="end" fontFamily="ui-monospace, monospace">
        {(zoom * 100).toFixed(0)}%
      </text>
      <text x="22" y={VIEW_SIZE - 22} fontSize="11" fill="#475569" fontFamily="ui-monospace, monospace">
        {title}
      </text>
    </svg>
  );
}

/**
 * Deterministic render of every entity using only React SVG elements. All
 * geometry is derived from the validated scene — no model SVG is ever injected.
 */
function renderScene(scene: DrawingScene) {
  const bounds = sceneBounds(scene);
  const viewport = fitViewport(bounds, VIEW_SIZE, PADDING);
  const project = viewport.project;

  // Grid spacing in world units — pick a "nice" step from the bounds span.
  const spanX = bounds.maxX - bounds.minX;
  const niceStep = niceGridStep(spanX / 10);
  const grid = gridLines(bounds, niceStep);

  const origin = project([0, 0]);

  return (
    <g>
      <defs>
        <pattern id="hatch-pattern" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="6" stroke={LAYER_HATCH} strokeWidth="0.7" opacity="0.55" />
        </pattern>
        <clipPath id="drawing-clip">
          <rect x="14" y="14" width={VIEW_SIZE - 28} height={VIEW_SIZE - 28} />
        </clipPath>
      </defs>

      <g clipPath="url(#drawing-clip)">
        {/* Dot grid in screen space, sparse, low-contrast */}
        {grid.map(([wx, wy], i) => {
          const [sx, sy] = project([wx, wy]);
          return <circle key={`g${i}`} cx={num(sx)} cy={num(sy)} r="0.8" fill={GRID_COLOR} />;
        })}

        {/* Origin marker — UCS-style crosshair */}
        <g stroke={ORIGIN_COLOR} strokeWidth="1.2" opacity="0.7">
          <line x1={num(origin[0] - 10)} y1={num(origin[1])} x2={num(origin[0] + 10)} y2={num(origin[1])} />
          <line x1={num(origin[0])} y1={num(origin[1] - 10)} x2={num(origin[0])} y2={num(origin[1] + 10)} />
          <circle cx={num(origin[0])} cy={num(origin[1])} r="2.5" fill="none" />
        </g>

        {scene.hatches.map((hatch) => {
          const points = hatch.boundary.map((point) => project(point).map(num).join(",")).join(" ");
          const d = "M " + hatch.boundary.map((point) => project(point).map(num).join(",")).join(" L ") + " Z";
          return (
            <g key={hatch.id} data-entity-id={hatch.id}>
              <polygon points={points} fill="url(#hatch-pattern)" stroke="none" />
              <path d={d} fill="none" stroke={colorForLayer(hatch.layer)} strokeWidth="1" opacity="0.5" />
            </g>
          );
        })}

        {scene.polylines.map((polyline) => {
          const color = colorForLayer(polyline.layer);
          const dash = strokeDasharrayFor(polyline.layer);
          const sw = strokeWidthFor(polyline.layer);
          const d = polyline.points
            .map((point) => project(point))
            .map(([x, y], index) => `${index === 0 ? "M" : "L"} ${num(x)},${num(y)}`)
            .join(" ") + (polyline.closed ? " Z" : "");
          return (
            <path
              key={polyline.id}
              data-entity-id={polyline.id}
              d={d}
              fill="none"
              stroke={color}
              strokeWidth={sw}
              strokeLinejoin="round"
              strokeLinecap={dash ? "round" : "butt"}
              strokeDasharray={dash}
            />
          );
        })}

        {scene.circles.map((circle) => {
          const [cx, cy] = project(circle.center);
          return (
            <circle
              key={circle.id}
              data-entity-id={circle.id}
              cx={num(cx)} cy={num(cy)} r={num(circle.radius * viewport.scale)}
              fill="none" stroke={colorForLayer(circle.layer)} strokeWidth={strokeWidthFor(circle.layer)}
              strokeDasharray={strokeDasharrayFor(circle.layer)} strokeLinecap="round"
            />
          );
        })}

        {scene.arcs.map((arc) => (
          <path
            key={arc.id}
            data-entity-id={arc.id}
            d={arcPath(arc.center, arc.radius, arc.startAngle, arc.endAngle, project)}
            fill="none" stroke={colorForLayer(arc.layer)} strokeWidth={strokeWidthFor(arc.layer)}
            strokeDasharray={strokeDasharrayFor(arc.layer)} strokeLinecap="round"
          />
        ))}

        {scene.slots.map((slot) => (
          <path
            key={slot.id}
            data-entity-id={slot.id}
            d={slotPath(slot, viewport.scale, project)}
            fill="none" stroke={colorForLayer(slot.layer)} strokeWidth={strokeWidthFor(slot.layer)}
            strokeDasharray={strokeDasharrayFor(slot.layer)} strokeLinecap="round"
          />
        ))}

        {scene.dimensions.map((dimension) => {
          const p1 = project(dimension.start);
          const p2 = project(dimension.end);
          const offset = dimension.offset * viewport.scale;
          const vertical = Math.abs((dimension.angle % 180) - 90) < 0.01;
          const a = vertical ? [p1[0] + offset, p1[1]] as const : [p1[0], p1[1] + offset] as const;
          const b = vertical ? [p2[0] + offset, p2[1]] as const : [p2[0], p2[1] + offset] as const;
          const midX = (a[0] + b[0]) / 2;
          const midY = (a[1] + b[1]) / 2;
          // Extension lines from the feature to the dimension line
          const ext = 6;
          const extA = vertical ? [p1[0], p1[1] - (p1[1] > a[1] ? ext : -ext)] as const : [p1[0] - (p1[0] > a[0] ? ext : -ext), p1[1]] as const;
          const extB = vertical ? [p2[0], p2[1] - (p2[1] > b[1] ? ext : -ext)] as const : [p2[0] - (p2[0] > b[0] ? ext : -ext), p2[1]] as const;
          // Arrow ticks at each end of the dimension line
          const tick = 5;
          const dir = vertical ? (b[1] > a[1] ? 1 : -1) : (b[0] > a[0] ? 1 : -1);
          const tickA = vertical ? `${num(a[0] - tick)},${num(a[1])} ${num(a[0] + tick)},${num(a[1])}` : `${num(a[0])},${num(a[1] - tick)} ${num(a[0])},${num(a[1] + tick)}`;
          const tickB = vertical ? `${num(b[0] - tick)},${num(b[1])} ${num(b[0] + tick)},${num(b[1])}` : `${num(b[0])},${num(b[1] - tick)} ${num(b[0])},${num(b[1] + tick)}`;
          return (
            <g key={dimension.id} data-entity-id={dimension.id} stroke={LAYER_DIMENSIONS} fill={LAYER_DIMENSIONS}>
              <line x1={num(extA[0])} y1={num(extA[1])} x2={num(a[0])} y2={num(a[1])} strokeWidth="0.8" opacity="0.6" />
              <line x1={num(extB[0])} y1={num(extB[1])} x2={num(b[0])} y2={num(b[1])} strokeWidth="0.8" opacity="0.6" />
              <line x1={num(a[0])} y1={num(a[1])} x2={num(b[0])} y2={num(b[1])} strokeWidth="1.4" />
              <polyline points={tickA} strokeWidth="1.4" fill="none" />
              <polyline points={tickB} strokeWidth="1.4" fill="none" />
              {dimension.text && (
                <text x={num(midX)} y={num(midY - 5)} fontSize="13" fill={LAYER_DIMENSIONS} textAnchor="middle" fontFamily="ui-monospace, monospace" stroke="none">
                  {dimension.text}
                </text>
              )}
            </g>
          );
        })}

        {scene.leaders.map((leader) => {
          const points = leader.points.map((point) => project(point));
          const pointsString = points.map(([x, y]) => `${num(x)},${num(y)}`).join(" ");
          const last = points[points.length - 1];
          return (
            <g key={leader.id} data-entity-id={leader.id}>
              <polyline points={pointsString} fill="none" stroke={LAYER_ANNOTATION} strokeWidth="1.2" />
              <text x={num(last[0] + 6)} y={num(last[1] - 6)} fontSize="12" fill={LAYER_ANNOTATION} fontFamily="ui-monospace, monospace">
                {leader.text}
              </text>
            </g>
          );
        })}

        {scene.texts.map((text) => {
          const [x, y] = project(text.insert);
          return (
            <text key={text.id} data-entity-id={text.id} x={num(x)} y={num(y)} fontSize="14" fill={colorForLayer(text.layer)} fontFamily="ui-monospace, monospace">
              {text.text}
            </text>
          );
        })}
      </g>
    </g>
  );
}

/** Pick a "nice" round grid step (1, 2, 5 × 10^n) for a target spacing. */
function niceGridStep(target: number): number {
  if (target <= 0) return 10;
  const exp = Math.floor(Math.log10(target));
  const base = target / 10 ** exp;
  const nice = base < 1.5 ? 1 : base < 3.5 ? 2 : base < 7.5 ? 5 : 10;
  return nice * 10 ** exp;
}

/** Generate grid line intersections covering the bounds, stepped by `step`. */
function gridLines(bounds: { minX: number; minY: number; maxX: number; maxY: number }, step: number): [number, number][] {
  const pts: [number, number][] = [];
  const startX = Math.floor(bounds.minX / step) * step;
  const startY = Math.floor(bounds.minY / step) * step;
  for (let x = startX; x <= bounds.maxX + step; x += step) {
    for (let y = startY; y <= bounds.maxY + step; y += step) {
      pts.push([x, y]);
    }
  }
  return pts;
}