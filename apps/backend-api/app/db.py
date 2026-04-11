from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .config import settings

try:
    import psycopg
except Exception:  # noqa: BLE001
    psycopg = None


@dataclass
class DatabaseState:
    enabled: bool
    reason: str | None = None


def get_database_state() -> DatabaseState:
    if not settings.database_url:
        return DatabaseState(enabled=False, reason="DATABASE_URL not configured")
    if psycopg is None:
        return DatabaseState(enabled=False, reason="psycopg not installed")
    return DatabaseState(enabled=True)


def connect():
    state = get_database_state()
    if not state.enabled:
        raise RuntimeError(state.reason or "Database unavailable")
    assert psycopg is not None
    return psycopg.connect(settings.database_url)


def serialize_json(value: Any) -> str:
    return json.dumps(value)
