from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_name: str = "NaturalCAD Backend"
    app_env: str = os.getenv("APP_ENV", "development")
    api_shared_secret: str = os.getenv("API_SHARED_SECRET", "")
    rate_limit_per_hour: int = int(os.getenv("RATE_LIMIT_PER_HOUR", "20"))
    max_prompt_length: int = int(os.getenv("MAX_PROMPT_LENGTH", "1000"))
    database_url: str = os.getenv("DATABASE_URL", "")
    supabase_url: str = os.getenv("SUPABASE_URL", "")
    supabase_service_role_key: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    supabase_anon_key: str = os.getenv("SUPABASE_ANON_KEY", "")
    supabase_bucket: str = os.getenv("SUPABASE_BUCKET", "naturalcad-artifacts")
    storage_max_upload_bytes: int = int(os.getenv("STORAGE_MAX_UPLOAD_BYTES", "26214400"))


settings = Settings()
