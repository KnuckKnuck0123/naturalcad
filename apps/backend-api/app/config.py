from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = "NaturalCAD Domain API"
    app_version: str = "0.1.0"

    # Optional shared gateway secret for frontend -> API
    api_shared_secret: str = os.getenv("API_SHARED_SECRET", "")

    # Optional Modal worker endpoint for real CAD generation
    cad_worker_url: str = os.getenv("NATURALCAD_CAD_WORKER_URL", "").strip()
    cad_worker_api_key: str = os.getenv("NATURALCAD_CAD_WORKER_API_KEY", "").strip()

    # Guest rate limits (simple in-memory MVP guardrails)
    rate_window_seconds: int = int(os.getenv("NATURALCAD_RATE_WINDOW_SECONDS", "3600"))
    guest_runs_per_window: int = int(os.getenv("NATURALCAD_GUEST_RUNS_PER_WINDOW", "5"))
    signed_runs_per_window: int = int(os.getenv("NATURALCAD_SIGNED_RUNS_PER_WINDOW", "30"))

    mode_fast_model: str = os.getenv("NATURALCAD_MODE_FAST", "openai/gpt-4o-mini")
    mode_balanced_model: str = os.getenv("NATURALCAD_MODE_BALANCED", "google/gemini-2.5-pro")
    mode_quality_model: str = os.getenv("NATURALCAD_MODE_QUALITY", "anthropic/claude-sonnet-4")


settings = Settings()
