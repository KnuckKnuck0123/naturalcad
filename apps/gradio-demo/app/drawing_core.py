"""Portable NaturalCAD 2D scene contract and deterministic exporters."""

from __future__ import annotations

import html
import hashlib
import itertools
import math
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import ezdxf
from ezdxf import colors as ezdxf_colors
from ezdxf import const as ezdxf_const
from ezdxf import units as ezdxf_units
from ezdxf.render import hatching as ezdxf_hatching

from drafting_standards import (
    GENERIC_PROFILE,
    NOAH_URIU_2D_PROFILE,
    SUPPORTED_STANDARD_PROFILES,
    URIU_2D_LAYER_SPECS,
    URIU_LEGACY_LAYER_ALIASES,
)

SCHEMA_VERSION = "1.2"
COORDINATE_SYSTEM = "XY_RIGHT_HANDED"

UNIT_MAP = {
    "mm": ezdxf_units.MM,
    "cm": ezdxf_units.CM,
    "m": ezdxf_units.M,
    "in": ezdxf_units.IN,
    "ft": ezdxf_units.FT,
}

ALLOWED_LINETYPES = {
    "CONTINUOUS", "CENTER", "CENTER2", "DASHED", "DASHED2", "HIDDEN",
    "PHANTOM", "PHANTOM2", "DASHDOT", "DASHDOT2", "DOT", "DOT2",
}
ALLOWED_LINEWEIGHTS = {0, 5, 9, 13, 15, 18, 20, 25, 30, 35, 40, 50, 53, 60, 70, 80, 90, 100, 106, 120, 140, 158, 200, 211}
ALLOWED_HATCH_PATTERNS = {
    "SOLID",
    "ANSI31", "ANSI32", "ANSI33", "ANSI34", "ANSI35", "ANSI36", "ANSI37", "ANSI38",
    "AR-BRSTD", "AR-CONC", "AR-SAND", "BRICK", "CONCRETE1", "CONCRETE2", "CONCRETE3",
    "EARTH", "ESCHER", "GLASS", "GRASS", "GRAVEL", "GRID", "INSUL", "NET", "SAND",
    "STEEL", "WATER", "WOOD1", "WOOD2", "WOOD3", "WOOD4",
}
REFERENCE_NOTE = "More reference dimensions = more accurate output."

MAX_LAYERS = 64
MAX_POLYLINES = 128
MAX_POINTS_PER_ENTITY = 128
MAX_CIRCLES = 96
MAX_ARCS = 96
MAX_SLOTS = 64
MAX_HATCHES = 64
MAX_HATCH_HOLES = 16
MAX_TEXTS = 64
MAX_DIMENSIONS = 64
MAX_LEADERS = 64
MAX_TOTAL_ENTITIES = 256
MAX_TOTAL_POINTS = 8_192
MAX_PREVIEW_SEGMENTS_PER_HATCH = 4_000
MAX_PREVIEW_SEGMENTS_TOTAL = 16_000


@dataclass
class LayerStyle:
    name: str
    color: int = 7
    linetype: str = "CONTINUOUS"
    lineweight: int = 25
    parent: str | None = None
    semantic_role: str = "generic"
    display_color: tuple[int, int, int] | None = None
    plot_color: tuple[int, int, int] = (0, 0, 0)
    lineweight_mm: float | None = None
    linetype_scale: float = 1.0
    plot: bool = True


@dataclass
class PolylineEntity:
    id: str
    points: list[tuple[float, float]]
    layer: str = "GEOMETRY"
    closed: bool = False


@dataclass
class CircleEntity:
    id: str
    center: tuple[float, float]
    radius: float
    layer: str = "GEOMETRY"


@dataclass
class ArcEntity:
    id: str
    center: tuple[float, float]
    radius: float
    start_angle: float
    end_angle: float
    layer: str = "GEOMETRY"


@dataclass
class SlotEntity:
    id: str
    center: tuple[float, float]
    length: float
    width: float
    angle: float = 0.0
    layer: str = "GEOMETRY"


@dataclass
class HatchEntity:
    id: str
    boundary: list[tuple[float, float]]
    holes: list[list[tuple[float, float]]] = field(default_factory=list)
    layer: str = "HATCH"
    pattern: str = "SOLID"
    pattern_scale: float = 1.0
    pattern_angle: float = 0.0
    opacity: float = 0.18


@dataclass
class TextEntity:
    id: str
    text: str
    insert: tuple[float, float]
    height: float
    layer: str = "TEXT"


@dataclass
class LinearDimensionEntity:
    id: str
    start: tuple[float, float]
    end: tuple[float, float]
    offset: float
    layer: str = "DIMENSIONS"
    angle: float = 0.0
    text: str | None = None


@dataclass
class LeaderEntity:
    id: str
    points: list[tuple[float, float]]
    text: str
    text_height: float
    layer: str = "ANNOTATION"


@dataclass
class DrawingScene:
    title: str
    units: str = "mm"
    standard_profile: str = GENERIC_PROFILE
    schema_version: str = SCHEMA_VERSION
    coordinate_system: str = COORDINATE_SYSTEM
    layers: list[LayerStyle] = field(default_factory=list)
    polylines: list[PolylineEntity] = field(default_factory=list)
    circles: list[CircleEntity] = field(default_factory=list)
    arcs: list[ArcEntity] = field(default_factory=list)
    slots: list[SlotEntity] = field(default_factory=list)
    hatches: list[HatchEntity] = field(default_factory=list)
    texts: list[TextEntity] = field(default_factory=list)
    dimensions: list[LinearDimensionEntity] = field(default_factory=list)
    leaders: list[LeaderEntity] = field(default_factory=list)


def _rgb_to_aci(rgb: tuple[int, int, int]) -> int:
    return min(
        range(1, 256),
        key=lambda index: sum((channel - target) ** 2 for channel, target in zip(ezdxf_colors.aci2rgb(index), rgb)),
    )


def _nearest_lineweight(value_mm: float) -> int:
    requested = int(round(value_mm * 100))
    return min(ALLOWED_LINEWEIGHTS, key=lambda candidate: abs(candidate - requested))


def _standard_layer(spec: dict[str, Any]) -> LayerStyle:
    display_color = tuple(spec["display_color"])
    lineweight_mm = float(spec["lineweight_mm"])
    return LayerStyle(
        name=spec["name"],
        color=_rgb_to_aci(display_color),
        linetype=spec["linetype"],
        lineweight=_nearest_lineweight(lineweight_mm),
        parent=spec["parent"],
        semantic_role=spec["semantic_role"],
        display_color=display_color,
        plot_color=tuple(spec["plot_color"]),
        lineweight_mm=lineweight_mm,
        linetype_scale=float(spec["linetype_scale"]),
        plot=bool(spec["plot"]),
    )


