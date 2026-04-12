from __future__ import annotations

from typing import Any

from .db import connect, get_database_state, serialize_json
from .models import JobRecord
from .store import _ARTIFACTS, _JOBS


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


def create_artifact(job_id: str, kind: str, storage_key: str, size_bytes: int | None) -> dict[str, Any]:
    db_state = get_database_state()
    if not db_state.enabled:
        row = {
            "id": f"{job_id}:{kind}:{len(_ARTIFACTS[job_id]) + 1}",
            "job_id": job_id,
            "kind": kind,
            "storage_key": storage_key,
            "size_bytes": size_bytes,
            "created_at": None,
        }
        _ARTIFACTS[job_id].append(row)
        return row

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                insert into artifacts (job_id, kind, storage_key, size_bytes)
                values (%s, %s, %s, %s)
                returning id, job_id, kind, storage_key, size_bytes, created_at
                """,
                (job_id, kind, storage_key, size_bytes),
            )
            row = cur.fetchone()
        conn.commit()

    artifact_id, r_job_id, r_kind, r_storage_key, r_size_bytes, r_created_at = row
    return {
        "id": str(artifact_id),
        "job_id": str(r_job_id),
        "kind": r_kind,
        "storage_key": r_storage_key,
        "size_bytes": r_size_bytes,
        "created_at": r_created_at.isoformat() if r_created_at else None,
    }


def list_artifacts(job_id: str) -> list[dict[str, Any]]:
    db_state = get_database_state()
    if not db_state.enabled:
        return list(_ARTIFACTS.get(job_id, []))

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                select id, job_id, kind, storage_key, size_bytes, created_at
                from artifacts
                where job_id = %s
                order by created_at asc
                """,
                (job_id,),
            )
            rows = cur.fetchall() or []

    out: list[dict[str, Any]] = []
    for artifact_id, r_job_id, r_kind, r_storage_key, r_size_bytes, r_created_at in rows:
        out.append(
            {
                "id": str(artifact_id),
                "job_id": str(r_job_id),
                "kind": r_kind,
                "storage_key": r_storage_key,
                "size_bytes": r_size_bytes,
                "created_at": r_created_at.isoformat() if r_created_at else None,
            }
        )
    return out
