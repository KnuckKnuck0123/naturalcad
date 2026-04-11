from __future__ import annotations

from typing import Any

from .db import connect, get_database_state, serialize_json
from .models import JobRecord
from .store import _JOBS


def save_job(job: JobRecord) -> None:
    db_state = get_database_state()
    if not db_state.enabled:
        _JOBS[job.id] = job.model_dump()
        return

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into jobs (
                    id, status, prompt, mode, output_type, client_session_id,
                    prompt_hash, spec_json, notes_json, error_text
                )
                values (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
                on conflict (id) do update set
                    status = excluded.status,
                    prompt = excluded.prompt,
                    mode = excluded.mode,
                    output_type = excluded.output_type,
                    client_session_id = excluded.client_session_id,
                    prompt_hash = excluded.prompt_hash,
                    spec_json = excluded.spec_json,
                    notes_json = excluded.notes_json,
                    error_text = excluded.error_text,
                    updated_at = now()
                """,
                (
                    job.id,
                    job.status,
                    job.prompt,
                    job.mode,
                    job.output_type,
                    job.session_id,
                    job.prompt_hash,
                    serialize_json(job.spec.model_dump() if job.spec else None),
                    serialize_json(job.notes),
                    job.error,
                ),
            )
        conn.commit()


def get_job(job_id: str) -> dict[str, Any] | None:
    db_state = get_database_state()
    if not db_state.enabled:
        return _JOBS.get(job_id)

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, status, prompt, mode, output_type, client_session_id,
                       prompt_hash, spec_json, notes_json, error_text
                from jobs
                where id = %s
                """,
                (job_id,),
            )
            row = cur.fetchone()
            if not row:
                return None

    id_, status, prompt, mode, output_type, client_session_id, prompt_hash, spec_json, notes_json, error_text = row
    return {
        "id": str(id_),
        "status": status,
        "prompt": prompt,
        "mode": mode,
        "output_type": output_type,
        "session_id": client_session_id,
        "prompt_hash": prompt_hash,
        "spec": spec_json,
        "notes": notes_json or [],
        "error": error_text,
    }