def default_layers(standard_profile: str = GENERIC_PROFILE) -> list[LayerStyle]:
    if standard_profile == NOAH_URIU_2D_PROFILE:
        return [_standard_layer(spec) for spec in URIU_2D_LAYER_SPECS]
    return [
        LayerStyle("OUTLINE", color=7, lineweight=50, semantic_role="outline", lineweight_mm=0.50),
        LayerStyle("GEOMETRY", color=7, lineweight=35, semantic_role="geometry", lineweight_mm=0.35),
        LayerStyle("DETAIL", color=4, lineweight=18, semantic_role="detail", lineweight_mm=0.18),
        LayerStyle("HIDDEN", color=1, linetype="HIDDEN", lineweight=18, semantic_role="hidden", lineweight_mm=0.18),
        LayerStyle("CENTER", color=4, linetype="CENTER", lineweight=18, semantic_role="centerline", lineweight_mm=0.18),
        LayerStyle("HATCH", color=8, lineweight=13, semantic_role="hatch", lineweight_mm=0.13),
        LayerStyle("DIMENSIONS", color=2, lineweight=18, semantic_role="dimension", lineweight_mm=0.18),
        LayerStyle("TEXT", color=3, lineweight=18, semantic_role="text", lineweight_mm=0.18),
        LayerStyle("ANNOTATION", color=6, lineweight=18, semantic_role="note", lineweight_mm=0.18),
    ]


def _default_layer_style(name: str, standard_profile: str = GENERIC_PROFILE) -> LayerStyle:
    layers = default_layers(standard_profile)
    normalized_name = URIU_LEGACY_LAYER_ALIASES.get(name, name) if standard_profile == NOAH_URIU_2D_PROFILE else name
    return next((layer for layer in layers if layer.name == normalized_name), LayerStyle(normalized_name))


def _safe_name(value: Any, fallback: str) -> str:
    candidate = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value or "").strip())[:48]
    return candidate or fallback


def _entity_id(prefix: str, index: int, value: Any = None) -> str:
    return _safe_name(value, f"{prefix}_{index + 1:03d}")


def _normalize_units(value: Any, fallback: str = "mm") -> str:
    candidate = str(value or fallback or "mm").strip().lower()
    return candidate if candidate in UNIT_MAP else fallback


def _coerce_point(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        point = float(value[0]), float(value[1])
    except (TypeError, ValueError):
        return None
    return point if all(math.isfinite(axis) for axis in point) else None


def _coerce_points(
    values: Any, *, minimum: int = 2, maximum: int = MAX_POINTS_PER_ENTITY,
) -> list[tuple[float, float]]:
    if not isinstance(values, list):
        return []
    if len(values) > maximum:
        raise ValueError(f"Point list exceeds the {maximum}-point limit")
    points = [point for point in (_coerce_point(item) for item in values) if point is not None]
    return points if len(points) >= minimum else []


def _coerce_ring(values: Any) -> list[tuple[float, float]]:
    if not isinstance(values, list):
        return []
    if len(values) > MAX_POINTS_PER_ENTITY:
        raise ValueError(f"Hatch ring exceeds the {MAX_POINTS_PER_ENTITY}-point limit")
    points = [_coerce_point(item) for item in values]
    if any(point is None for point in points):
        raise ValueError("hatch rings cannot contain malformed points")
    return [point for point in points if point is not None] if len(points) >= 3 else []


def _coerce_float(value: Any, default: float) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


def _coerce_bounded_float(value: Any, default: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, _coerce_float(value, default)))


