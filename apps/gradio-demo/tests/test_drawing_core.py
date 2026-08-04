from __future__ import annotations

import sys
from pathlib import Path

import ezdxf
import pytest
from ezdxf.lldxf import const as ezdxf_const
from ezdxf.render import hatching as ezdxf_hatching

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

from drawing_core import (  # noqa: E402
    SCHEMA_VERSION,
    build_fallback_scene,
    export_dxf,
    render_svg,
    scene_from_payload,
    scene_quality_report,
    scene_to_dict,
)
from drafting_standards import NOAH_URIU_2D_PROFILE  # noqa: E402


def test_scene_contract_preserves_ids_and_normalizes_layers() -> None:
    scene = scene_from_payload(
        {
            "title": "Bracket",
            "units": "mm",
            "layers": [{"name": "geometry", "color": 999, "linetype": "invented"}],
            "circles": [{"id": "mount_hole", "center": [0, 0], "radius": 5, "layer": "geometry"}],
        }
    )

    payload = scene_to_dict(scene)
    assert payload["schema_version"] == SCHEMA_VERSION
    assert scene.circles[0].id == "mount_hole"
    assert scene.circles[0].layer == "GEOMETRY"
    assert scene.layers[0].color == 255
    assert scene.layers[0].linetype == "CONTINUOUS"


def test_circle_only_scene_is_valid() -> None:
    scene = scene_from_payload({"title": "Washer", "circles": [{"center": [0, 0], "radius": 12}]})
    assert len(scene.circles) == 1
    assert not scene.polylines


def test_empty_scene_is_rejected() -> None:
    with pytest.raises(ValueError, match="no supported geometry"):
        scene_from_payload({"title": "Empty", "texts": [{"text": "nothing", "insert": [0, 0]}]})


def test_duplicate_entity_ids_are_made_unique() -> None:
    scene = scene_from_payload(
        {
            "circles": [
                {"id": "hole", "center": [0, 0], "radius": 3},
                {"id": "hole", "center": [10, 0], "radius": 3},
            ]
        }
    )
    assert [entity.id for entity in scene.circles] == ["hole", "hole_2"]


def test_demo_fallback_uses_true_slots() -> None:
    scene = build_fallback_scene("Wall bracket 180x90 mm with two slots", "mm")
    assert len(scene.slots) == 2
    assert not scene.circles
    assert {slot.id for slot in scene.slots} == {"slot_001", "slot_002"}


def test_svg_and_dxf_share_slot_and_arc_geometry(tmp_path: Path) -> None:
    scene = scene_from_payload(
        {
            "title": "Slot and arc fixture",
            "units": "mm",
            "polylines": [
                {"id": "outline", "points": [[-50, -30], [50, -30], [50, 30], [-50, 30]], "closed": True}
            ],
            "slots": [{"id": "slot_a", "center": [0, 0], "length": 30, "width": 10, "angle": 15}],
            "arcs": [{"id": "arc_a", "center": [0, 0], "radius": 20, "start_angle": 0, "end_angle": 135}],
            "dimensions": [
                {"id": "overall", "start": [-50, -30], "end": [50, -30], "offset": 12, "text": "100 mm"}
            ],
        }
    )
    svg = render_svg(scene)
    assert 'data-entity-id="slot_a"' in svg
    assert 'data-entity-id="arc_a"' in svg
    assert 'data-entity-id="overall"' in svg

    output = tmp_path / "fixture.dxf"
    export_dxf(scene, output)
    document = ezdxf.readfile(output)
    modelspace = document.modelspace()
    assert len(modelspace.query("ARC")) == 3  # one requested arc + two slot ends
    assert len(modelspace.query("LINE")) == 2  # slot tangents
    assert len(modelspace.query("LWPOLYLINE")) == 1
    assert len(modelspace.query("DIMENSION")) == 1
    assert modelspace.query("DIMENSION").first.dxf.text == "100 mm"


