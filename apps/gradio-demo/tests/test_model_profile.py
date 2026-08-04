from __future__ import annotations

import json
import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

import main as main_app  # noqa: E402
from main import MODEL_SYSTEM_PROMPT, _generation_profile  # noqa: E402


def test_conceptual_staircase_gets_detail_headroom() -> None:
    profile = _generation_profile("mc escher stair case", None, None)
    assert profile == {"mode": "CREATIVE_CONCEPT", "temperature": 0.35, "max_tokens": 8_000}


def test_simple_technical_plate_keeps_lower_cost_budget() -> None:
    profile = _generation_profile("steel plate 200x100 with four holes", None, None)
    assert profile == {"mode": "TECHNICAL_DRAFT", "temperature": 0.15, "max_tokens": 4_000}


def test_explicit_technical_detail_gets_detail_headroom() -> None:
    profile = _generation_profile("steel plate section detail with material hatch", None, None)
    assert profile["mode"] == "TECHNICAL_DRAFT"
    assert profile["max_tokens"] == 6_500


def test_dimensioned_stair_section_stays_technical() -> None:
    profile = _generation_profile("staircase section, 12 risers at 175 mm", None, None)
    assert profile["mode"] == "TECHNICAL_DRAFT"


def test_model_prompt_requires_uriu_layers_and_depth_floor() -> None:
    assert '"standard_profile": "NOAH_URIU_2D_V1"' in MODEL_SYSTEM_PROMPT
    assert "A-2D::A-DETAIL::A-DETAIL 06" in MODEL_SYSTEM_PROMPT
    assert "fewer than 32 polylines" in MODEL_SYSTEM_PROMPT


def _response(scene: dict, *, prompt_tokens: int, completion_tokens: int) -> dict:
    return {
        "choices": [{"message": {"content": json.dumps(scene)}}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def test_shallow_creative_scene_gets_one_cost_bounded_deepening_pass(monkeypatch) -> None:
    shallow = {
        "title": "Shallow stair",
        "polylines": [{"id": "edge", "points": [[0, 0], [10, 0]]}],
    }
    deep = {
        "title": "Deep stair",
        "polylines": [
            {
                "id": f"line_{index}",
                "points": [[0, index], [10, index], [20, index + 1]],
                "layer": "GEOMETRY",
            }
            for index in range(32)
        ],
        "hatches": [
            {"id": "shadow_a", "boundary": [[0, 0], [5, 0], [5, 5], [0, 5]], "layer": "HATCH"},
            {"id": "shadow_b", "boundary": [[6, 0], [11, 0], [11, 5], [6, 5]], "layer": "DETAIL"},
        ],
    }
    queued = [
        _response(shallow, prompt_tokens=10, completion_tokens=20),
        _response(deep, prompt_tokens=30, completion_tokens=40),
    ]
    payloads: list[dict] = []

    def fake_post(payload: dict) -> dict:
        payloads.append(payload)
        return queued.pop(0)

    monkeypatch.setattr(main_app, "OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(main_app, "MAX_GENERATION_PASSES", 2)
    monkeypatch.setattr(main_app, "_post_openrouter", fake_post)

    scene, meta = main_app.request_model_scene("mc escher stair case", "", "mm", None)

    assert scene is not None and len(scene.polylines) == 32
    assert len(payloads) == 2
    assert "DEEPEN THE PREVIOUS VALIDATED DRAWING SCENE" in payloads[1]["messages"][1]["content"]
    assert meta["passes"] == 2
    assert meta["pass_summaries"][0]["quality_status"] == "needs_refinement"
    assert meta["pass_summaries"][1]["quality_status"] == "pass"
    assert meta["usage"] == {"prompt_tokens": 40, "completion_tokens": 60, "total_tokens": 100}


def test_simple_technical_scene_never_pays_for_depth_retry(monkeypatch) -> None:
    payloads: list[dict] = []

    def fake_post(payload: dict) -> dict:
        payloads.append(payload)
        return _response(
            {"title": "Plate", "polylines": [{"points": [[0, 0], [20, 0]]}]},
            prompt_tokens=8,
            completion_tokens=12,
        )

    monkeypatch.setattr(main_app, "OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(main_app, "MAX_GENERATION_PASSES", 2)
    monkeypatch.setattr(main_app, "_post_openrouter", fake_post)

    scene, meta = main_app.request_model_scene("steel plate 200x100", "", "mm", None)

    assert scene is not None
    assert len(payloads) == 1
    assert meta["passes"] == 1


def test_failed_depth_repair_preserves_first_valid_scene(monkeypatch) -> None:
    calls = 0

    def fake_post(payload: dict) -> dict:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _response(
                {"title": "Valid first pass", "polylines": [{"id": "edge", "points": [[0, 0], [10, 0]]}]},
                prompt_tokens=10,
                completion_tokens=20,
            )
        raise RuntimeError("repair unavailable")

    monkeypatch.setattr(main_app, "OPENROUTER_API_KEY", "test-key")
    monkeypatch.setattr(main_app, "MAX_GENERATION_PASSES", 2)
    monkeypatch.setattr(main_app, "_post_openrouter", fake_post)

    scene, meta = main_app.request_model_scene("impossible stair", "", "mm", None)

    assert scene is not None and scene.title == "Valid first pass"
    assert meta["source"] == "model"
    assert meta["passes"] == 1
    assert meta["deepen_error"] == "repair unavailable"