def _coerce_rgb(value: Any, default: tuple[int, int, int]) -> tuple[int, int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return default
    try:
        return tuple(max(0, min(255, int(channel))) for channel in value)  # type: ignore[return-value]
    except (TypeError, ValueError):
        return default


def _bounded_items(payload: dict[str, Any], key: str, maximum: int) -> list[Any]:
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    if len(value) > maximum:
        raise ValueError(f"{key} exceeds the {maximum}-entity limit")
    return value


def _layer_name(value: Any, fallback: str, standard_profile: str = GENERIC_PROFILE) -> str:
    raw = str(value or fallback or "").strip()
    raw = re.sub(r"[^A-Za-z0-9 _:\-]+", "_", raw)[:160].strip()
    normalized = raw or fallback
    if standard_profile == NOAH_URIU_2D_PROFILE:
        upper = normalized.upper()
        alias = URIU_LEGACY_LAYER_ALIASES.get(upper)
        if alias:
            return alias
        canonical = {spec["name"].upper(): spec["name"] for spec in URIU_2D_LAYER_SPECS}
        return canonical.get(upper, normalized)
    return _safe_name(normalized.upper(), fallback).upper()


def _infer_semantic_role(name: str) -> str:
    upper = name.upper()
    for token, role in (
        ("HATCH", "hatch"), ("DIM", "dimension"), ("TEXT", "text"), ("NOTES", "note"),
        ("HIDDEN", "hidden"), ("DASHED", "hidden"), ("CENTER", "centerline"),
        ("SECTION", "section_cut"), ("DETAIL", "detail"), ("OUTLINE", "outline"),
    ):
        if token in upper:
            return role
    return "geometry"


def _profile_layer_map() -> dict[str, LayerStyle]:
    return {layer.name: layer for layer in default_layers(NOAH_URIU_2D_PROFILE)}


def _layer_from_payload(item: dict[str, Any], standard_profile: str) -> LayerStyle | None:
    name = _layer_name(item.get("name"), "", standard_profile)
    if not name:
        return None
    base = _profile_layer_map().get(name) if standard_profile == NOAH_URIU_2D_PROFILE else None
    fallback_color = base.color if base else 7
    color = max(1, min(255, int(_coerce_float(item.get("color"), fallback_color))))
    fallback_display = base.display_color if base and base.display_color else tuple(ezdxf_colors.aci2rgb(color))
    display_color = _coerce_rgb(item.get("display_color"), fallback_display)
    if "display_color" in item and "color" not in item:
        color = _rgb_to_aci(display_color)
    fallback_plot = base.plot_color if base else display_color
    plot_color = _coerce_rgb(item.get("plot_color"), fallback_plot)
    linetype = str(item.get("linetype") or (base.linetype if base else "CONTINUOUS")).strip().upper()
    if linetype not in ALLOWED_LINETYPES:
        linetype = "CONTINUOUS"
    if item.get("lineweight_mm") is not None:
        lineweight_mm = _coerce_bounded_float(item.get("lineweight_mm"), 0.25, 0.0, 2.11)
    elif base and base.lineweight_mm is not None:
        lineweight_mm = base.lineweight_mm
    else:
        lineweight_mm = _coerce_bounded_float(item.get("lineweight"), 25, 0, 211) / 100
    base_parent = base.parent if base else None
    requested_parent = item.get("parent") or base_parent
    return LayerStyle(
        name=name,
        color=color,
        linetype=linetype,
        lineweight=_nearest_lineweight(lineweight_mm),
        parent=_layer_name(requested_parent, base_parent or "", standard_profile) if requested_parent else None,
        semantic_role=_safe_name(item.get("semantic_role"), base.semantic_role if base else _infer_semantic_role(name)).lower(),
        display_color=display_color,
        plot_color=plot_color,
        lineweight_mm=lineweight_mm,
        linetype_scale=_coerce_bounded_float(item.get("linetype_scale"), base.linetype_scale if base else 1.0, 0.01, 100.0),
        plot=_coerce_bool(item.get("plot"), base.plot if base else True),
    )


def _normalized_layers(payload: Any, standard_profile: str) -> list[LayerStyle]:
    layers: list[LayerStyle] = []
    if isinstance(payload, list) and len(payload) > MAX_LAYERS:
        raise ValueError(f"layers exceeds the {MAX_LAYERS}-layer limit")
    for item in payload if isinstance(payload, list) else []:
        if not isinstance(item, dict):
            continue
        layer = _layer_from_payload(item, standard_profile)
        if layer:
            layers.append(layer)
    if layers or standard_profile == NOAH_URIU_2D_PROFILE:
        return layers
    return default_layers()


def scene_from_payload(payload: dict[str, Any], *, requested_units: str = "mm") -> DrawingScene:
    if not isinstance(payload, dict):
        raise ValueError("Drawing scene must be a JSON object")
    incoming_version = payload.get("schema_version")
    if incoming_version is not None and str(incoming_version) not in {"1.0", "1.1", SCHEMA_VERSION}:
        raise ValueError(f"Unsupported DrawingScene schema_version: {incoming_version}")
    incoming_coordinates = payload.get("coordinate_system")
    if incoming_coordinates is not None and str(incoming_coordinates) != COORDINATE_SYSTEM:
        raise ValueError(f"Unsupported coordinate_system: {incoming_coordinates}")

    standard_profile = str(
        payload.get("standard_profile") or payload.get("drafting_standard") or GENERIC_PROFILE
    ).strip().upper()
    if standard_profile not in SUPPORTED_STANDARD_PROFILES:
        raise ValueError(f"Unsupported drafting standard: {standard_profile}")

    scene = DrawingScene(
        title=str(payload.get("title") or "NaturalCAD 2D Draft")[:120],
        units=_normalize_units(payload.get("units"), requested_units),
        standard_profile=standard_profile,
        layers=_normalized_layers(payload.get("layers"), standard_profile),
    )

    for index, item in enumerate(_bounded_items(payload, "polylines", MAX_POLYLINES)):
        if not isinstance(item, dict):
            continue
        points = _coerce_points(item.get("points"), minimum=2)
        if points:
            scene.polylines.append(PolylineEntity(
                id=_entity_id("polyline", index, item.get("id")),
                points=points,
                layer=_layer_name(item.get("layer"), "GEOMETRY", standard_profile),
                closed=_coerce_bool(item.get("closed")),
            ))

    for index, item in enumerate(_bounded_items(payload, "circles", MAX_CIRCLES)):
        if not isinstance(item, dict):
            continue
        center = _coerce_point(item.get("center"))
        radius = _coerce_float(item.get("radius"), 0.0)
        if center and radius > 0:
            scene.circles.append(CircleEntity(
                id=_entity_id("circle", index, item.get("id")),
                center=center,
                radius=radius,
                layer=_layer_name(item.get("layer"), "GEOMETRY", standard_profile),
            ))

    for index, item in enumerate(_bounded_items(payload, "arcs", MAX_ARCS)):
        if not isinstance(item, dict):
            continue
        center = _coerce_point(item.get("center"))
        radius = _coerce_float(item.get("radius"), 0.0)
        if center and radius > 0:
            scene.arcs.append(ArcEntity(
                id=_entity_id("arc", index, item.get("id")),
                center=center,
                radius=radius,
                start_angle=_coerce_float(item.get("start_angle"), 0.0) % 360,
                end_angle=_coerce_float(item.get("end_angle"), 90.0) % 360,
                layer=_layer_name(item.get("layer"), "GEOMETRY", standard_profile),
            ))

    for index, item in enumerate(_bounded_items(payload, "slots", MAX_SLOTS)):
        if not isinstance(item, dict):
            continue
        center = _coerce_point(item.get("center"))
        length = _coerce_float(item.get("length"), 0.0)
        width = _coerce_float(item.get("width"), 0.0)
        if center and length >= width > 0:
            scene.slots.append(SlotEntity(
                id=_entity_id("slot", index, item.get("id")),
                center=center,
                length=length,
                width=width,
                angle=_coerce_float(item.get("angle"), 0.0),
                layer=_layer_name(item.get("layer"), "GEOMETRY", standard_profile),
            ))

    for index, item in enumerate(_bounded_items(payload, "hatches", MAX_HATCHES)):
        if not isinstance(item, dict):
            continue
        boundary = _coerce_ring(item.get("boundary"))
        if boundary:
            raw_holes = item.get("holes", [])
            if raw_holes is None:
                raw_holes = []
            if not isinstance(raw_holes, list):
                raise ValueError("hatch holes must be a list of polygon rings")
            if len(raw_holes) > MAX_HATCH_HOLES:
                raise ValueError(f"hatch holes exceeds the {MAX_HATCH_HOLES}-ring limit")
            holes: list[list[tuple[float, float]]] = []
            for raw_hole in raw_holes:
                hole = _coerce_ring(raw_hole)
                if not hole:
                    raise ValueError("each hatch hole must contain at least three valid points")
                holes.append(hole)
            pattern = str(item.get("pattern") or "SOLID").strip().upper()
            scene.hatches.append(HatchEntity(
                id=_entity_id("hatch", index, item.get("id")),
                boundary=boundary,
                holes=holes,
                layer=_layer_name(item.get("layer"), "HATCH", standard_profile),
                pattern=pattern if pattern in ALLOWED_HATCH_PATTERNS else "SOLID",
                pattern_scale=_coerce_bounded_float(item.get("pattern_scale"), 1.0, 0.05, 100.0),
                pattern_angle=_coerce_float(item.get("pattern_angle"), 0.0) % 360,
                opacity=_coerce_bounded_float(item.get("opacity"), 0.18, 0.0, 1.0),
            ))

    for index, item in enumerate(_bounded_items(payload, "texts", MAX_TEXTS)):
        if not isinstance(item, dict):
            continue
        insert = _coerce_point(item.get("insert"))
        if insert:
            scene.texts.append(TextEntity(
                id=_entity_id("text", index, item.get("id")),
                text=str(item.get("text") or "")[:500],
                insert=insert,
                height=max(0.1, _coerce_float(item.get("height"), 3.0)),
                layer=_layer_name(item.get("layer"), "TEXT", standard_profile),
            ))

    for index, item in enumerate(_bounded_items(payload, "dimensions", MAX_DIMENSIONS)):
        if not isinstance(item, dict):
            continue
        start = _coerce_point(item.get("start"))
        end = _coerce_point(item.get("end"))
        if start and end and start != end:
            scene.dimensions.append(LinearDimensionEntity(
                id=_entity_id("dimension", index, item.get("id")),
                start=start,
                end=end,
                offset=max(0.1, _coerce_float(item.get("offset"), 10.0)),
                angle=_coerce_float(item.get("angle"), 0.0),
                text=str(item.get("text"))[:120] if item.get("text") is not None else None,
                layer=_layer_name(item.get("layer"), "DIMENSIONS", standard_profile),
            ))

    for index, item in enumerate(_bounded_items(payload, "leaders", MAX_LEADERS)):
        if not isinstance(item, dict):
            continue
        points = _coerce_points(item.get("points"), minimum=2)
        if points:
            scene.leaders.append(LeaderEntity(
                id=_entity_id("leader", index, item.get("id")),
                points=points,
                text=str(item.get("text") or REFERENCE_NOTE)[:500],
                text_height=max(0.1, _coerce_float(item.get("text_height"), 2.5)),
                layer=_layer_name(item.get("layer"), "ANNOTATION", standard_profile),
            ))

    if not any((scene.polylines, scene.circles, scene.arcs, scene.slots)):
        raise ValueError("Drawing scene contains no supported geometry")

    entity_count = sum(len(collection) for collection in (
        scene.polylines, scene.circles, scene.arcs, scene.slots, scene.hatches,
        scene.texts, scene.dimensions, scene.leaders,
    ))
    point_count = (
        sum(len(entity.points) for entity in scene.polylines)
        + sum(len(entity.boundary) + sum(map(len, entity.holes)) for entity in scene.hatches)
        + sum(len(entity.points) for entity in scene.leaders)
        + 2 * len(scene.dimensions)
        + len(scene.circles) + len(scene.arcs) + len(scene.slots) + len(scene.texts)
    )
    if entity_count > MAX_TOTAL_ENTITIES:
        raise ValueError(f"Drawing scene exceeds the {MAX_TOTAL_ENTITIES}-entity total limit")
    if point_count > MAX_TOTAL_POINTS:
        raise ValueError(f"Drawing scene exceeds the {MAX_TOTAL_POINTS}-point total limit")

    seen_ids: set[str] = set()
    for collection in (
        scene.polylines, scene.circles, scene.arcs, scene.slots, scene.hatches,
        scene.texts, scene.dimensions, scene.leaders,
    ):
        for entity in collection:
            base_id = entity.id
            suffix = 2
            while entity.id in seen_ids:
                entity.id = f"{base_id}_{suffix}"
                suffix += 1
            seen_ids.add(entity.id)

    referenced_layers = {
        entity.layer
        for collection in (
            scene.polylines, scene.circles, scene.arcs, scene.slots, scene.hatches,
            scene.texts, scene.dimensions, scene.leaders,
        )
        for entity in collection
    }
    existing_by_name = {layer.name: layer for layer in scene.layers}
    if standard_profile == NOAH_URIU_2D_PROFILE:
        profile_by_name = _profile_layer_map()
        unknown = referenced_layers - existing_by_name.keys() - profile_by_name.keys()
        if unknown:
            raise ValueError(f"Layers are not defined by {NOAH_URIU_2D_PROFILE}: {', '.join(sorted(unknown))}")
        ordered: list[LayerStyle] = []
        added: set[str] = set()

        def add_layer(name: str) -> None:
            if not name or name in added:
                return
            layer = existing_by_name.get(name) or profile_by_name.get(name)
            if layer is None:
                return
            if layer.parent:
                add_layer(layer.parent)
            ordered.append(layer)
            added.add(name)

        for name in (*existing_by_name.keys(), *sorted(referenced_layers)):
            add_layer(name)
        scene.layers = ordered
    else:
        scene.layers.extend(
            _default_layer_style(name, standard_profile)
            for name in sorted(referenced_layers - existing_by_name.keys())
        )
    return scene


def scene_to_dict(scene: DrawingScene) -> dict[str, Any]:
    return asdict(scene)


def scene_to_json(scene: DrawingScene) -> str:
    import json

    return json.dumps(scene_to_dict(scene), indent=2)


def scene_quality_report(scene: DrawingScene, *, intent_mode: str = "TECHNICAL_DRAFT") -> dict[str, Any]:
    geometry_points = (
        sum(len(entity.points) for entity in scene.polylines)
        + 2 * len(scene.circles)
        + 3 * len(scene.arcs)
        + 6 * len(scene.slots)
    )
    used_layers = {
        entity.layer
        for collection in (
            scene.polylines, scene.circles, scene.arcs, scene.slots, scene.hatches,
            scene.texts, scene.dimensions, scene.leaders,
        )
        for entity in collection
    }
    issues: list[str] = []
    annotation_count = len(scene.texts) + len(scene.dimensions) + len(scene.leaders)
    if intent_mode == "CREATIVE_CONCEPT":
        if len(scene.polylines) < 32:
            issues.append("Creative scene has fewer than 32 editable polylines")
        if geometry_points < 96:
            issues.append("Creative scene has fewer than 96 geometry control points")
        if len(scene.hatches) < 2:
            issues.append("Creative scene has fewer than two hatch or shadow regions")
        if len(used_layers) < 3:
            issues.append("Creative scene uses fewer than three semantic CAD layers")
        if scene.dimensions:
            issues.append("Conceptual scene includes unrequested dimension objects")
        if len(scene.leaders) > 4:
            issues.append("Conceptual scene uses more than four leaders")
        if len(scene.texts) > 2:
            issues.append("Conceptual scene uses more than two free text labels")
    else:
        if len(used_layers) < 2:
            issues.append("Technical scene uses fewer than two semantic CAD layers")
        if len(scene.dimensions) > 8:
            issues.append("Technical scene uses more than eight dimensions")
        if len(scene.leaders) > 4:
            issues.append("Technical scene uses more than four leaders")
        if len(scene.texts) > 6:
            issues.append("Technical scene uses more than six free text labels")
    if annotation_count > 16:
        issues.append("Scene contains more than sixteen annotation objects")
    return {
        "status": "pass" if not issues else "needs_refinement",
        "issues": issues,
        "geometry_points": geometry_points,
        "annotation_count": annotation_count,
        "used_layers": sorted(used_layers),
        "standard_profile": scene.standard_profile,
    }


def _extract_first(prompt: str, pattern: str, default: float) -> float:
    match = re.search(pattern, prompt, re.IGNORECASE)
    if not match:
        return default
    return _coerce_float(match.group(1), default)


def build_fallback_scene(prompt: str, units: str) -> DrawingScene:
    """Build a visibly labelled local demo, never presented as model output."""
    prompt = (prompt or "").strip()
    pair = re.search(r"(\d+(?:\.\d+)?)\s*[xX]\s*(\d+(?:\.\d+)?)", prompt)
    width, height = (float(pair.group(1)), float(pair.group(2))) if pair else (180.0, 90.0)
    margin = min(width, height) * 0.15
    hole_diameter = _extract_first(prompt, r"(\d+(?:\.\d+)?)\s*mm\s+(?:corner\s+)?holes?", 12.0)
    outline = [
        (-width / 2, -height / 2), (width / 2, -height / 2),
        (width / 2, height / 2), (-width / 2, height / 2),
    ]
    scene = DrawingScene(
        title="NaturalCAD 2D Demo",
        units=_normalize_units(units),
        standard_profile=NOAH_URIU_2D_PROFILE,
        layers=default_layers(NOAH_URIU_2D_PROFILE),
    )
    scene.polylines.append(PolylineEntity(
        "outline", outline, layer=URIU_LEGACY_LAYER_ALIASES["OUTLINE"], closed=True,
    ))
    scene.hatches.append(HatchEntity(
        "body_hatch", outline, layer=URIU_LEGACY_LAYER_ALIASES["HATCH"],
    ))

    slot_match = re.search(r"(\d+)\s+slots?", prompt, re.IGNORECASE)
    if slot_match or "slot" in prompt.lower():
        count = max(1, min(4, int(slot_match.group(1)) if slot_match else 2))
        spacing = width / (count + 1)
        for index in range(count):
            scene.slots.append(SlotEntity(
                id=f"slot_{index + 1:03d}",
                center=(-width / 2 + spacing * (index + 1), 0.0),
                length=max(24.0, width * 0.16),
                width=max(8.0, min(height * 0.16, 14.0)),
                layer=URIU_LEGACY_LAYER_ALIASES["GEOMETRY"],
            ))
    else:
        positions = [
            (-width / 2 + margin, -height / 2 + margin),
            (width / 2 - margin, -height / 2 + margin),
            (width / 2 - margin, height / 2 - margin),
            (-width / 2 + margin, height / 2 - margin),
        ]
        for index, center in enumerate(positions):
            scene.circles.append(CircleEntity(
                f"hole_{index + 1:03d}", center, hole_diameter / 2,
                layer=URIU_LEGACY_LAYER_ALIASES["GEOMETRY"],
            ))

    scene.polylines.append(PolylineEntity(
        "horizontal_centerline", [(-width / 2 - 20, 0), (width / 2 + 20, 0)],
        layer=URIU_LEGACY_LAYER_ALIASES["CENTER"],
    ))
    scene.texts.append(TextEntity(
        "drawing_title", prompt or "2D drafting study", (-width / 2, height / 2 + 22),
        max(3.0, min(width, height) * 0.05),
        layer=URIU_LEGACY_LAYER_ALIASES["TEXT"],
    ))
    scene.dimensions.extend([
        LinearDimensionEntity(
            "overall_width", (-width / 2, -height / 2), (width / 2, -height / 2),
            20.0, layer=URIU_LEGACY_LAYER_ALIASES["DIMENSIONS"], text=f"{width:g} {scene.units}",
        ),
        LinearDimensionEntity(
            "overall_height", (width / 2, -height / 2), (width / 2, height / 2),
            22.0, layer=URIU_LEGACY_LAYER_ALIASES["DIMENSIONS"], angle=90.0, text=f"{height:g} {scene.units}",
        ),
    ])
    scene.leaders.append(LeaderEntity(
        "accuracy_note",
        [(width / 2 - margin, height / 2 - margin), (width / 2 + 18, height / 2 + 18)],
        REFERENCE_NOTE,
        max(2.5, min(width, height) * 0.035),
        layer=URIU_LEGACY_LAYER_ALIASES["ANNOTATION"],
    ))
    return scene


def _slot_points(slot: SlotEntity) -> tuple[tuple[float, float], ...]:
    angle = math.radians(slot.angle)
    ux, uy = math.cos(angle), math.sin(angle)
    px, py = -uy, ux
    radius = slot.width / 2
    center_distance = max(0.0, slot.length - slot.width) / 2
    left = (slot.center[0] - ux * center_distance, slot.center[1] - uy * center_distance)
    right = (slot.center[0] + ux * center_distance, slot.center[1] + uy * center_distance)
    return (
        (left[0] + px * radius, left[1] + py * radius),
        (right[0] + px * radius, right[1] + py * radius),
        (right[0] - px * radius, right[1] - py * radius),
        (left[0] - px * radius, left[1] - py * radius),
        left,
        right,
    )


def scene_bounds(scene: DrawingScene) -> tuple[float, float, float, float]:
    points: list[tuple[float, float]] = []
    points.extend(point for entity in scene.polylines for point in entity.points)
    points.extend(point for entity in scene.hatches for point in entity.boundary)
    points.extend(point for entity in scene.leaders for point in entity.points)
    points.extend(entity.insert for entity in scene.texts)
    points.extend(point for entity in scene.dimensions for point in (entity.start, entity.end))
    for entity in (*scene.circles, *scene.arcs):
        points.extend([
            (entity.center[0] - entity.radius, entity.center[1] - entity.radius),
            (entity.center[0] + entity.radius, entity.center[1] + entity.radius),
        ])
    for slot in scene.slots:
        points.extend(_slot_points(slot)[:4])
    if not points:
        return -100.0, -100.0, 100.0, 100.0
    xs, ys = zip(*points)
    return min(xs), min(ys), max(xs), max(ys)


def _svg_point(
    point: tuple[float, float], bounds: tuple[float, float, float, float], size: int, padding: int,
) -> tuple[float, float]:
    min_x, min_y, max_x, max_y = bounds
    scale = min((size - 2 * padding) / max(max_x - min_x, 1), (size - 2 * padding) / max(max_y - min_y, 1))
    return padding + (point[0] - min_x) * scale, size - padding - (point[1] - min_y) * scale


def _svg_layer_style(scene: DrawingScene, layer_name: str) -> LayerStyle:
    return next(
        (candidate for candidate in scene.layers if candidate.name == layer_name),
        _default_layer_style(layer_name, scene.standard_profile),
    )


def _aci_svg_color(color_index: int) -> str:
    try:
        red, green, blue = ezdxf_colors.aci2rgb(color_index)
    except (IndexError, ValueError):
        return "#e2e8f0"
    return f"#{red:02x}{green:02x}{blue:02x}"


def _rgb_svg_color(rgb: tuple[int, int, int]) -> str:
    return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"


def _svg_layer_color(
    scene: DrawingScene,
    layer_name: str,
    *,
    plot_mode: bool = False,
    monochrome: bool = False,
) -> str:
    layer = _svg_layer_style(scene, layer_name)
    if monochrome and not plot_mode:
        return "#ffffff"
    rgb = layer.plot_color if plot_mode else layer.display_color
    return _rgb_svg_color(rgb) if rgb is not None else _aci_svg_color(layer.color)


def _svg_layer_stroke(
    scene: DrawingScene,
    layer_name: str,
    *,
    plot_mode: bool = False,
    monochrome: bool = False,
) -> tuple[str, float, str]:
    layer = _svg_layer_style(scene, layer_name)
    color = _svg_layer_color(
        scene, layer_name, plot_mode=plot_mode, monochrome=monochrome,
    )
    lineweight_mm = layer.lineweight_mm if layer.lineweight_mm is not None else layer.lineweight / 100
    width = max(0.6, min(8.0, lineweight_mm * 8.0))
    dash_by_linetype = {
        "CENTER": "14 5 3 5",
        "CENTER2": "10 4 2 4",
        "DASHED": "9 6",
        "DASHED2": "6 4",
        "HIDDEN": "7 5",
        "PHANTOM": "18 5 3 5 3 5",
        "PHANTOM2": "12 4 2 4 2 4",
        "DASHDOT": "10 4 2 4",
        "DASHDOT2": "7 3 2 3",
        "DOT": "2 4",
        "DOT2": "1 3",
    }
    base_dash = dash_by_linetype.get(layer.linetype, "")
    dash = " ".join(
        f"{float(value) * layer.linetype_scale:g}" for value in base_dash.split()
    ) if base_dash else ""
    return color, width, dash


def _svg_hatch_path(hatch: HatchEntity, map_point: Any) -> str:
    commands: list[str] = []
    for ring in (hatch.boundary, *hatch.holes):
        mapped = list(map(map_point, ring))
        commands.append("M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in mapped) + " Z")
    return " ".join(commands)


def _configure_document(document: ezdxf.document.Drawing, units: str) -> None:
    document.units = UNIT_MAP.get(units, ezdxf_units.MM)
    document.header["$MEASUREMENT"] = 0 if units in {"in", "ft"} else 1


def _configure_dxf_hatch(hatch: Any, entity: HatchEntity) -> None:
    hatch.dxf.hatch_style = ezdxf_const.HATCH_STYLE_NESTED
    hatch.paths.add_polyline_path(
        entity.boundary,
        is_closed=True,
        flags=ezdxf_const.BOUNDARY_PATH_EXTERNAL,
    )
    for hole in entity.holes:
        hatch.paths.add_polyline_path(
            hole,
            is_closed=True,
            flags=ezdxf_const.BOUNDARY_PATH_DEFAULT,
        )
    if entity.pattern != "SOLID":
        hatch.set_pattern_fill(
            entity.pattern,
            color=256,
            scale=entity.pattern_scale,
            angle=entity.pattern_angle,
            style=ezdxf_const.HATCH_STYLE_NESTED,
        )


def _preview_hatch_segments(
    scene: DrawingScene,
    entity: HatchEntity,
    limit: int,
) -> tuple[list[tuple[tuple[float, float], tuple[float, float]]], bool]:
    if entity.pattern == "SOLID" or limit <= 0:
        return [], limit <= 0 and entity.pattern != "SOLID"
    document = ezdxf.new("R2010", setup=True)
    _configure_document(document, scene.units)
    hatch = document.modelspace().add_hatch(color=256)
    _configure_dxf_hatch(hatch, entity)
    raw_segments = list(itertools.islice(
        ezdxf_hatching.hatch_entity(hatch, jiggle_origin=False),
        limit + 1,
    ))
    simplified = len(raw_segments) > limit
    raw_segments = raw_segments[:limit]
    return [
        (((float(start.x), float(start.y))), ((float(end.x), float(end.y))))
        for start, end in raw_segments
    ], simplified


def _dimension_text(entity: LinearDimensionEntity, units: str) -> str:
    if entity.text:
        return entity.text
    length = math.dist(entity.start, entity.end)
    value = f"{length:.2f}".rstrip("0").rstrip(".")
    return f"{value} {units}"


def render_svg(
    scene: DrawingScene,
    *,
    plot_mode: bool = False,
    monochrome: bool = True,
) -> str:
    size, padding = 860, 56
    bounds = scene_bounds(scene)
    map_point = lambda point: _svg_point(point, bounds, size, padding)
    span_x = max(bounds[2] - bounds[0], 1)
    span_y = max(bounds[3] - bounds[1], 1)
    scale = min((size - 2 * padding) / span_x, (size - 2 * padding) / span_y)
    preview_segments: dict[str, list[tuple[tuple[float, float], tuple[float, float]]]] = {}
    preview_simplified = False
    remaining_segments = MAX_PREVIEW_SEGMENTS_TOTAL
    for hatch in scene.hatches:
        if hatch.pattern == "SOLID":
            continue
        try:
            segments, simplified = _preview_hatch_segments(
                scene, hatch, min(MAX_PREVIEW_SEGMENTS_PER_HATCH, remaining_segments),
            )
        except Exception:
            segments, simplified = [], True
        preview_segments[hatch.id] = segments
        remaining_segments -= len(segments)
        preview_simplified = preview_simplified or simplified

    simplified_attr = ' data-preview-simplified="true"' if preview_simplified else ""
    background = "#ffffff" if plot_mode else "#000000"
    field = "#ffffff" if plot_mode else "#000000"
    border = "#cbd5e1" if plot_mode else "#333333"
    display_mode = "plot" if plot_mode else ("monochrome" if monochrome else "working-color")
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="100%" role="img" '
        f'aria-label="{html.escape(scene.title)}" data-standard-profile="{html.escape(scene.standard_profile)}" '
        f'data-display-mode="{display_mode}"{simplified_attr}>',
        f'<rect width="100%" height="100%" fill="{background}"/>',
        f'<rect x="14" y="14" width="832" height="832" rx="4" fill="{field}" stroke="{border}" stroke-width="1"/>',
    ]
    if not plot_mode:
        parts.extend([
            '<defs><pattern id="naturalcad-dot-grid" width="18" height="18" patternUnits="userSpaceOnUse">'
            '<circle cx="1" cy="1" r="0.55" fill="#141414"/></pattern></defs>',
            '<rect x="15" y="15" width="830" height="830" fill="url(#naturalcad-dot-grid)"/>',
        ])
    for hatch in scene.hatches:
        layer = _svg_layer_style(scene, hatch.layer)
        if plot_mode and not layer.plot:
            continue
        color = _svg_layer_color(
            scene, hatch.layer, plot_mode=plot_mode, monochrome=monochrome,
        )
        common = (
            f'data-entity-id="{html.escape(hatch.id)}" data-layer="{html.escape(hatch.layer)}" '
            f'data-role="{html.escape(layer.semantic_role)}" data-pattern="{html.escape(hatch.pattern)}"'
        )
        if hatch.pattern == "SOLID":
            parts.append(
                f'<path {common} d="{_svg_hatch_path(hatch, map_point)}" fill="{color}" '
                f'fill-opacity="{hatch.opacity:.3f}" fill-rule="evenodd" clip-rule="evenodd"/>'
            )
        else:
            path_commands: list[str] = []
            for start, end in preview_segments.get(hatch.id, []):
                p1, p2 = map_point(start), map_point(end)
                path_commands.append(f"M {p1[0]:.2f},{p1[1]:.2f} L {p2[0]:.2f},{p2[1]:.2f}")
            parts.append(
                f'<path {common} d="{" ".join(path_commands)}" fill="none" stroke="{color}" '
                f'stroke-width="0.8" stroke-opacity="{hatch.opacity:.3f}"/>'
            )
    for polyline in scene.polylines:
        layer = _svg_layer_style(scene, polyline.layer)
        if plot_mode and not layer.plot:
            continue
        mapped = list(map(map_point, polyline.points))
        path = " ".join(f"{x:.2f},{y:.2f}" for x, y in mapped)
        color, stroke_width, dash_pattern = _svg_layer_stroke(
            scene, polyline.layer, plot_mode=plot_mode, monochrome=monochrome,
        )
        dash = f' stroke-dasharray="{dash_pattern}"' if dash_pattern else ""
        close = " Z" if polyline.closed else ""
        parts.append(f'<path data-entity-id="{html.escape(polyline.id)}" data-layer="{html.escape(polyline.layer)}" data-role="{html.escape(layer.semantic_role)}" d="M {path}{close}" fill="none" stroke="{color}" stroke-width="{stroke_width:.2f}"{dash}/>')
    for circle in scene.circles:
        layer = _svg_layer_style(scene, circle.layer)
        if plot_mode and not layer.plot:
            continue
        cx, cy = map_point(circle.center)
        color, stroke_width, dash_pattern = _svg_layer_stroke(
            scene, circle.layer, plot_mode=plot_mode, monochrome=monochrome,
        )
        dash = f' stroke-dasharray="{dash_pattern}"' if dash_pattern else ""
        parts.append(f'<circle data-entity-id="{html.escape(circle.id)}" data-layer="{html.escape(circle.layer)}" data-role="{html.escape(layer.semantic_role)}" cx="{cx:.2f}" cy="{cy:.2f}" r="{circle.radius * scale:.2f}" fill="none" stroke="{color}" stroke-width="{stroke_width:.2f}"{dash}/>')
    for arc in scene.arcs:
        layer = _svg_layer_style(scene, arc.layer)
        if plot_mode and not layer.plot:
            continue
        start = (
            arc.center[0] + arc.radius * math.cos(math.radians(arc.start_angle)),
            arc.center[1] + arc.radius * math.sin(math.radians(arc.start_angle)),
        )
        end = (
            arc.center[0] + arc.radius * math.cos(math.radians(arc.end_angle)),
            arc.center[1] + arc.radius * math.sin(math.radians(arc.end_angle)),
        )
        sx, sy = map_point(start)
        ex, ey = map_point(end)
        delta = (arc.end_angle - arc.start_angle) % 360
        large = 1 if delta > 180 else 0
        color, stroke_width, dash_pattern = _svg_layer_stroke(
            scene, arc.layer, plot_mode=plot_mode, monochrome=monochrome,
        )
        dash = f' stroke-dasharray="{dash_pattern}"' if dash_pattern else ""
        parts.append(f'<path data-entity-id="{html.escape(arc.id)}" data-layer="{html.escape(arc.layer)}" data-role="{html.escape(layer.semantic_role)}" d="M {sx:.2f},{sy:.2f} A {arc.radius * scale:.2f},{arc.radius * scale:.2f} 0 {large} 0 {ex:.2f},{ey:.2f}" fill="none" stroke="{color}" stroke-width="{stroke_width:.2f}"{dash}/>')
    for slot in scene.slots:
        layer = _svg_layer_style(scene, slot.layer)
        if plot_mode and not layer.plot:
            continue
        top_left, top_right, bottom_right, bottom_left, _, _ = _slot_points(slot)
        tl, tr, br, bl = map(map_point, (top_left, top_right, bottom_right, bottom_left))
        radius = slot.width / 2 * scale
        color, stroke_width, dash_pattern = _svg_layer_stroke(
            scene, slot.layer, plot_mode=plot_mode, monochrome=monochrome,
        )
        dash = f' stroke-dasharray="{dash_pattern}"' if dash_pattern else ""
        parts.append(
            f'<path data-entity-id="{html.escape(slot.id)}" data-layer="{html.escape(slot.layer)}" data-role="{html.escape(layer.semantic_role)}" d="M {tl[0]:.2f},{tl[1]:.2f} L {tr[0]:.2f},{tr[1]:.2f} '
            f'A {radius:.2f},{radius:.2f} 0 0 1 {br[0]:.2f},{br[1]:.2f} L {bl[0]:.2f},{bl[1]:.2f} '
            f'A {radius:.2f},{radius:.2f} 0 0 1 {tl[0]:.2f},{tl[1]:.2f} Z" fill="none" stroke="{color}" stroke-width="{stroke_width:.2f}"{dash}/>'
        )
    for dimension in scene.dimensions:
        layer = _svg_layer_style(scene, dimension.layer)
        if plot_mode and not layer.plot:
            continue
        source_p1, source_p2 = map_point(dimension.start), map_point(dimension.end)
        p1, p2 = source_p1, source_p2
        offset = dimension.offset * scale
        if abs(dimension.angle % 180 - 90) < 0.01:
            p1, p2 = (p1[0] + offset, p1[1]), (p2[0] + offset, p2[1])
        else:
            p1, p2 = (p1[0], p1[1] + offset), (p2[0], p2[1] + offset)
        color, stroke_width, dash_pattern = _svg_layer_stroke(
            scene, dimension.layer, plot_mode=plot_mode, monochrome=monochrome,
        )
        dash = f' stroke-dasharray="{dash_pattern}"' if dash_pattern else ""
        common = (
            f'data-entity-id="{html.escape(dimension.id)}" data-layer="{html.escape(dimension.layer)}" '
            f'data-role="{html.escape(layer.semantic_role)}" data-annotation-kind="dimension"'
        )
        parts.append(
            f'<g {common} stroke="{color}" fill="{color}" '
            'font-family="ui-monospace, SFMono-Regular, Menlo, monospace">'
            f'<line x1="{source_p1[0]:.2f}" y1="{source_p1[1]:.2f}" x2="{p1[0]:.2f}" y2="{p1[1]:.2f}" '
            f'stroke-width="0.7" opacity="0.65"/>'
            f'<line x1="{source_p2[0]:.2f}" y1="{source_p2[1]:.2f}" x2="{p2[0]:.2f}" y2="{p2[1]:.2f}" '
            f'stroke-width="0.7" opacity="0.65"/>'
            f'<line x1="{p1[0]:.2f}" y1="{p1[1]:.2f}" x2="{p2[0]:.2f}" y2="{p2[1]:.2f}" '
            f'stroke-width="{stroke_width:.2f}"{dash}/>'
            f'<path d="M {p1[0] - 4:.2f},{p1[1] + 4:.2f} L {p1[0] + 4:.2f},{p1[1] - 4:.2f} '
            f'M {p2[0] - 4:.2f},{p2[1] + 4:.2f} L {p2[0] + 4:.2f},{p2[1] - 4:.2f}" '
            f'fill="none" stroke-width="{max(0.9, stroke_width):.2f}"/>'
            f'<text x="{(p1[0] + p2[0]) / 2:.2f}" y="{(p1[1] + p2[1]) / 2 - 7:.2f}" '
            f'font-size="13" fill="{color}" stroke="{field}" stroke-width="5" paint-order="stroke" '
            f'text-anchor="middle" letter-spacing="0.35">{html.escape(_dimension_text(dimension, scene.units))}</text>'
            '</g>'
        )
    for leader in scene.leaders:
        layer = _svg_layer_style(scene, leader.layer)
        if plot_mode and not layer.plot:
            continue
        mapped = list(map(map_point, leader.points))
        points = " ".join(f"{x:.2f},{y:.2f}" for x, y in mapped)
        color, stroke_width, dash_pattern = _svg_layer_stroke(
            scene, leader.layer, plot_mode=plot_mode, monochrome=monochrome,
        )
        dash = f' stroke-dasharray="{dash_pattern}"' if dash_pattern else ""
        x, y = mapped[-1]
        landing_direction = -1 if x > size * 0.68 else 1
        landing_end = x + landing_direction * 24
        text_x = landing_end + landing_direction * 6
        anchor = "end" if landing_direction < 0 else "start"
        arrow = ""
        if len(mapped) >= 2:
            tip, next_point = mapped[0], mapped[1]
            dx, dy = next_point[0] - tip[0], next_point[1] - tip[1]
            magnitude = math.hypot(dx, dy)
            if magnitude > 1e-6:
                ux, uy = dx / magnitude, dy / magnitude
                px, py = -uy, ux
                base_x, base_y = tip[0] + ux * 9, tip[1] + uy * 9
                arrow = (
                    f'<path d="M {tip[0]:.2f},{tip[1]:.2f} L {base_x + px * 3.5:.2f},{base_y + py * 3.5:.2f} '
                    f'L {base_x - px * 3.5:.2f},{base_y - py * 3.5:.2f} Z" fill="{color}" stroke="none"/>'
                )
        parts.append(
            f'<g data-entity-id="{html.escape(leader.id)}" data-layer="{html.escape(leader.layer)}" '
            f'data-role="{html.escape(layer.semantic_role)}" data-annotation-kind="leader" '
            'font-family="ui-monospace, SFMono-Regular, Menlo, monospace">'
            f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="{stroke_width:.2f}"{dash}/>'
            f'{arrow}<line x1="{x:.2f}" y1="{y:.2f}" x2="{landing_end:.2f}" y2="{y:.2f}" '
            f'stroke="{color}" stroke-width="{stroke_width:.2f}"/>'
            f'<text x="{text_x:.2f}" y="{y - 5:.2f}" font-size="12" fill="{color}" stroke="{field}" '
            f'stroke-width="5" paint-order="stroke" text-anchor="{anchor}" letter-spacing="0.35">'
            f'{html.escape(leader.text)}</text></g>'
        )
    for text_entity in scene.texts:
        layer = _svg_layer_style(scene, text_entity.layer)
        if plot_mode and not layer.plot:
            continue
        x, y = map_point(text_entity.insert)
        color = _svg_layer_color(
            scene, text_entity.layer, plot_mode=plot_mode, monochrome=monochrome,
        )
        font_size = max(10.0, min(24.0, text_entity.height * scale))
        anchor = "end" if x > size - 120 else "start"
        parts.append(
            f'<text data-entity-id="{html.escape(text_entity.id)}" data-layer="{html.escape(text_entity.layer)}" '
            f'data-role="{html.escape(layer.semantic_role)}" data-annotation-kind="text" '
            f'x="{x:.2f}" y="{y:.2f}" font-size="{font_size:.2f}" fill="{color}" stroke="{field}" '
            f'stroke-width="5" paint-order="stroke" text-anchor="{anchor}" letter-spacing="0.4" '
            f'font-family="ui-monospace, SFMono-Regular, Menlo, monospace">{html.escape(text_entity.text)}</text>'
        )
    if not plot_mode:
        parts.extend([
            '<g stroke="#ffffff" stroke-width="1.4" fill="#ffffff" opacity="0.9" '
            'font-family="ui-monospace, SFMono-Regular, Menlo, monospace" font-size="11">'
            '<line x1="38" y1="806" x2="60" y2="806"/><path d="M 60 806 L 55 803 L 55 809 Z" stroke="none"/>'
            '<line x1="38" y1="806" x2="38" y2="784"/><path d="M 38 784 L 35 789 L 41 789 Z" stroke="none"/>'
            '<circle cx="38" cy="806" r="1.5" fill="none"/><text x="65" y="810" stroke="none">X</text>'
            '<text x="34" y="778" stroke="none">Y</text></g>',
            '<g stroke="#475569" stroke-width="1" fill="none">'
            '<path d="M 14 34 L 14 14 L 34 14 M 826 14 L 846 14 L 846 34 '
            'M 14 826 L 14 846 L 34 846 M 826 846 L 846 846 L 846 826"/></g>',
        ])
    parts.append("</svg>")
    return "".join(parts)


def _flatten_dxf_layer_name(name: str) -> str:
    flattened = name.replace("::", "$")
    flattened = re.sub(r'[<>/\\":;?*|=,]+', "_", flattened).strip()[:255]
    return flattened or "NATURALCAD"


def _dxf_layer_map(scene: DrawingScene) -> dict[str, str]:
    result: dict[str, str] = {}
    claimed: dict[str, str] = {}
    for layer in scene.layers:
        candidate = _flatten_dxf_layer_name(layer.name)
        key = candidate.casefold()
        if key in claimed and claimed[key] != layer.name:
            suffix = hashlib.sha1(layer.name.encode("utf-8")).hexdigest()[:7]
            candidate = f"{candidate[:247]}${suffix}"
            key = candidate.casefold()
        result[layer.name] = candidate
        claimed[key] = layer.name
    return result


def _dxf_entity_attribs(layer_name: str, layer_map: dict[str, str], layer: LayerStyle) -> dict[str, Any]:
    return {
        "layer": layer_map[layer_name],
        "color": 256,
        "ltscale": layer.linetype_scale,
    }


def export_dxf(scene: DrawingScene, path: Path) -> None:
    document = ezdxf.new("R2010", setup=True)
    _configure_document(document, scene.units)
    if not document.appids.has_entry("NATURALCAD"):
        document.appids.add("NATURALCAD")
    layer_map = _dxf_layer_map(scene)
    styles = {layer.name: layer for layer in scene.layers}
    for layer in scene.layers:
        export_name = layer_map[layer.name]
        if export_name not in document.layers:
            record = document.layers.add(
                export_name,
                color=layer.color,
                linetype=layer.linetype,
                lineweight=_nearest_lineweight(layer.lineweight_mm if layer.lineweight_mm is not None else layer.lineweight / 100),
            )
            if layer.display_color is not None:
                record.rgb = layer.display_color
            record.dxf.plot = int(layer.plot)
            record.set_xdata("NATURALCAD", [
                (1000, "LAYER_STANDARD_V1"),
                (1000, layer.name),
                (1000, layer.parent or ""),
                (1000, layer.semantic_role),
                (1000, ",".join(map(str, layer.plot_color))),
                (1040, layer.lineweight_mm if layer.lineweight_mm is not None else layer.lineweight / 100),
            ])
    modelspace = document.modelspace()
    for entity in scene.polylines:
        modelspace.add_lwpolyline(
            entity.points,
            close=entity.closed,
            dxfattribs=_dxf_entity_attribs(entity.layer, layer_map, styles[entity.layer]),
        )
    for entity in scene.circles:
        modelspace.add_circle(
            entity.center,
            entity.radius,
            dxfattribs=_dxf_entity_attribs(entity.layer, layer_map, styles[entity.layer]),
        )
    for entity in scene.arcs:
        modelspace.add_arc(
            entity.center,
            entity.radius,
            entity.start_angle,
            entity.end_angle,
            dxfattribs=_dxf_entity_attribs(entity.layer, layer_map, styles[entity.layer]),
        )
    for entity in scene.slots:
        top_left, top_right, bottom_right, bottom_left, left, right = _slot_points(entity)
        attribs = _dxf_entity_attribs(entity.layer, layer_map, styles[entity.layer])
        modelspace.add_line(top_left, top_right, dxfattribs=attribs)
        modelspace.add_arc(right, entity.width / 2, entity.angle - 90, entity.angle + 90, dxfattribs=attribs)
        modelspace.add_line(bottom_right, bottom_left, dxfattribs=attribs)
        modelspace.add_arc(left, entity.width / 2, entity.angle + 90, entity.angle + 270, dxfattribs=attribs)
    for entity in scene.hatches:
        hatch = modelspace.add_hatch(
            dxfattribs=_dxf_entity_attribs(entity.layer, layer_map, styles[entity.layer]),
        )
        _configure_dxf_hatch(hatch, entity)
    for entity in scene.texts:
        attribs = _dxf_entity_attribs(entity.layer, layer_map, styles[entity.layer])
        attribs["height"] = entity.height
        modelspace.add_text(entity.text, dxfattribs=attribs).set_placement(entity.insert)
    for entity in scene.dimensions:
        if abs(entity.angle % 180 - 90) < 0.01:
            base = (entity.start[0] + entity.offset, (entity.start[1] + entity.end[1]) / 2)
        else:
            base = ((entity.start[0] + entity.end[0]) / 2, entity.start[1] - entity.offset)
        dimension = modelspace.add_linear_dim(
            base=base, p1=entity.start, p2=entity.end, angle=entity.angle,
            dxfattribs=_dxf_entity_attribs(entity.layer, layer_map, styles[entity.layer]),
            override={"dimtad": 1},
        )
        if entity.text:
            dimension.dimension.dxf.text = entity.text
        dimension.render()
    for entity in scene.leaders:
        attribs = _dxf_entity_attribs(entity.layer, layer_map, styles[entity.layer])
        modelspace.add_lwpolyline(entity.points, dxfattribs=attribs)
        text_attribs = {**attribs, "height": entity.text_height}
        modelspace.add_text(entity.text, dxfattribs=text_attribs).set_placement(entity.points[-1])
    document.saveas(path)
