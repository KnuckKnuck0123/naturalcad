from __future__ import annotations

import re
import threading
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from .models import (
    AttachmentResponse,
    GenerationRunResponse,
    MessageResponse,
    ParameterControl,
    PartSpec,
    ProjectResponse,
    SessionResponse,
    VersionResponse,
    utc_now,
)


@dataclass
class QuotaState:
    bucket: deque[float]


class InMemoryRepo:
    """Reference repository used locally and as the behavioral contract for Supabase."""

    def __init__(self) -> None:
        self.sessions: dict[str, SessionResponse] = {}
        self.user_sessions: dict[str, str] = {}
        self.projects: dict[str, ProjectResponse] = {}
        self.project_versions: defaultdict[str, list[VersionResponse]] = defaultdict(list)
        self.project_messages: defaultdict[str, list[MessageResponse]] = defaultdict(list)
        self.project_runs: defaultdict[str, list[GenerationRunResponse]] = defaultdict(list)
        self.project_attachments: defaultdict[str, list[AttachmentResponse]] = defaultdict(list)
        self.quotas: dict[str, QuotaState] = {}
        self._lock = threading.RLock()

    def create_guest_session(self, runs_per_window: int) -> SessionResponse:
        session = SessionResponse(
            session_id=f"guest_{uuid.uuid4().hex}",
            actor_type="guest",
            created_at=utc_now(),
            expires_at=utc_now() + timedelta(days=7),
            quotas={"runs_per_window": runs_per_window},
        )
        with self._lock:
            self.sessions[session.session_id] = session
            self.quotas[session.session_id] = QuotaState(bucket=deque())
        return session

    def create_user_session(self, user_id: str, runs_per_window: int) -> SessionResponse:
        with self._lock:
            session_id = self.user_sessions.get(user_id)
            if session_id and session_id in self.sessions:
                return self.sessions[session_id]
            session = SessionResponse(
                session_id=f"user_{uuid.uuid4().hex}",
                actor_type="user",
                created_at=utc_now(),
                expires_at=utc_now() + timedelta(days=30),
                quotas={"runs_per_window": runs_per_window},
            )
            self.sessions[session.session_id] = session
            self.user_sessions[user_id] = session.session_id
            self.quotas[session.session_id] = QuotaState(bucket=deque())
            return session

    def get_session(self, session_id: str) -> SessionResponse | None:
        session = self.sessions.get(session_id)
        return session if session and session.expires_at > utc_now() else None

    def check_and_consume_quota(self, session_id: str, *, max_runs: int, window_seconds: int) -> tuple[bool, int]:
        with self._lock:
            state = self.quotas.setdefault(session_id, QuotaState(bucket=deque()))
            now = time.time()
            cutoff = now - window_seconds
            while state.bucket and state.bucket[0] < cutoff:
                state.bucket.popleft()
            if len(state.bucket) >= max_runs:
                return False, 0
            state.bucket.append(now)
            return True, max_runs - len(state.bucket)

    def create_project(self, session_id: str, title: str, mode: str, output_type: str) -> ProjectResponse:
        now = utc_now()
        project = ProjectResponse(
            id=f"proj_{uuid.uuid4().hex[:10]}", title=title, mode=mode, output_type=output_type,
            owner_session_id=session_id, created_at=now, updated_at=now,
        )
        with self._lock:
            self.projects[project.id] = project
        return project

    def get_project(self, project_id: str) -> ProjectResponse | None:
        return self.projects.get(project_id)

    def create_message(
        self, *, project_id: str, role: str, content: str, attachment_ids: list[str] | None = None,
        run_id: str | None = None, version_id: str | None = None,
    ) -> MessageResponse:
        message = MessageResponse(
            id=f"msg_{uuid.uuid4().hex[:12]}", project_id=project_id, role=role, content=content,
            attachment_ids=attachment_ids or [], run_id=run_id, version_id=version_id, created_at=utc_now(),
        )
        with self._lock:
            self.project_messages[project_id].append(message)
        return message

    def list_messages(self, project_id: str) -> list[MessageResponse]:
        return list(self.project_messages.get(project_id, []))

    def create_run(
        self, *, project_id: str, session_id: str, parent_version_id: str | None,
        idempotency_key: str, message: str, attachment_ids: list[str], profile: str,
    ) -> tuple[GenerationRunResponse, bool]:
        with self._lock:
            existing = next(
                (r for r in self.project_runs[project_id] if r.idempotency_key == idempotency_key), None
            )
            if existing:
                return existing, False
            now = utc_now()
            run = GenerationRunResponse(
                id=f"run_{uuid.uuid4().hex[:12]}", project_id=project_id, session_id=session_id,
                parent_version_id=parent_version_id, idempotency_key=idempotency_key, message=message,
                attachment_ids=attachment_ids, profile=profile, status="submitted", created_at=now, updated_at=now,
            )
            self.project_runs[project_id].append(run)
            return run, True

    def get_run(self, project_id: str, run_id: str) -> GenerationRunResponse | None:
        return next((r for r in self.project_runs.get(project_id, []) if r.id == run_id), None)

    def list_runs(self, project_id: str) -> list[GenerationRunResponse]:
        return sorted(self.project_runs.get(project_id, []), key=lambda r: r.created_at, reverse=True)

    def update_run(self, project_id: str, run_id: str, **updates: Any) -> GenerationRunResponse:
        with self._lock:
            run = self.get_run(project_id, run_id)
            if not run:
                raise KeyError(run_id)
            updated = run.model_copy(update={**updates, "updated_at": utc_now()})
            rows = self.project_runs[project_id]
            rows[rows.index(run)] = updated
            return updated

    def create_version(
        self, *, project_id: str, prompt: str, profile: str, model: str,
        artifacts: dict[str, str], generated_code: str, status: str, error: str | None,
        parent_version_id: str | None, parameters: list[ParameterControl], spec: PartSpec | None = None,
        spec_delta: list[dict[str, Any]] | None = None, change_summary: str = "",
    ) -> VersionResponse:
        version = VersionResponse(
            id=f"ver_{uuid.uuid4().hex[:10]}", project_id=project_id,
            parent_version_id=parent_version_id, prompt=prompt, profile=profile, model=model,
            artifacts=artifacts, generated_code=generated_code, parameters=parameters, spec=spec,
            spec_delta=spec_delta or [], change_summary=change_summary, status=status, error=error,
            created_at=utc_now(),
        )
        with self._lock:
            self.project_versions[project_id].append(version)
            project = self.projects[project_id]
            self.projects[project_id] = project.model_copy(update={"updated_at": version.created_at})
        return version

    def get_version(self, project_id: str, version_id: str) -> VersionResponse | None:
        return next((v for v in self.project_versions.get(project_id, []) if v.id == version_id), None)

    def list_versions(self, project_id: str) -> list[VersionResponse]:
        return sorted(self.project_versions.get(project_id, []), key=lambda v: v.created_at, reverse=True)

    def create_attachment(
        self, *, project_id: str, session_id: str, content_type: str, size_bytes: int,
        storage_key: str, upload_url: str | None, max_active: int = 3,
    ) -> AttachmentResponse:
        now = utc_now()
        with self._lock:
            active = sum(a.status not in {"failed", "deleted"} for a in self.project_attachments[project_id])
            if active >= max_active:
                raise ValueError("Project image limit reached")
            attachment = AttachmentResponse(
                id=f"att_{uuid.uuid4().hex[:12]}", project_id=project_id, owner_session_id=session_id,
                status="reserved", content_type=content_type, size_bytes=size_bytes, storage_key=storage_key,
                upload_url=upload_url, expires_at=now + timedelta(days=7), created_at=now,
            )
            self.project_attachments[project_id].append(attachment)
        return attachment

    def get_attachment(self, project_id: str, attachment_id: str) -> AttachmentResponse | None:
        return next((a for a in self.project_attachments.get(project_id, []) if a.id == attachment_id), None)

    def list_attachments(self, project_id: str, *, include_deleted: bool = False) -> list[AttachmentResponse]:
        rows = self.project_attachments.get(project_id, [])
        return [a for a in rows if include_deleted or a.status != "deleted"]

    def update_attachment(self, project_id: str, attachment_id: str, **updates: Any) -> AttachmentResponse:
        with self._lock:
            attachment = self.get_attachment(project_id, attachment_id)
            if not attachment:
                raise KeyError(attachment_id)
            updated = attachment.model_copy(update=updates)
            rows = self.project_attachments[project_id]
            rows[rows.index(attachment)] = updated
            return updated

    def list_expired_attachments(self) -> list[AttachmentResponse]:
        now = utc_now()
        return [
            item for rows in self.project_attachments.values() for item in rows
            if item.status != "deleted" and item.expires_at <= now
        ]


def derive_legacy_spec(prompt: str, mode: str, output_type: str) -> PartSpec:
    dimensions: dict[str, float] = {}
    for label in ("width", "height", "thickness", "diameter", "length", "depth", "span"):
        match = re.search(rf"\b{label}\b\s*(?:=|:|of)?\s*(\d+(?:\.\d+)?)", prompt.lower())
        if match:
            dimensions[label] = float(match.group(1))
    return PartSpec(
        intent=prompt.strip(), mode=mode, output_type=output_type,
        semantic_part={"category": "unspecified", "function": prompt.strip(), "topology": []},
        geometry={"features": []}, dimensions=dimensions,
        assumptions=["Legacy prompt converted to a draft structured specification."],
    )


def extract_slider_controls(prompt: str) -> list[ParameterControl]:
    spec = derive_legacy_spec(prompt, "part", "3d_solid")
    values = spec.dimensions
    return [
        ParameterControl(key="width", label="Width", min=20, max=400, step=1, value=values.get("width", 80)),
        ParameterControl(key="height", label="Height", min=20, max=400, step=1, value=values.get("height", 50)),
        ParameterControl(key="thickness", label="Thickness", min=1, max=80, step=0.5, value=values.get("thickness", 6)),
    ]
