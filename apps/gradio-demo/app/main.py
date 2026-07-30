#!/usr/bin/env python3
"""Gradio app for the NaturalCAD 2D Hugging Face lane."""

from __future__ import annotations

import base64
import html
import json
import math
import mimetypes
import os
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import ezdxf
import gradio as gr
import httpx
from ezdxf import units as ezdxf_units
from shapely.geometry import Polygon

ARTIFACTS_DIR = Path(__file__).parent.parent / "artifacts"
RUNS_DIR = ARTIFACTS_DIR / "runs"
LOGS_DIR = ARTIFACTS_DIR / "logs"
RUN_LOG_PATH = LOGS_DIR / "runs.jsonl"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

OPENROUTER_API_URL = os.getenv("OPENROUTER_API_URL", "https://openrouter.ai/api/v1/chat/completions").strip()
OPENROUTER_MODEL = (
    os.getenv("NATURALCAD_2D_MODEL")
    or os.getenv("OPENROUTER_MODEL")
    or "openai/gpt-4.1-mini"
).strip()
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_REFERER = os.getenv("OPENROUTER_REFERER", "").strip()
OPENROUTER_TITLE = os.getenv("OPENROUTER_TITLE", "NaturalCAD 2D").strip()
OPENROUTER_TIMEOUT = float(os.getenv("NATURALCAD_2D_TIMEOUT", "120"))

UNIT_MAP = {
    "mm": ezdxf_units.MM,
    "cm": ezdxf_units.CM,
    "m": ezdxf_units.M,
    "in": ezdxf_units.IN,
    "ft": ezdxf_units.FT,
}

REFERENCE_NOTE = "More reference dimensions = more accurate output."

EXAMPLE_PROMPTS = [
    "Steel mounting plate 180x90 mm with four 12 mm corner holes and center label",
    "Wall bracket detail with two slots, one centerline, and dimensions in millimeters",
    "Draft a hatch-filled footing detail with leader note and title text",
]

MODEL_SYSTEM_PROMPT = """You are NaturalCAD 2D, a drafting scene generator.
Return only valid JSON matching this schema:
{
  "title": "short title",
  "units": "mm|cm|m|in|ft",
  "layers": [{"name": "GEOMETRY", "color": 7, "linetype": "CONTINUOUS"}],
  "polylines": [{"points": [[0,0],[10,0],[10,5],[0,5]], "layer": "GEOMETRY", "closed": true}],
  "circles": [{"center": [0,0], "radius": 3, "layer": "GEOMETRY"}],
  "hatches": [{"boundary": [[0,0],[10,0],[10,5],[0,5]], "layer": "HATCH", "pattern": "SOLID"}],
  "texts": [{"text": "note", "insert": [0,0], "height": 3, "layer": "TEXT"}],
  "dimensions": [{"start": [0,0], "end": [10,0], "offset": 10, "angle": 0, "text": "10 mm", "layer": "DIMENSIONS"}],
  "leaders": [{"points": [[0,0],[10,10]], "text": "note", "text_height": 2.5, "layer": "ANNOTATION"}]
}
Rules:
- Use numeric world coordinates only.
- Keep the scene compact and editable.
- Represent hatches, dimensions, leaders, and text as their own objects.
- Prefer millimeters unless the user clearly specifies another unit.
- If details are uncertain, keep geometry simple and preserve the user's intent in text/leader annotations.
- Do not include markdown fences, prose, comments, or explanations."""


@dataclass
class LayerStyle:
    name: str
    color: int = 7
    linetype: str = "CONTINUOUS"


@dataclass
class PolylineEntity:
    points: list[tuple[float, float]]
    layer: str = "GEOMETRY"
    closed: bool = False


@dataclass
class CircleEntity:
    center: tuple[float, float]
    radius: float
    layer: str = "GEOMETRY"


@dataclass
class HatchEntity:
    boundary: list[tuple[float, float]]
    layer: str = "HATCH"
    pattern: str = "SOLID"


