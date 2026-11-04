from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = "NaturalCAD Domain API"
    app_version: str = "0.1.0"
    environment: str = os.getenv("NATURALCAD_ENV", "development").strip().lower()

    # Optional shared gateway secret for frontend -> API
    api_shared_secret: str = os.getenv("API_SHARED_SECRET", "")

    # Optional Modal worker endpoint for real CAD generation
    cad_worker_url: str = os.getenv("NATURALCAD_CAD_WORKER_URL", "").strip()
    cad_worker_api_key: str = os.getenv("NATURALCAD_CAD_WORKER_API_KEY", "").strip()

    # Supabase persistence (optional, falls back to in-memory when unset)
    supabase_url: str = os.getenv("SUPABASE_URL", "").strip()
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    source_image_bucket: str = os.getenv("NATURALCAD_SOURCE_IMAGE_BUCKET", "naturalcad-source-images").strip()
    allowed_origins: tuple[str, ...] = tuple(
        origin.strip() for origin in os.getenv("NATURALCAD_ALLOWED_ORIGINS", "http://localhost:3000").split(",") if origin.strip()
    )

    # Guest rate limits
    rate_window_seconds: int = int(os.getenv("NATURALCAD_RATE_WINDOW_SECONDS", "3600"))
    guest_runs_per_window: int = int(os.getenv("NATURALCAD_GUEST_RUNS_PER_WINDOW", "5"))
    signed_runs_per_window: int = int(os.getenv("NATURALCAD_SIGNED_RUNS_PER_WINDOW", "30"))
    guest_project_generation_cap: int = int(os.getenv("NATURALCAD_GUEST_PROJECT_GENERATION_CAP", "0"))
    guest_project_token_cap: int = int(os.getenv("NATURALCAD_GUEST_PROJECT_TOKEN_CAP", "0"))

    # Per-IP abuse limits (0 = disabled). Guest sessions are free to mint, so
    # public deployments must also cap by client IP.
    ip_sessions_per_window: int = int(os.getenv("NATURALCAD_IP_SESSIONS_PER_WINDOW", "0"))
    ip_runs_per_window: int = int(os.getenv("NATURALCAD_IP_RUNS_PER_WINDOW", "0"))

    # Kill switch: set "true" to immediately block new generations with a friendly 503.
    generations_disabled: bool = os.getenv("NATURALCAD_GENERATIONS_DISABLED", "false").strip().lower() in {"1", "true", "yes", "on"}

    mode_fast_model: str = os.getenv("NATURALCAD_MODE_FAST", "openai/gpt-4o-mini")
    mode_balanced_model: str = os.getenv("NATURALCAD_MODE_BALANCED", "google/gemini-2.5-pro")
    mode_quality_model: str = os.getenv("NATURALCAD_MODE_QUALITY", "anthropic/claude-sonnet-4")
    vision_model: str = os.getenv("NATURALCAD_VISION_MODEL", "google/gemini-2.5-flash")
    cad_model: str = os.getenv("NATURALCAD_CAD_MODEL", "anthropic/claude-sonnet-4")
    legacy_cad_model: str = os.getenv("NATURALCAD_LEGACY_CAD_MODEL", "")
    vision_summary_max_tokens: int = int(os.getenv("NATURALCAD_VISION_SUMMARY_MAX_TOKENS", "220"))
    max_guest_attachments: int = int(os.getenv("NATURALCAD_MAX_GUEST_ATTACHMENTS", "3"))


settings = Settings()
