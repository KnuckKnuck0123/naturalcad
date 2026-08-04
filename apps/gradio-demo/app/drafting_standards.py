"""Portable drafting standards derived from Noah's URIU Rhino layer template.

The source template remains external and untouched:
``Documents/Library/Rhino Resources/Rhino Scripts/CreateUALayers.py``.
Only the explicit layer intent, RGB working colors, linetypes, and print widths
are represented here. DXF exporters flatten Rhino ``::`` paths at export time.
"""

from __future__ import annotations

from typing import Any

NOAH_URIU_2D_PROFILE = "NOAH_URIU_2D_V1"
GENERIC_PROFILE = "NATURALCAD_GENERIC_V1"
SUPPORTED_STANDARD_PROFILES = {GENERIC_PROFILE, NOAH_URIU_2D_PROFILE}

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
BLUE = (0, 0, 255)
GOLD = (255, 215, 0)
TURQUOISE = (64, 224, 208)
DARK_GREY = (169, 169, 169)
LIGHT_GREY = (211, 211, 211)
LIME = (0, 255, 0)
RED = (255, 0, 0)
OLIVE_DRAB = (107, 142, 35)
CADET_BLUE = (95, 158, 160)
STEEL_BLUE = (70, 130, 180)
CHARTREUSE = (127, 255, 0)
SALMON = (250, 128, 114)
DARK_ORANGE = (255, 140, 0)
MAGENTA = (255, 0, 255)


def _layer(
    name: str,
    *,
    parent: str | None = None,
    semantic_role: str = "container",
    display_color: tuple[int, int, int] = WHITE,
    plot_color: tuple[int, int, int] = BLACK,
    lineweight_mm: float = 0.18,
    linetype: str = "CONTINUOUS",
    linetype_scale: float = 1.0,
    plot: bool = True,
) -> dict[str, Any]:
    return {
        "name": name,
        "parent": parent,
        "semantic_role": semantic_role,
        "display_color": display_color,
        "plot_color": plot_color,
        "lineweight_mm": lineweight_mm,
        "linetype": linetype,
        "linetype_scale": linetype_scale,
        "plot": plot,
    }