@dataclass
class TextEntity:
    text: str
    insert: tuple[float, float]
    height: float
    layer: str = "TEXT"


@dataclass
class LinearDimensionEntity:
    start: tuple[float, float]
    end: tuple[float, float]
    offset: float
    layer: str = "DIMENSIONS"
    angle: float = 0.0
    text: str | None = None


@dataclass
class LeaderEntity:
    points: list[tuple[float, float]]
    text: str
    text_height: float
    layer: str = "ANNOTATION"


@dataclass
class DrawingScene:
    units: str
    title: str
    prompt: str
    reference_notes: str
    image_name: str | None
    image_size: tuple[int, int] | None
    layers: list[LayerStyle] = field(default_factory=list)
    polylines: list[PolylineEntity] = field(default_factory=list)
    circles: list[CircleEntity] = field(default_factory=list)
    hatches: list[HatchEntity] = field(default_factory=list)
    texts: list[TextEntity] = field(default_factory=list)
    dimensions: list[LinearDimensionEntity] = field(default_factory=list)
    leaders: list[LeaderEntity] = field(default_factory=list)


def _extract_first(prompt: str, pattern: str, default: float) -> float:
    match = re.search(pattern, prompt, re.IGNORECASE)
    if not match:
        return default
    try:
        return float(match.group(1))
    except ValueError:
        return default


def _extract_plate_size(prompt: str) -> tuple[float, float]:
    pair = re.search(r"(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)", prompt)
    if pair:
        return float(pair.group(1)), float(pair.group(2))
    width = _extract_first(prompt, r"width\s*(?:of)?\s*(\d+(?:\.\d+)?)", 180.0)
    height = _extract_first(prompt, r"(?:height|depth)\s*(?:of)?\s*(\d+(?:\.\d+)?)", 90.0)
    return width, height


def _extract_hole_count(prompt: str) -> int:
    match = re.search(r"(\d+)\s+(?:corner\s+)?holes?", prompt, re.IGNORECASE)
    if match:
        return max(0, int(match.group(1)))
    if "slot" in prompt.lower():
        return 2
    return 4


def _extract_hole_diameter(prompt: str) -> float:
    return _extract_first(prompt, r"(\d+(?:\.\d+)?)\s*mm\s+(?:corner\s+)?holes?", 12.0)


def _default_layers() -> list[LayerStyle]:
    return [
        LayerStyle("GEOMETRY", color=7),
        LayerStyle("CENTER", color=4, linetype="CENTER"),
        LayerStyle("HATCH", color=8),
        LayerStyle("DIMENSIONS", color=2),
        LayerStyle("TEXT", color=3),
        LayerStyle("ANNOTATION", color=6),
    ]


def _image_info(image_path: str | None) -> tuple[str | None, tuple[int, int] | None]:
    if not image_path:
        return None, None
    path = Path(image_path)
    image_name = path.name
    image_size = None
    try:
        from PIL import Image

        with Image.open(path) as image:
            image_size = image.size
    except Exception:
        image_size = None
    return image_name, image_size


def _normalize_units(value: str | None, fallback: str) -> str:
    candidate = (value or fallback or "mm").strip().lower()
    return candidate if candidate in UNIT_MAP else fallback