def test_hatch_defaults_and_controls_are_normalized() -> None:
    scene = scene_from_payload(
        {
            "polylines": [{"points": [[0, 0], [20, 0], [20, 20], [0, 20]], "closed": True}],
            "hatches": [
                {"id": "legacy", "boundary": [[0, 0], [8, 0], [8, 8], [0, 8]]},
                {
                    "id": "controlled",
                    "boundary": [[0, 0], [20, 0], [20, 20], [0, 20]],
                    "holes": [[[5, 5], [15, 5], [15, 15], [5, 15]]],
                    "pattern": "ANSI31",
                    "pattern_scale": 500,
                    "pattern_angle": -45,
                    "opacity": 2,
                },
            ],
        }
    )

    legacy, controlled = scene.hatches
    assert legacy.holes == []
    assert legacy.pattern_scale == 1.0
    assert legacy.pattern_angle == 0.0
    assert legacy.opacity == 0.18
    assert len(controlled.holes) == 1
    assert controlled.pattern_scale == 100.0
    assert controlled.pattern_angle == 315.0
    assert controlled.opacity == 1.0


def test_svg_and_dxf_preserve_patterned_hatch_hole_and_bylayer_style(tmp_path: Path) -> None:
    scene = scene_from_payload(
        {
            "layers": [
                {"name": "outline", "color": 7, "linetype": "CONTINUOUS", "lineweight": 50},
                {"name": "detail", "color": 4, "linetype": "DASHED", "lineweight": 18},
                {"name": "hatch", "color": 8, "linetype": "CONTINUOUS", "lineweight": 13},
            ],
            "polylines": [
                {"id": "outline", "points": [[0, 0], [30, 0], [30, 20], [0, 20]], "closed": True, "layer": "OUTLINE"},
                {"id": "detail", "points": [[0, 10], [30, 10]], "layer": "DETAIL"},
            ],
            "hatches": [
                {
                    "id": "section_cut",
                    "boundary": [[0, 0], [30, 0], [30, 20], [0, 20]],
                    "holes": [[[10, 5], [20, 5], [20, 15], [10, 15]]],
                    "pattern": "ANSI31",
                    "pattern_scale": 2.5,
                    "pattern_angle": 37,
                    "opacity": 0.6,
                }
            ],
        }
    )

    svg = render_svg(scene)
    assert 'data-pattern="ANSI31"' in svg
    assert 'data-display-mode="monochrome"' in svg
    assert 'data-preview-simplified="true"' not in svg
    assert 'stroke-opacity="0.600"' in svg
    assert 'stroke="#ffffff"' in svg
    assert 'stroke-dasharray="9 6"' in svg

    output = tmp_path / "patterned_hatch.dxf"
    export_dxf(scene, output)
    document = ezdxf.readfile(output)
    hatch = document.modelspace().query("HATCH").first
    assert hatch.dxf.pattern_name == "ANSI31"
    assert hatch.dxf.pattern_scale == 2.5
    assert hatch.dxf.pattern_angle == 37
    assert not hatch.dxf.hasattr("transparency")  # opacity is preview-only; legacy DXF stays opaque
    assert len(hatch.paths) == 2
    assert hatch.dxf.hatch_style == ezdxf_const.HATCH_STYLE_NESTED
    segments = list(ezdxf_hatching.hatch_entity(hatch, jiggle_origin=False))
    assert segments
    assert not any(
        10 < (start.x + end.x) / 2 < 20 and 5 < (start.y + end.y) / 2 < 15
        for start, end in segments
    )
    assert hatch.dxf.color == 256
    assert document.layers.get("OUTLINE").dxf.lineweight == 50
    assert not document.audit().has_errors