URIU_2D_LAYER_SPECS = [
    _layer("A-2D", plot=False),
    _layer("A-2D::A-PLAN", parent="A-2D", plot=False),
    _layer("A-2D::A-PLAN::A-WALL", parent="A-2D::A-PLAN", semantic_role="plan_wall", display_color=BLUE, lineweight_mm=0.35),
    _layer("A-2D::A-PLAN::A-DOOR", parent="A-2D::A-PLAN", semantic_role="plan_door", display_color=GOLD, lineweight_mm=0.25),
    _layer("A-2D::A-PLAN::A-WINDOW", parent="A-2D::A-PLAN", semantic_role="plan_window", display_color=TURQUOISE, lineweight_mm=0.18),
    _layer("A-2D::A-PLAN::A-HATCH", parent="A-2D::A-PLAN", semantic_role="plan_hatch", display_color=DARK_GREY, lineweight_mm=0.13),
    _layer("A-2D::A-PLAN::A-FURNITURE", parent="A-2D::A-PLAN", semantic_role="plan_furniture", display_color=LIME, lineweight_mm=0.18),
    _layer("A-2D::A-ELECTRICAL", parent="A-2D", plot=False),
    _layer("A-2D::A-ELECTRICAL::A-WIRE", parent="A-2D::A-ELECTRICAL", semantic_role="electrical_wire", display_color=RED, lineweight_mm=0.18),
    _layer("A-2D::A-SECELEV", parent="A-2D", plot=False),
    _layer("A-2D::A-SECELEV::A-LINE 00", parent="A-2D::A-SECELEV", semantic_role="construction", display_color=DARK_GREY, lineweight_mm=0.0, plot=False),
    _layer("A-2D::A-SECELEV::A-LINE 01", parent="A-2D::A-SECELEV", semantic_role="secelev_hairline", lineweight_mm=0.075),
    _layer("A-2D::A-SECELEV::A-LINE 02-Elev", parent="A-2D::A-SECELEV", semantic_role="secelev_distant", display_color=OLIVE_DRAB, lineweight_mm=0.13),
    _layer("A-2D::A-SECELEV::A-LINE 02-Elev-DASHED", parent="A-2D::A-SECELEV", semantic_role="secelev_hidden", display_color=OLIVE_DRAB, lineweight_mm=0.13, linetype="DASHED"),
    _layer("A-2D::A-SECELEV::A-LINE 03", parent="A-2D::A-SECELEV", semantic_role="secelev_minor", display_color=CADET_BLUE, lineweight_mm=0.18),
    _layer("A-2D::A-SECELEV::A-LINE 04", parent="A-2D::A-SECELEV", semantic_role="secelev_medium", lineweight_mm=0.25),
    _layer("A-2D::A-SECELEV::A-LINE 05", parent="A-2D::A-SECELEV", semantic_role="secelev_major", lineweight_mm=0.35),
    _layer("A-2D::A-SECELEV::A-LINE 06-Section", parent="A-2D::A-SECELEV", semantic_role="section_cut", display_color=BLUE, lineweight_mm=0.50),
    _layer("A-2D::A-SECELEV::A-LINE 07", parent="A-2D::A-SECELEV", semantic_role="section_heavy", lineweight_mm=0.70),
    _layer("A-2D::A-SECELEV::A-LINE 08", parent="A-2D::A-SECELEV", semantic_role="section_poche_edge", display_color=STEEL_BLUE, lineweight_mm=1.00),
    _layer("A-2D::A-DETAIL", parent="A-2D", plot=False),
    _layer("A-2D::A-DETAIL::A-DETAIL 00", parent="A-2D::A-DETAIL", semantic_role="construction", display_color=DARK_GREY, lineweight_mm=0.0, plot=False),
    _layer("A-2D::A-DETAIL::A-DETAIL 01", parent="A-2D::A-DETAIL", semantic_role="detail_hairline", lineweight_mm=0.075),
    _layer("A-2D::A-DETAIL::A-DETAIL 02", parent="A-2D::A-DETAIL", semantic_role="detail_distant", display_color=CHARTREUSE, lineweight_mm=0.13),
    _layer("A-2D::A-DETAIL::A-DETAIL 02-Elev-DASHED", parent="A-2D::A-DETAIL", semantic_role="detail_hidden", display_color=CHARTREUSE, lineweight_mm=0.13, linetype="DASHED"),
    _layer("A-2D::A-DETAIL::A-DETAIL 03", parent="A-2D::A-DETAIL", semantic_role="detail_minor", lineweight_mm=0.18),
    _layer("A-2D::A-DETAIL::A-DETAIL 04", parent="A-2D::A-DETAIL", semantic_role="detail_medium", display_color=SALMON, lineweight_mm=0.25),
    _layer("A-2D::A-DETAIL::A-DETAIL 05", parent="A-2D::A-DETAIL", semantic_role="detail_major", display_color=BLUE, lineweight_mm=0.35),
    _layer("A-2D::A-DETAIL::A-DETAIL 06", parent="A-2D::A-DETAIL", semantic_role="detail_cut", display_color=BLUE, lineweight_mm=0.50),
    _layer("A-2D::A-DETAIL::A-CENTER", parent="A-2D::A-DETAIL", semantic_role="centerline", display_color=TURQUOISE, lineweight_mm=0.13, linetype="CENTER"),
    _layer("A-2D::A-DETAIL::A-HATCH", parent="A-2D::A-DETAIL", semantic_role="detail_hatch", display_color=LIGHT_GREY, lineweight_mm=0.13),
    _layer("A-ANNOT", plot=False),
    _layer("A-ANNOT::A-DIM", parent="A-ANNOT", semantic_role="dimension", display_color=DARK_ORANGE, lineweight_mm=0.18),
    _layer("A-ANNOT::A-TEXT", parent="A-ANNOT", semantic_role="text", display_color=DARK_ORANGE, lineweight_mm=0.18),
    _layer("A-ANNOT::A-NOTES", parent="A-ANNOT", semantic_role="note", display_color=DARK_ORANGE, lineweight_mm=0.18),
    _layer("A-ANNOT::A-SYMBOL", parent="A-ANNOT", semantic_role="symbol", display_color=DARK_ORANGE, lineweight_mm=0.18),
    _layer("A-HELPERS", plot=False),
    _layer("A-HELPERS::A-CLIPPING PLANES", parent="A-HELPERS", semantic_role="helper", display_color=MAGENTA, lineweight_mm=0.0, plot=False),
]


URIU_LEGACY_LAYER_ALIASES = {
    "OUTLINE": "A-2D::A-DETAIL::A-DETAIL 06",
    "GEOMETRY": "A-2D::A-DETAIL::A-DETAIL 05",
    "DETAIL": "A-2D::A-DETAIL::A-DETAIL 03",
    "HIDDEN": "A-2D::A-DETAIL::A-DETAIL 02-Elev-DASHED",
    "CENTER": "A-2D::A-DETAIL::A-CENTER",
    "HATCH": "A-2D::A-DETAIL::A-HATCH",
    "DIMENSIONS": "A-ANNOT::A-DIM",
    "TEXT": "A-ANNOT::A-TEXT",
    "ANNOTATION": "A-ANNOT::A-NOTES",
}


URIU_PROMPT_LAYER_ROLES = {
    "heavy cut/outer edge": "A-2D::A-DETAIL::A-DETAIL 06",
    "major visible edge": "A-2D::A-DETAIL::A-DETAIL 05",
    "medium edge": "A-2D::A-DETAIL::A-DETAIL 04",
    "minor/detail edge": "A-2D::A-DETAIL::A-DETAIL 03",
    "distant edge": "A-2D::A-DETAIL::A-DETAIL 02",
    "hidden edge": "A-2D::A-DETAIL::A-DETAIL 02-Elev-DASHED",
    "hairline": "A-2D::A-DETAIL::A-DETAIL 01",
    "centerline": "A-2D::A-DETAIL::A-CENTER",
    "hatch": "A-2D::A-DETAIL::A-HATCH",
    "dimension": "A-ANNOT::A-DIM",
    "text": "A-ANNOT::A-TEXT",
    "note/leader": "A-ANNOT::A-NOTES",
}
