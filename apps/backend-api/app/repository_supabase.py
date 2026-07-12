from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

import httpx

from .models import (
    AttachmentResponse, GenerationRunResponse, MessageResponse, ParameterControl, PartSpec,
    ProjectResponse, SessionResponse, VersionResponse, utc_now,
)


class SupabaseRepo:
    """PostgREST repository. All authorization is checked before these service-role calls."""

    def __init__(self, *, url: str, service_role_key: str) -> None:
        self.url = url.rstrip("/")
        self.key = service_role_key
        self.base = f"{self.url}/rest/v1"

    def _headers(self, prefer: str | None = None) -> dict[str, str]:
        headers = {"apikey": self.key, "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"}
        if prefer:
            headers["Prefer"] = prefer
        return headers

    def _request(self, method: str, table: str, *, params: dict | None = None, json: Any = None, prefer: str | None = None) -> Any:
        with httpx.Client(timeout=20.0) as client:
            response = client.request(method, f"{self.base}/{table}", params=params, json=json, headers=self._headers(prefer))
        response.raise_for_status()
        return response.json() if response.content else None

    @staticmethod
    def _jsonable(value: Any) -> Any:
        if isinstance(value, PartSpec):
            return value.model_dump()
        if isinstance(value, ParameterControl):
            return value.model_dump()
        if isinstance(value, list):
            return [SupabaseRepo._jsonable(item) for item in value]
        if isinstance(value, dict):
            return {key: SupabaseRepo._jsonable(item) for key, item in value.items()}
        return value

    @staticmethod
    def _dt(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def create_guest_session(self, runs_per_window: int) -> SessionResponse:
        now, session_id = utc_now(), f"guest_{uuid.uuid4().hex}"
        expires_at = now + timedelta(days=7)
        self._request("POST", "nc_sessions", json={"id": session_id, "actor_type": "guest", "created_at": now.isoformat(), "expires_at": expires_at.isoformat()}, prefer="return=minimal")
        return SessionResponse(session_id=session_id, actor_type="guest", created_at=now, expires_at=expires_at, quotas={"runs_per_window": runs_per_window})

    def create_user_session(self, user_id: str, runs_per_window: int) -> SessionResponse:
        rows = self._request("GET", "nc_sessions", params={"select": "id,created_at,expires_at", "actor_type": "eq.user", "user_id": f"eq.{user_id}", "expires_at": f"gt.{utc_now().isoformat()}", "limit": "1"})
        if rows:
            return SessionResponse(session_id=rows[0]["id"], actor_type="user", created_at=self._dt(rows[0]["created_at"]), expires_at=self._dt(rows[0]["expires_at"]), quotas={"runs_per_window": runs_per_window})
        now, session_id = utc_now(), f"user_{uuid.uuid4().hex}"
        expires_at = now + timedelta(days=30)
        self._request("POST", "nc_sessions", json={"id": session_id, "actor_type": "user", "user_id": user_id, "created_at": now.isoformat(), "expires_at": expires_at.isoformat()}, prefer="return=minimal")
        return SessionResponse(session_id=session_id, actor_type="user", created_at=now, expires_at=expires_at, quotas={"runs_per_window": runs_per_window})

    def get_session(self, session_id: str) -> SessionResponse | None:
        rows = self._request("GET", "nc_sessions", params={"select": "id,actor_type,created_at,expires_at", "id": f"eq.{session_id}", "expires_at": f"gt.{utc_now().isoformat()}", "limit": "1"})
        if not rows:
            return None
        row = rows[0]
        return SessionResponse(session_id=row["id"], actor_type=row["actor_type"], created_at=self._dt(row["created_at"]), expires_at=self._dt(row["expires_at"]), quotas={})

    def check_and_consume_quota(self, session_id: str, *, max_runs: int, window_seconds: int) -> tuple[bool, int]:
        rows = self._request("POST", "rpc/nc_reserve_generation_quota", json={"p_session_id": session_id, "p_max_runs": max_runs, "p_window_seconds": window_seconds})
        result = rows[0] if isinstance(rows, list) else rows
        return bool(result["allowed"]), int(result["remaining"])

    def create_project(self, session_id: str, title: str, mode: str, output_type: str) -> ProjectResponse:
        now, project_id = utc_now(), f"proj_{uuid.uuid4().hex[:10]}"
        payload = {"id": project_id, "owner_session_id": session_id, "title": title, "mode": mode, "output_type": output_type, "created_at": now.isoformat(), "updated_at": now.isoformat()}
        self._request("POST", "nc_projects", json=payload, prefer="return=minimal")
        return ProjectResponse(**payload)

    def get_project(self, project_id: str) -> ProjectResponse | None:
        rows = self._request("GET", "nc_projects", params={"select": "*", "id": f"eq.{project_id}", "limit": "1"})
        return ProjectResponse(**rows[0]) if rows else None

    def create_message(self, *, project_id: str, role: str, content: str, attachment_ids: list[str] | None = None, run_id: str | None = None, version_id: str | None = None) -> MessageResponse:
        payload = {"id": f"msg_{uuid.uuid4().hex[:12]}", "project_id": project_id, "role": role, "content": content, "attachment_ids": attachment_ids or [], "run_id": run_id, "version_id": version_id, "created_at": utc_now().isoformat()}
        self._request("POST", "nc_messages", json=payload, prefer="return=minimal")
        return MessageResponse(**payload)

    def list_messages(self, project_id: str) -> list[MessageResponse]:
        rows = self._request("GET", "nc_messages", params={"select": "*", "project_id": f"eq.{project_id}", "order": "created_at.asc"})
        return [MessageResponse(**row) for row in rows]

    def create_run(self, *, project_id: str, session_id: str, parent_version_id: str | None, idempotency_key: str, message: str, attachment_ids: list[str], profile: str) -> tuple[GenerationRunResponse, bool]:
        existing = self._request("GET", "nc_generation_runs", params={"select": "*", "project_id": f"eq.{project_id}", "idempotency_key": f"eq.{idempotency_key}", "limit": "1"})
        if existing:
            return GenerationRunResponse(**existing[0]), False
        now = utc_now().isoformat()
        payload = {"id": f"run_{uuid.uuid4().hex[:12]}", "project_id": project_id, "session_id": session_id, "parent_version_id": parent_version_id, "idempotency_key": idempotency_key, "message": message, "attachment_ids": attachment_ids, "profile": profile, "status": "submitted", "created_at": now, "updated_at": now}
        try:
            self._request("POST", "nc_generation_runs", json=payload, prefer="return=minimal")
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 409:
                raise
            raced = self._request("GET", "nc_generation_runs", params={"select": "*", "project_id": f"eq.{project_id}", "idempotency_key": f"eq.{idempotency_key}", "limit": "1"})
            if not raced:
                raise
            return GenerationRunResponse(**raced[0]), False
        return GenerationRunResponse(**payload), True

    def get_run(self, project_id: str, run_id: str) -> GenerationRunResponse | None:
        rows = self._request("GET", "nc_generation_runs", params={"select": "*", "project_id": f"eq.{project_id}", "id": f"eq.{run_id}", "limit": "1"})
        return GenerationRunResponse(**rows[0]) if rows else None

    def claim_run(self, project_id: str, run_id: str, *, stale_seconds: int) -> str | None:
        """Atomically claim exclusive processing of a run via a conditional UPDATE.
        Returns a claim token, or None if another worker holds a fresh claim."""
        token = uuid.uuid4().hex
        cutoff = (utc_now() - timedelta(seconds=stale_seconds)).isoformat()
        rows = self._request(
            "PATCH", "nc_generation_runs",
            params={
                "id": f"eq.{run_id}", "project_id": f"eq.{project_id}",
                "or": f'(claimed_at.is.null,claimed_at.lt."{cutoff}")',
            },
            json={"claimed_at": utc_now().isoformat(), "claim_token": token},
            prefer="return=representation",
        )
        return token if rows else None

    def refresh_run_claim(self, project_id: str, run_id: str, token: str) -> bool:
        """Heartbeat an existing claim. Returns False if the claim was stolen."""
        rows = self._request(
            "PATCH", "nc_generation_runs",
            params={"id": f"eq.{run_id}", "project_id": f"eq.{project_id}", "claim_token": f"eq.{token}"},
            json={"claimed_at": utc_now().isoformat()},
            prefer="return=representation",
        )
        return bool(rows)

    def list_runs(self, project_id: str) -> list[GenerationRunResponse]:
        rows = self._request("GET", "nc_generation_runs", params={"select": "*", "project_id": f"eq.{project_id}", "order": "created_at.desc"})
        return [GenerationRunResponse(**row) for row in rows]

    def update_run(self, project_id: str, run_id: str, **updates: Any) -> GenerationRunResponse:
        payload = {key: self._jsonable(value) for key, value in {**updates, "updated_at": utc_now().isoformat()}.items()}
        self._request("PATCH", "nc_generation_runs", params={"id": f"eq.{run_id}", "project_id": f"eq.{project_id}"}, json=payload, prefer="return=minimal")
        run = self.get_run(project_id, run_id)
        if not run:
            raise KeyError(run_id)
        return run

    def create_version(self, *, project_id: str, prompt: str, profile: str, model: str, artifacts: dict[str, str], generated_code: str, status: str, error: str | None, parent_version_id: str | None, parameters: list[ParameterControl], spec: PartSpec | None = None, spec_delta: list[dict[str, Any]] | None = None, change_summary: str = "") -> VersionResponse:
        now, version_id = utc_now(), f"ver_{uuid.uuid4().hex[:10]}"
        payload = {"id": version_id, "project_id": project_id, "parent_version_id": parent_version_id, "prompt": prompt, "profile": profile, "model": model, "artifacts": artifacts, "generated_code": generated_code, "parameters": [p.model_dump() for p in parameters], "spec": spec.model_dump() if spec else None, "spec_delta": spec_delta or [], "change_summary": change_summary, "status": status, "error": error, "created_at": now.isoformat()}
        self._request("POST", "nc_versions", json=payload, prefer="return=minimal")
        self._request("PATCH", "nc_projects", params={"id": f"eq.{project_id}"}, json={"updated_at": now.isoformat()}, prefer="return=minimal")
        return VersionResponse(**payload)

    def _version(self, row: dict) -> VersionResponse:
        return VersionResponse(**{**row, "parameters": [ParameterControl(**p) for p in row.get("parameters") or []], "spec": PartSpec(**row["spec"]) if row.get("spec") else None})

    def get_version(self, project_id: str, version_id: str) -> VersionResponse | None:
        rows = self._request("GET", "nc_versions", params={"select": "*", "project_id": f"eq.{project_id}", "id": f"eq.{version_id}", "limit": "1"})
        return self._version(rows[0]) if rows else None

    def list_versions(self, project_id: str) -> list[VersionResponse]:
        rows = self._request("GET", "nc_versions", params={"select": "*", "project_id": f"eq.{project_id}", "order": "created_at.desc"})
        return [self._version(row) for row in rows]

    def create_attachment(self, *, project_id: str, session_id: str, content_type: str, size_bytes: int, storage_key: str, upload_url: str | None, max_active: int = 3) -> AttachmentResponse:
        now = utc_now()
        payload = {"id": f"att_{uuid.uuid4().hex[:12]}", "project_id": project_id, "owner_session_id": session_id, "status": "reserved", "content_type": content_type, "size_bytes": size_bytes, "storage_key": storage_key, "expires_at": (now + timedelta(days=7)).isoformat(), "created_at": now.isoformat()}
        result = self._request("POST", "rpc/nc_reserve_attachment", json={
            "p_id": payload["id"], "p_project_id": project_id, "p_owner_session_id": session_id,
            "p_content_type": content_type, "p_size_bytes": size_bytes, "p_storage_key": storage_key,
            "p_expires_at": payload["expires_at"], "p_max_active": max_active,
        })
        row = result[0] if isinstance(result, list) else result
        if not row.get("reserved"):
            raise ValueError("Project image limit reached")
        return AttachmentResponse(**payload, upload_url=upload_url)

    def get_attachment(self, project_id: str, attachment_id: str) -> AttachmentResponse | None:
        rows = self._request("GET", "nc_attachments", params={"select": "*", "project_id": f"eq.{project_id}", "id": f"eq.{attachment_id}", "limit": "1"})
        return AttachmentResponse(**rows[0]) if rows else None

    def list_attachments(self, project_id: str, *, include_deleted: bool = False) -> list[AttachmentResponse]:
        params = {"select": "*", "project_id": f"eq.{project_id}", "order": "created_at.desc"}
        if not include_deleted:
            params["status"] = "neq.deleted"
        return [AttachmentResponse(**row) for row in self._request("GET", "nc_attachments", params=params)]

    def update_attachment(self, project_id: str, attachment_id: str, **updates: Any) -> AttachmentResponse:
        persisted = {key: value for key, value in updates.items() if key not in {"upload_url", "preview_url"}}
        self._request("PATCH", "nc_attachments", params={"id": f"eq.{attachment_id}", "project_id": f"eq.{project_id}"}, json=persisted, prefer="return=minimal")
        attachment = self.get_attachment(project_id, attachment_id)
        if not attachment:
            raise KeyError(attachment_id)
        return attachment

    def list_expired_attachments(self) -> list[AttachmentResponse]:
        rows = self._request("GET", "nc_attachments", params={
            "select": "*", "status": "neq.deleted", "expires_at": f"lte.{utc_now().isoformat()}",
        })
        return [AttachmentResponse(**row) for row in rows]
