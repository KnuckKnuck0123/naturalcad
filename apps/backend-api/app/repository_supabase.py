from __future__ import annotations

from datetime import UTC, datetime, timedelta
import uuid

import httpx

from .models import ParameterControl, ProjectResponse, SessionResponse, VersionResponse, utc_now


class SupabaseRepo:
    def __init__(self, *, url: str, service_role_key: str) -> None:
        self.url = url.rstrip("/")
        self.key = service_role_key
        self.base = f"{self.url}/rest/v1"

    def _headers(self, *, prefer: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    def _parse_iso(self, value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    def create_guest_session(self, runs_per_window: int) -> SessionResponse:
        session_id = f"guest_{uuid.uuid4().hex[:12]}"
        now = utc_now()
        payload = {
            "id": session_id,
            "actor_type": "guest",
            "created_at": now.isoformat(),
        }
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                f"{self.base}/nc_sessions",
                json=payload,
                headers=self._headers(prefer="return=representation"),
            )
        resp.raise_for_status()

        return SessionResponse(
            session_id=session_id,
            actor_type="guest",
            created_at=now,
            quotas={"runs_per_window": runs_per_window},
        )

    def create_user_session(self, user_id: str, runs_per_window: int) -> SessionResponse:
        select_params = {
            "select": "id,created_at",
            "actor_type": "eq.user",
            "user_id": f"eq.{user_id}",
            "order": "created_at.asc",
            "limit": "1",
        }
        with httpx.Client(timeout=20.0) as client:
            select_resp = client.get(f"{self.base}/nc_sessions", params=select_params, headers=self._headers())
        select_resp.raise_for_status()
        rows = select_resp.json()
        if rows:
            row = rows[0]
            return SessionResponse(
                session_id=row["id"],
                actor_type="user",
                created_at=self._parse_iso(row["created_at"]),
                quotas={"runs_per_window": runs_per_window},
            )

        session_id = f"user_{uuid.uuid4().hex[:12]}"
        now = utc_now()
        insert_payload = {
            "id": session_id,
            "actor_type": "user",
            "user_id": user_id,
            "created_at": now.isoformat(),
        }
        with httpx.Client(timeout=20.0) as client:
            insert_resp = client.post(
                f"{self.base}/nc_sessions",
                json=insert_payload,
                headers=self._headers(prefer="return=representation"),
            )
        insert_resp.raise_for_status()

        return SessionResponse(
            session_id=session_id,
            actor_type="user",
            created_at=now,
            quotas={"runs_per_window": runs_per_window},
        )

    def get_session(self, session_id: str) -> SessionResponse | None:
        params = {
            "select": "id,actor_type,user_id,created_at",
            "id": f"eq.{session_id}",
            "limit": "1",
        }
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(f"{self.base}/nc_sessions", params=params, headers=self._headers())
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            return None

        row = rows[0]
        actor = row.get("actor_type", "guest")
        return SessionResponse(
            session_id=row["id"],
            actor_type=actor,
            created_at=self._parse_iso(row["created_at"]),
            quotas={},
        )

    def check_and_consume_quota(self, session_id: str, *, max_runs: int, window_seconds: int) -> tuple[bool, int]:
        cutoff = (datetime.now(UTC) - timedelta(seconds=window_seconds)).isoformat()
        params = {
            "select": "id",
            "session_id": f"eq.{session_id}",
            "event_type": "eq.generation",
            "created_at": f"gte.{cutoff}",
        }

        with httpx.Client(timeout=20.0) as client:
            count_resp = client.get(f"{self.base}/nc_usage_events", params=params, headers=self._headers())
        count_resp.raise_for_status()
        count = len(count_resp.json())
        if count >= max_runs:
            return False, 0

        with httpx.Client(timeout=20.0) as client:
            insert_resp = client.post(
                f"{self.base}/nc_usage_events",
                json={"session_id": session_id, "event_type": "generation"},
                headers=self._headers(prefer="return=minimal"),
            )
        insert_resp.raise_for_status()

        return True, max_runs - (count + 1)

    def create_project(self, session_id: str, title: str, mode: str, output_type: str) -> ProjectResponse:
        project_id = f"proj_{uuid.uuid4().hex[:10]}"
        now = utc_now()
        payload = {
            "id": project_id,
            "owner_session_id": session_id,
            "title": title,
            "mode": mode,
            "output_type": output_type,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }

        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                f"{self.base}/nc_projects",
                json=payload,
                headers=self._headers(prefer="return=representation"),
            )
        resp.raise_for_status()

        return ProjectResponse(
            id=project_id,
            title=title,
            mode=mode,
            output_type=output_type,
            owner_session_id=session_id,
            created_at=now,
            updated_at=now,
        )

    def get_project(self, project_id: str) -> ProjectResponse | None:
        params = {
            "select": "id,title,mode,output_type,owner_session_id,created_at,updated_at",
            "id": f"eq.{project_id}",
            "limit": "1",
        }
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(f"{self.base}/nc_projects", params=params, headers=self._headers())
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            return None

        row = rows[0]
        return ProjectResponse(
            id=row["id"],
            title=row["title"],
            mode=row["mode"],
            output_type=row["output_type"],
            owner_session_id=row["owner_session_id"],
            created_at=self._parse_iso(row["created_at"]),
            updated_at=self._parse_iso(row["updated_at"]),
        )

    def create_version(
        self,
        *,
        project_id: str,
        prompt: str,
        profile: str,
        model: str,
        artifacts: dict[str, str],
        generated_code: str,
        status: str,
        error: str | None,
        parent_version_id: str | None,
        parameters: list[ParameterControl],
    ) -> VersionResponse:
        version_id = f"ver_{uuid.uuid4().hex[:10]}"
        now = utc_now()

        payload = {
            "id": version_id,
            "project_id": project_id,
            "parent_version_id": parent_version_id,
            "prompt": prompt,
            "profile": profile,
            "model": model,
            "status": status,
            "error": error,
            "artifacts": artifacts,
            "generated_code": generated_code,
            "parameters": [p.model_dump() for p in parameters],
            "created_at": now.isoformat(),
        }

        with httpx.Client(timeout=20.0) as client:
            resp = client.post(
                f"{self.base}/nc_versions",
                json=payload,
                headers=self._headers(prefer="return=representation"),
            )
        resp.raise_for_status()

        patch_params = {"id": f"eq.{project_id}"}
        patch_payload = {"updated_at": now.isoformat()}
        with httpx.Client(timeout=20.0) as client:
            patch_resp = client.patch(
                f"{self.base}/nc_projects",
                params=patch_params,
                json=patch_payload,
                headers=self._headers(prefer="return=minimal"),
            )
        patch_resp.raise_for_status()

        return VersionResponse(
            id=version_id,
            project_id=project_id,
            parent_version_id=parent_version_id,
            prompt=prompt,
            profile=profile,
            model=model,
            artifacts=artifacts,
            generated_code=generated_code,
            parameters=parameters,
            status=status,
            error=error,
            created_at=now,
        )

    def list_versions(self, project_id: str) -> list[VersionResponse]:
        params = {
            "select": "id,project_id,parent_version_id,prompt,profile,model,status,error,artifacts,generated_code,parameters,created_at",
            "project_id": f"eq.{project_id}",
            "order": "created_at.desc",
        }
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(f"{self.base}/nc_versions", params=params, headers=self._headers())
        resp.raise_for_status()
        rows = resp.json()

        out: list[VersionResponse] = []
        for row in rows:
            controls = [ParameterControl(**item) for item in (row.get("parameters") or [])]
            out.append(
                VersionResponse(
                    id=row["id"],
                    project_id=row["project_id"],
                    parent_version_id=row.get("parent_version_id"),
                    prompt=row["prompt"],
                    profile=row["profile"],
                    model=row["model"],
                    artifacts=row.get("artifacts") or {},
                    generated_code=row.get("generated_code") or "",
                    parameters=controls,
                    status=row["status"],
                    error=row.get("error"),
                    created_at=self._parse_iso(row["created_at"]),
                )
            )

        return out