def test_dense_scene_survives_without_silent_truncation(tmp_path: Path) -> None:
    payload = {
        "polylines": [
            {"id": f"detail_{index}", "points": [[0, index], [100, index]], "layer": "DETAIL"}
            for index in range(96)
        ],
        "hatches": [
            {
                "id": f"shadow_{index}",
                "boundary": [[index, 0], [index + 0.8, 0], [index + 0.8, 4], [index, 4]],
                "pattern": "ANSI31",
                "pattern_angle": 45 if index % 2 else 135,
            }
            for index in range(48)
        ],
    }
    scene = scene_from_payload(payload)
    assert len(scene.polylines) == 96
    assert len(scene.hatches) == 48

    output = tmp_path / "dense_scene.dxf"
    export_dxf(scene, output)
    document = ezdxf.readfile(output)
    assert len(document.modelspace().query("LWPOLYLINE")) == 96
    assert len(document.modelspace().query("HATCH")) == 48
    assert not document.audit().has_errors


def test_over_budget_scene_is_rejected_instead_of_truncated() -> None:
    with pytest.raises(ValueError, match="polylines exceeds the 128-entity limit"):
        scene_from_payload(
            {
                "polylines": [
                    {"points": [[0, index], [1, index]]}
                    for index in range(129)
                ]
            }
        )


def test_every_entity_is_assigned_to_a_defined_cad_layer() -> None:
    scene = scene_from_payload(
        {
            "polylines": [{"points": [[0, 0], [20, 0]], "layer": "custom_detail"}],
            "circles": [{"center": [5, 5], "radius": 2}],
            "arcs": [{"center": [8, 8], "radius": 2, "start_angle": 0, "end_angle": 90}],
            "slots": [{"center": [10, 10], "length": 8, "width": 3}],
            "hatches": [{"boundary": [[0, 0], [4, 0], [4, 4], [0, 4]]}],
            "texts": [{"text": "note", "insert": [0, 6]}],
            "dimensions": [{"start": [0, 0], "end": [20, 0], "offset": 4}],
            "leaders": [{"points": [[0, 0], [3, 3]], "text": "callout"}],
        }
    )
    layer_names = {layer.name for layer in scene.layers}
    entities = (
        *scene.polylines,
        *scene.circles,
        *scene.arcs,
        *scene.slots,
        *scene.hatches,
        *scene.texts,
        *scene.dimensions,
        *scene.leaders,
    )
    assert entities
    assert all(entity.layer in layer_names for entity in entities)


