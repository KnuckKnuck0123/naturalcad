"use client";

import { useMemo } from "react";
import type { CSSProperties } from "react";

import { parseDrawingScene } from "@/lib/drawing-scene";
import type { DrawingScene } from "@/lib/drawing-scene";
import type { ViewportMapping } from "@/lib/drawing-scene-geometry";
import { arcPath, fitViewport, num, sceneBounds, slotPath } from "@/lib/drawing-scene-geometry";

const VIEW_SIZE = 860;
const PADDING = 56;

/** Palette matching the Python preview renderer. */
const LAYER_GEOMETRY = "#d5d9e3";
const LAYER_CENTER = "#38bdf8";
const LAYER_HATCH = "#334155";
const LAYER_DIMENSIONS = "#f59e0b";
const LAYER_TEXT = "#e2e8f0";
const LAYER_ANNOTATION = "#7dd3fc";

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
  if (upper.includes("CENTER")) return "12 8";
  if (upper.includes("DASH") || upper.includes("HIDDEN")) return "8 6";
  return undefined;
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
}

export function DraftingViewport2D({
  scene,
  width = "100%",
  height = "100%",
  className,
  style,
  "aria-label": ariaLabel,
}: DraftingViewport2DProps) {
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

  const parsed = useMemo(() => parseDrawingScene(scene), [scene]);

  const body = useMemo(() => {
    if (!parsed.ok || !parsed.scene) return null;
    return renderScene(parsed.scene);
  }, [parsed]);

  if (!parsed.ok) {
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

  if (!body) return null;

  const title = parsed.scene.title;

  return (
    <svg
      className={className}
      style={style}
      width={width}
      height={height}
      viewBox={`0 0 ${VIEW_SIZE} ${VIEW_SIZE}`}
      role="img"
      aria-label={ariaLabel ?? title}
      preserveAspectRatio="xMidYMid meet"
    >
      <rect width="100%" height="100%" fill="#0e1116" />
      <rect
        x="20" y="20" width={VIEW_SIZE - 40} height={VIEW_SIZE - 40} rx="18"
        fill="#141922" stroke="#2b3342" strokeWidth="2"
      />
      {body}
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

  return (
    <g>
      {scene.hatches.map((hatch) => {
        const color = colorForLayer(hatch.layer);
        const points = hatch.boundary.map((point) => project(point).map(num).join(",")).join(" ");
        return <polygon key={hatch.id} data-entity-id={hatch.id} points={points} fill={color} fillOpacity="0.18" />;
      })}

      {scene.polylines.map((polyline) => {
        const color = colorForLayer(polyline.layer);
        const dash = strokeDasharrayFor(polyline.layer);
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
            strokeWidth="2"
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
            fill="none" stroke={colorForLayer(circle.layer)} strokeWidth="2"
          />
        );
      })}

      {scene.arcs.map((arc) => (
        <path
          key={arc.id}
          data-entity-id={arc.id}
          d={arcPath(arc.center, arc.radius, arc.startAngle, arc.endAngle, project)}
          fill="none" stroke={colorForLayer(arc.layer)} strokeWidth="2"
        />
      ))}

      {scene.slots.map((slot) => (
        <path
          key={slot.id}
          data-entity-id={slot.id}
          d={slotPath(slot, viewport.scale, project)}
          fill="none" stroke={colorForLayer(slot.layer)} strokeWidth="2"
        />
      ))}

      {scene.dimensions.map((dimension) => {
        const p1 = project(dimension.start);
        const p2 = project(dimension.end);
        const offset = dimension.offset * viewport.scale;
        const a = Math.abs((dimension.angle % 180) - 90) < 0.01 ? [p1[0] + offset, p1[1]] as const : [p1[0], p1[1] + offset] as const;
        const b = Math.abs((dimension.angle % 180) - 90) < 0.01 ? [p2[0] + offset, p2[1]] as const : [p2[0], p2[1] + offset] as const;
        const midX = (a[0] + b[0]) / 2;
        const midY = (a[1] + b[1]) / 2;
        return (
          <g key={dimension.id} data-entity-id={dimension.id}>
            <line x1={num(a[0])} y1={num(a[1])} x2={num(b[0])} y2={num(b[1])} stroke={LAYER_DIMENSIONS} strokeWidth="2" />
            {dimension.text && (
              <text x={num(midX)} y={num(midY - 6)} fontSize="16" fill="#fbbf24" textAnchor="middle">
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
            <polyline points={pointsString} fill="none" stroke={LAYER_ANNOTATION} strokeWidth="2" />
            <text x={num(last[0] + 8)} y={num(last[1] - 8)} fontSize="15" fill={LAYER_ANNOTATION}>
              {leader.text}
            </text>
          </g>
        );
      })}

      {scene.texts.map((text) => {
        const [x, y] = project(text.insert);
        return (
          <text key={text.id} data-entity-id={text.id} x={num(x)} y={num(y)} fontSize="20" fill={colorForLayer(text.layer)}>
            {text.text}
          </text>
        );
      })}
    </g>
  );
}