def build_fallback_scene(prompt: str, reference_notes: str, units: str, image_path: str | None) -> DrawingScene:
    prompt = (prompt or "").strip()
    reference_notes = (reference_notes or "").strip()
    width, height = _extract_plate_size(prompt or "180x90")
    hole_count = _extract_hole_count(prompt)
    hole_diameter = _extract_hole_diameter(prompt)
    margin = min(width, height) * 0.15
    title = "NaturalCAD 2D Draft"
    image_name, image_size = _image_info(image_path)

    outline = [
        (-width / 2, -height / 2),
        (width / 2, -height / 2),
        (width / 2, height / 2),
        (-width / 2, height / 2),
    ]
    scene = DrawingScene(
        units=units,
        title=title,
        prompt=prompt,
        reference_notes=reference_notes,
        image_name=image_name,
        image_size=image_size,
        layers=_default_layers(),
    )
    scene.polylines.append(PolylineEntity(points=outline, closed=True))
    scene.hatches.append(HatchEntity(boundary=outline))

    if hole_count >= 4:
        hole_positions = [
            (-width / 2 + margin, -height / 2 + margin),
            (width / 2 - margin, -height / 2 + margin),
            (width / 2 - margin, height / 2 - margin),
            (-width / 2 + margin, height / 2 - margin),
        ]
    elif hole_count == 2:
        hole_positions = [(-width / 4, 0.0), (width / 4, 0.0)]
    else:
        hole_positions = []

    for center in hole_positions[:hole_count]:
        scene.circles.append(CircleEntity(center=center, radius=hole_diameter / 2))

    scene.polylines.append(
        PolylineEntity(points=[(-width / 2 - 20, 0.0), (width / 2 + 20, 0.0)], layer="CENTER")
    )
    scene.texts.append(
        TextEntity(
            text=prompt or "2D drafting study",
            insert=(-width / 2, height / 2 + 22),
            height=max(3.0, min(width, height) * 0.05),
        )
    )
    scene.dimensions.append(
        LinearDimensionEntity(
            start=(-width / 2, -height / 2),
            end=(width / 2, -height / 2),
            offset=20.0,
            text=f"{width:g} {units}",
        )
    )
    scene.dimensions.append(
        LinearDimensionEntity(
            start=(width / 2, -height / 2),
            end=(width / 2, height / 2),
            offset=22.0,
            angle=90.0,
            text=f"{height:g} {units}",
        )
    )
    scene.leaders.append(
        LeaderEntity(
            points=[
                (width / 2 - margin, height / 2 - margin),
                (width / 2 + 18.0, height / 2 + 18.0),
            ],
            text=REFERENCE_NOTE,
            text_height=max(2.5, min(width, height) * 0.035),
        )
    )
    return scene


def _openrouter_headers() -> dict[str, str]:
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not configured")
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    if OPENROUTER_REFERER:
        headers["HTTP-Referer"] = OPENROUTER_REFERER
    if OPENROUTER_TITLE:
        headers["X-Title"] = OPENROUTER_TITLE
    return headers


