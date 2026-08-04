from __future__ import annotations

import sys
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

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