def test_hatch_rings_reject_malformed_points_instead_of_changing_topology() -> None:
    with pytest.raises(ValueError, match="hatch rings cannot contain malformed points"):
        scene_from_payload(
            {
                "polylines": [{"points": [[0, 0], [10, 0]]}],
                "hatches": [
                    {"boundary": [[0, 0], [10, 0], [10, "bad"], [0, 10]]}
                ],
            }
        )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("schema_version", "9.0", "Unsupported DrawingScene schema_version"),
        ("coordinate_system", "SCREEN_Y_DOWN", "Unsupported coordinate_system"),
    ],
)
def test_explicit_unsupported_contract_values_are_rejected(field: str, value: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        scene_from_payload(
            {
                field: value,
                "polylines": [{"points": [[0, 0], [10, 0]]}],
            }
        )


def test_v1_scene_is_accepted_as_a_migration_input() -> None:
    scene = scene_from_payload(
        {
            "schema_version": "1.0",
            "polylines": [{"points": [[0, 0], [10, 0]]}],
        }
    )
    assert scene.schema_version == SCHEMA_VERSION


def test_uriu_profile_resolves_hierarchy_display_and_plot_styles() -> None:
    scene = scene_from_payload(
        {
            "standard_profile": NOAH_URIU_2D_PROFILE,
            "layers": [{"name": "A-2D::A-DETAIL::A-DETAIL 01"}],
            "polylines": [
                {
                    "id": "hairline",
                    "points": [[0, 0], [10, 0]],
                    "layer": "A-2D::A-DETAIL::A-DETAIL 01",
                }
            ],
        }
    )
    names = [layer.name for layer in scene.layers]
    assert names == ["A-2D", "A-2D::A-DETAIL", "A-2D::A-DETAIL::A-DETAIL 01"]
    hairline = scene.layers[-1]
    assert hairline.lineweight_mm == 0.075
    assert hairline.lineweight == 9
    assert hairline.display_color == (255, 255, 255)
    assert hairline.plot_color == (0, 0, 0)


def test_uriu_layer_paths_resolve_case_insensitively_to_canonical_spelling() -> None:
    scene = scene_from_payload(
        {
            "standard_profile": NOAH_URIU_2D_PROFILE,
            "polylines": [
                {
                    "points": [[0, 0], [10, 0]],
                    "layer": "a-2d::a-detail::a-detail 02-elev-dashed",
                }
            ],
        }
    )
    assert scene.polylines[0].layer == "A-2D::A-DETAIL::A-DETAIL 02-Elev-DASHED"


def test_uriu_dxf_flattens_layer_paths_and_preserves_metadata(tmp_path: Path) -> None:
    scene = scene_from_payload(
        {
            "standard_profile": NOAH_URIU_2D_PROFILE,
            "polylines": [
                {
                    "id": "cut",
                    "points": [[0, 0], [20, 0]],
                    "layer": "A-2D::A-DETAIL::A-DETAIL 06",
                }
            ],
        }
    )
    output = tmp_path / "uriu.dxf"
    export_dxf(scene, output)
    document = ezdxf.readfile(output)
    layer = document.layers.get("A-2D$A-DETAIL$A-DETAIL 06")
    assert layer.rgb == (0, 0, 255)
    assert layer.dxf.lineweight == 50
    assert layer.get_xdata("NATURALCAD")[1] == (1000, "A-2D::A-DETAIL::A-DETAIL 06")
    assert document.modelspace().query("LWPOLYLINE").first.dxf.layer == layer.dxf.name
    assert document.header["$MEASUREMENT"] == 1
    assert not document.audit().has_errors


def test_monochrome_working_color_and_plot_svg_modes() -> None:
    scene = scene_from_payload(
        {
            "standard_profile": NOAH_URIU_2D_PROFILE,
            "polylines": [
                {"id": "blue_cut", "points": [[0, 0], [10, 0]], "layer": "A-2D::A-DETAIL::A-DETAIL 06"},
                {"id": "helper", "points": [[0, 1], [10, 1]], "layer": "A-2D::A-DETAIL::A-DETAIL 00"},
            ],
        }
    )
    monochrome = render_svg(scene)
    working_color = render_svg(scene, monochrome=False)
    plot = render_svg(scene, plot_mode=True)
    assert 'data-display-mode="monochrome"' in monochrome
    assert 'data-entity-id="blue_cut"' in monochrome and 'stroke="#ffffff"' in monochrome
    assert 'fill="url(#naturalcad-dot-grid)"' in monochrome
    assert 'data-display-mode="working-color"' in working_color
    assert 'data-entity-id="blue_cut"' in working_color and 'stroke="#0000ff"' in working_color
    assert 'data-entity-id="helper"' in working_color
    assert 'data-entity-id="blue_cut"' in plot and 'stroke="#000000"' in plot
    assert 'data-entity-id="helper"' not in plot


def test_creative_quality_gate_reports_shallow_and_deep_scenes() -> None:
    shallow = scene_from_payload({"polylines": [{"points": [[0, 0], [10, 0]]}]})
    assert scene_quality_report(shallow, intent_mode="CREATIVE_CONCEPT")["status"] == "needs_refinement"

    deep = scene_from_payload(
        {
            "polylines": [
                {"points": [[0, index], [10, index], [20, index + 1]]}
                for index in range(32)
            ],
            "hatches": [
                {"boundary": [[0, 0], [5, 0], [5, 5], [0, 5]], "layer": "HATCH"},
                {"boundary": [[6, 0], [11, 0], [11, 5], [6, 5]], "layer": "DETAIL"},
            ],
        }
    )
    report = scene_quality_report(deep, intent_mode="CREATIVE_CONCEPT")
    assert report["status"] == "pass"