def _data_url_for_image(image_path: str) -> str:
    mime_type = mimetypes.guess_type(image_path)[0] or "application/octet-stream"
    encoded = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _strip_markdown_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _coerce_point(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        return float(value[0]), float(value[1])
    except (TypeError, ValueError):
        return None


def _coerce_points(values: Any, *, minimum: int = 2) -> list[tuple[float, float]]:
    if not isinstance(values, list):
        return []
    points = [point for point in (_coerce_point(item) for item in values[:64]) if point is not None]
    return points if len(points) >= minimum else []


def _coerce_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def scene_from_payload(
    payload: dict[str, Any],
    *,
    prompt: str,
    reference_notes: str,
    requested_units: str,
    image_path: str | None,
) -> DrawingScene:
    image_name, image_size = _image_info(image_path)
    scene = DrawingScene(
        units=_normalize_units(payload.get("units"), requested_units),
        title=str(payload.get("title") or "NaturalCAD 2D Draft"),
        prompt=prompt,
        reference_notes=reference_notes,
        image_name=image_name,
        image_size=image_size,
        layers=[],
    )

    for layer in payload.get("layers", [])[:12] if isinstance(payload.get("layers"), list) else []:
        if not isinstance(layer, dict) or not layer.get("name"):
            continue
        scene.layers.append(
            LayerStyle(
                name=str(layer["name"]),
                color=int(_coerce_float(layer.get("color"), 7)),
                linetype=str(layer.get("linetype") or "CONTINUOUS"),
            )
        )
    if not scene.layers:
        scene.layers = _default_layers()

    for item in payload.get("polylines", [])[:32] if isinstance(payload.get("polylines"), list) else []:
        if not isinstance(item, dict):
            continue
        points = _coerce_points(item.get("points"), minimum=2)
        if points:
            scene.polylines.append(
                PolylineEntity(
                    points=points,
                    layer=str(item.get("layer") or "GEOMETRY"),
                    closed=_coerce_bool(item.get("closed"), False),
                )
            )

    for item in payload.get("circles", [])[:32] if isinstance(payload.get("circles"), list) else []:
        if not isinstance(item, dict):
            continue
        center = _coerce_point(item.get("center"))
        radius = _coerce_float(item.get("radius"), 0.0)
        if center and radius > 0:
            scene.circles.append(CircleEntity(center=center, radius=radius, layer=str(item.get("layer") or "GEOMETRY")))

    for item in payload.get("hatches", [])[:16] if isinstance(payload.get("hatches"), list) else []:
        if not isinstance(item, dict):
            continue
        boundary = _coerce_points(item.get("boundary"), minimum=3)
        if boundary:
            scene.hatches.append(
                HatchEntity(
                    boundary=boundary,
                    layer=str(item.get("layer") or "HATCH"),
                    pattern=str(item.get("pattern") or "SOLID"),
                )
            )

    for item in payload.get("texts", [])[:24] if isinstance(payload.get("texts"), list) else []:
        if not isinstance(item, dict):
            continue
        insert = _coerce_point(item.get("insert"))
        if insert:
            scene.texts.append(
                TextEntity(
                    text=str(item.get("text") or ""),
                    insert=insert,
                    height=max(0.1, _coerce_float(item.get("height"), 3.0)),
                    layer=str(item.get("layer") or "TEXT"),
                )
            )

    for item in payload.get("dimensions", [])[:24] if isinstance(payload.get("dimensions"), list) else []:
        if not isinstance(item, dict):
            continue
        start = _coerce_point(item.get("start"))
        end = _coerce_point(item.get("end"))
        if start and end:
            scene.dimensions.append(
                LinearDimensionEntity(
                    start=start,
                    end=end,
                    offset=max(0.1, _coerce_float(item.get("offset"), 10.0)),
                    angle=_coerce_float(item.get("angle"), 0.0),
                    text=str(item.get("text")) if item.get("text") is not None else None,
                    layer=str(item.get("layer") or "DIMENSIONS"),
                )
            )

    for item in payload.get("leaders", [])[:24] if isinstance(payload.get("leaders"), list) else []:
        if not isinstance(item, dict):
            continue
        points = _coerce_points(item.get("points"), minimum=2)
        if points:
            scene.leaders.append(
                LeaderEntity(
                    points=points,
                    text=str(item.get("text") or REFERENCE_NOTE),
                    text_height=max(0.1, _coerce_float(item.get("text_height"), 2.5)),
                    layer=str(item.get("layer") or "ANNOTATION"),
                )
            )

    if not scene.polylines:
        return build_fallback_scene(prompt, reference_notes, requested_units, image_path)
    return scene


def request_model_scene(
    prompt: str,
    reference_notes: str,
    units: str,
    image_path: str | None,
) -> tuple[DrawingScene | None, dict[str, Any]]:
    if not OPENROUTER_API_KEY:
        return None, {"source": "fallback", "reason": "OPENROUTER_API_KEY not configured"}

    user_text = "\n".join(
        [
            f"Prompt: {prompt or 'No prompt provided.'}",
            f"Reference notes: {reference_notes or 'None'}",
            f"Requested units: {units}",
            f"Accuracy note: {REFERENCE_NOTE}",
            "Return a compact, editable drafting scene. Use hatches, dimensions, leaders, and text where they help preserve intent.",
        ]
    )
    content: Any = [{"type": "text", "text": user_text}]
    if image_path:
        content.append({"type": "image_url", "image_url": {"url": _data_url_for_image(image_path)}})

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {"role": "system", "content": MODEL_SYSTEM_PROMPT},
            {"role": "user", "content": content if image_path else user_text},
        ],
        "temperature": 0.2,
        "max_tokens": 2400,
    }

    started = time.monotonic()
    try:
        with httpx.Client(timeout=OPENROUTER_TIMEOUT) as client:
            response = client.post(OPENROUTER_API_URL, headers=_openrouter_headers(), json=payload)
        response.raise_for_status()
        data = response.json()
        raw_content = (data.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
        if not raw_content:
            raise ValueError("Model returned empty content")
        payload_text = _strip_markdown_fences(raw_content)
        scene_payload = json.loads(payload_text)
        scene = scene_from_payload(
            scene_payload,
            prompt=prompt,
            reference_notes=reference_notes,
            requested_units=units,
            image_path=image_path,
        )
        return scene, {
            "source": "model",
            "model": OPENROUTER_MODEL,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "usage": data.get("usage", {}),
        }
    except Exception as exc:
        return None, {
            "source": "fallback",
            "model": OPENROUTER_MODEL,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "reason": str(exc),
        }


def scene_bounds(scene: DrawingScene) -> tuple[float, float, float, float]:
    min_x = math.inf
    min_y = math.inf
    max_x = -math.inf
    max_y = -math.inf

    def include(x: float, y: float) -> None:
        nonlocal min_x, min_y, max_x, max_y
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x)
        max_y = max(max_y, y)

    for polyline in scene.polylines:
        for x, y in polyline.points:
            include(x, y)
    for circle in scene.circles:
        x, y = circle.center
        include(x - circle.radius, y - circle.radius)
        include(x + circle.radius, y + circle.radius)
    for hatch in scene.hatches:
        bx0, by0, bx1, by1 = Polygon(hatch.boundary).bounds
        include(bx0, by0)
        include(bx1, by1)
    for text in scene.texts:
        include(*text.insert)
    for dim in scene.dimensions:
        include(*dim.start)
        include(*dim.end)
    for leader in scene.leaders:
        for point in leader.points:
            include(*point)

    if min_x is math.inf:
        return -100.0, -100.0, 100.0, 100.0
    return min_x, min_y, max_x, max_y


def _svg_point(x: float, y: float, bounds: tuple[float, float, float, float], size: int, padding: int) -> tuple[float, float]:
    min_x, min_y, max_x, max_y = bounds
    span_x = max(max_x - min_x, 1.0)
    span_y = max(max_y - min_y, 1.0)
    scale = min((size - 2 * padding) / span_x, (size - 2 * padding) / span_y)
    px = padding + (x - min_x) * scale
    py = size - padding - (y - min_y) * scale
    return px, py


def render_svg(scene: DrawingScene) -> str:
    size = 860
    padding = 56
    bounds = scene_bounds(scene)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">',
        '<rect width="100%" height="100%" fill="#0e1116" />',
        '<rect x="18" y="18" width="824" height="824" rx="18" fill="#141922" stroke="#2b3342" stroke-width="2" />',
    ]

    for hatch in scene.hatches:
        points = [_svg_point(x, y, bounds, size, padding) for x, y in hatch.boundary]
        path = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
        parts.append(f'<polygon points="{path}" fill="#334155" fill-opacity="0.18" stroke="none" />')

    for polyline in scene.polylines:
        points = [_svg_point(x, y, bounds, size, padding) for x, y in polyline.points]
        path = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
        dash = ' stroke-dasharray="12 8"' if polyline.layer == "CENTER" else ""
        close = " Z" if polyline.closed else ""
        parts.append(f'<path d="M {path}{close}" fill="none" stroke="#d5d9e3" stroke-width="2"{dash} />')

    for circle in scene.circles:
        cx, cy = _svg_point(circle.center[0], circle.center[1], bounds, size, padding)
        edge, _ = _svg_point(circle.center[0] + circle.radius, circle.center[1], bounds, size, padding)
        radius = abs(edge - cx)
        parts.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{radius:.2f}" fill="none" stroke="#d5d9e3" stroke-width="2" />')

    for dim in scene.dimensions:
        p1 = _svg_point(*dim.start, bounds, size, padding)
        p2 = _svg_point(*dim.end, bounds, size, padding)
        if dim.angle == 90.0:
            p1 = (p1[0] + 34, p1[1])
            p2 = (p2[0] + 34, p2[1])
        else:
            p1 = (p1[0], p1[1] + 34)
            p2 = (p2[0], p2[1] + 34)
        parts.append(f'<line x1="{p1[0]:.2f}" y1="{p1[1]:.2f}" x2="{p2[0]:.2f}" y2="{p2[1]:.2f}" stroke="#f59e0b" stroke-width="2" />')
        tx = (p1[0] + p2[0]) / 2
        ty = (p1[1] + p2[1]) / 2 - 6
        parts.append(f'<text x="{tx:.2f}" y="{ty:.2f}" font-size="16" fill="#fbbf24" text-anchor="middle">{html.escape(dim.text or "")}</text>')

    for leader in scene.leaders:
        points = [_svg_point(x, y, bounds, size, padding) for x, y in leader.points]
        path = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
        parts.append(f'<polyline points="{path}" fill="none" stroke="#38bdf8" stroke-width="2" />')
        lx, ly = points[-1]
        parts.append(f'<text x="{lx + 8:.2f}" y="{ly - 8:.2f}" font-size="15" fill="#7dd3fc">{html.escape(leader.text)}</text>')

    for text_entity in scene.texts:
        tx, ty = _svg_point(*text_entity.insert, bounds, size, padding)
        parts.append(f'<text x="{tx:.2f}" y="{ty:.2f}" font-size="20" fill="#e2e8f0">{html.escape(text_entity.text)}</text>')

    parts.append("</svg>")
    return "".join(parts)


def export_dxf(scene: DrawingScene, path: Path) -> None:
    document = ezdxf.new("R2010")
    document.units = UNIT_MAP.get(scene.units, ezdxf_units.MM)
    for layer in scene.layers:
        if layer.name not in document.layers:
            document.layers.add(layer.name, color=layer.color, linetype=layer.linetype)
    modelspace = document.modelspace()

    for polyline in scene.polylines:
        modelspace.add_lwpolyline(polyline.points, close=polyline.closed, dxfattribs={"layer": polyline.layer})
    for circle in scene.circles:
        modelspace.add_circle(circle.center, circle.radius, dxfattribs={"layer": circle.layer})
    for hatch in scene.hatches:
        hatch_entity = modelspace.add_hatch(color=8, dxfattribs={"layer": hatch.layer})
        hatch_entity.paths.add_polyline_path(hatch.boundary, is_closed=True)
        if hatch.pattern != "SOLID":
            hatch_entity.set_pattern_fill(hatch.pattern, scale=1.0)
    for text_entity in scene.texts:
        modelspace.add_text(
            text_entity.text,
            dxfattribs={"layer": text_entity.layer, "height": text_entity.height},
        ).set_placement(text_entity.insert)
    for dimension in scene.dimensions:
        if dimension.angle == 90.0:
            base = (dimension.start[0] + dimension.offset, (dimension.start[1] + dimension.end[1]) / 2)
        else:
            base = ((dimension.start[0] + dimension.end[0]) / 2, dimension.start[1] - dimension.offset)
        dim = modelspace.add_linear_dim(
            base=base,
            p1=dimension.start,
            p2=dimension.end,
            angle=dimension.angle,
            dxfattribs={"layer": dimension.layer},
            override={"dimtad": 1},
        )
        dim.render()
    for leader in scene.leaders:
        modelspace.add_lwpolyline(leader.points, dxfattribs={"layer": leader.layer})
        modelspace.add_text(
            leader.text,
            dxfattribs={"layer": leader.layer, "height": leader.text_height},
        ).set_placement(leader.points[-1])
    document.saveas(path)


def write_run_log(payload: dict[str, Any]) -> None:
    with RUN_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload) + "\n")


def generate_drawing(
    prompt: str,
    sketch_image: str | None,
    reference_notes: str,
    units: str,
) -> tuple[str, str, str, str]:
    run_id = uuid.uuid4().hex[:8]
    scene, model_meta = request_model_scene(prompt, reference_notes, units, sketch_image)
    if scene is None:
        scene = build_fallback_scene(prompt, reference_notes, units, sketch_image)

    dxf_path = RUNS_DIR / f"{run_id}.dxf"
    export_dxf(scene, dxf_path)
    svg_markup = render_svg(scene)
    preview_path = RUNS_DIR / f"{run_id}.svg"
    preview_path.write_text(svg_markup, encoding="utf-8")

    summary = {
        "run_id": run_id,
        "title": scene.title,
        "units": scene.units,
        "image_name": scene.image_name,
        "image_size": scene.image_size,
        "entity_counts": {
            "polylines": len(scene.polylines),
            "circles": len(scene.circles),
            "hatches": len(scene.hatches),
            "dimensions": len(scene.dimensions),
            "leaders": len(scene.leaders),
            "texts": len(scene.texts),
        },
        "reference_notes": scene.reference_notes,
        "note": REFERENCE_NOTE,
        "source": model_meta.get("source", "fallback"),
        "model": model_meta.get("model"),
        "model_latency_ms": model_meta.get("latency_ms"),
        "usage": model_meta.get("usage", {}),
        "fallback_reason": model_meta.get("reason"),
    }
    write_run_log(summary)

    status_lines = [
        f"Run `{run_id}` complete.",
        f"Source: `{summary['source']}`",
        f"Units: `{scene.units}`",
        f"DXF: `{dxf_path.name}`",
        REFERENCE_NOTE,
    ]
    if summary.get("model"):
        status_lines.append(f"Model: `{summary['model']}`")
    if summary.get("fallback_reason"):
        status_lines.append(f"Fallback reason: `{summary['fallback_reason']}`")
    if scene.image_name:
        image_suffix = f" ({scene.image_size[0]}x{scene.image_size[1]})" if scene.image_size else ""
        status_lines.append(f"Sketch input: `{scene.image_name}`{image_suffix}")

    return svg_markup, str(dxf_path), json.dumps(summary, indent=2), "\n".join(status_lines)


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="NaturalCAD 2D", theme=gr.themes.Soft()) as demo:
        gr.Markdown(
            """
            # NaturalCAD 2D
            Prompt, sketch, or combine both to generate a QCAD-ready DXF study.

            More reference dimensions = more accurate output.
            """
        )
        with gr.Row():
            with gr.Column(scale=1):
                prompt = gr.Textbox(
                    label="Text prompt",
                    placeholder="Describe the drawing you want: plate size, holes, notes, dimensions, hatch, title...",
                    lines=5,
                )
                sketch_image = gr.Image(type="filepath", label="Sketch image")
                reference_notes = gr.Textbox(
                    label="Reference dimensions or notes",
                    placeholder="Example: overall width 180 mm, holes are 12 mm, centerline through plate",
                    lines=4,
                )
                units = gr.Dropdown(choices=list(UNIT_MAP.keys()), value="mm", label="Units")
                generate = gr.Button("Generate 2D DXF", variant="primary")
                gr.Examples(examples=EXAMPLE_PROMPTS, inputs=prompt)
            with gr.Column(scale=1):
                preview = gr.HTML(label="Preview")
                dxf_file = gr.File(label="DXF download")
                scene_summary = gr.Code(label="Scene summary", language="json")
                status = gr.Markdown()

        generate.click(
            fn=generate_drawing,
            inputs=[prompt, sketch_image, reference_notes, units],
            outputs=[preview, dxf_file, scene_summary, status],
        )

    return demo


if __name__ == "__main__":
    build_ui().launch(server_name="0.0.0.0", server_port=7860)
