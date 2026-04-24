from __future__ import annotations

import re
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass

from .models import (
    ParameterControl,
    ProjectResponse,
    SessionResponse,
    VersionResponse,
    utc_now,
)


@dataclass
class QuotaState:
    bucket: deque[float]


class InMemoryRepo:
    def __init__(self) -> None:
        self.sessions: dict[str, SessionResponse] = {}
        self.projects: dict[str, ProjectResponse] = {}
        self.project_versions: defaultdict[str, list[VersionResponse]] = defaultdict(list)
        self.quotas: dict[str, QuotaState] = {}

    def create_guest_session(self, runs_per_window: int) -> SessionResponse:
        session = SessionResponse(
            session_id=f"guest_{uuid.uuid4().hex[:12]}",
            actor_type="guest",
            created_at=utc_now(),
            quotas={"runs_per_window": runs_per_window},
        )
        self.sessions[session.session_id] = session
        self.quotas[session.session_id] = QuotaState(bucket=deque())
        return session

    def get_session(self, session_id: str) -> SessionResponse | None:
        return self.sessions.get(session_id)

    def check_and_consume_quota(self, session_id: str, *, max_runs: int, window_seconds: int) -> tuple[bool, int]:
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
            id=f"proj_{uuid.uuid4().hex[:10]}",
            title=title,
            mode=mode,
            output_type=output_type,
            owner_session_id=session_id,
            created_at=now,
            updated_at=now,
        )
        self.projects[project.id] = project
        return project

    def get_project(self, project_id: str) -> ProjectResponse | None:
        return self.projects.get(project_id)

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
        version = VersionResponse(
            id=f"ver_{uuid.uuid4().hex[:10]}",
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
            created_at=utc_now(),
        )
        self.project_versions[project_id].append(version)

        project = self.projects[project_id]
        project.updated_at = version.created_at
        self.projects[project_id] = project
        return version

    def list_versions(self, project_id: str) -> list[VersionResponse]:
        return list(self.project_versions.get(project_id, []))


def extract_slider_controls(prompt: str) -> list[ParameterControl]:
    p = prompt.lower()

    def number_for(keywords: list[str], default: float) -> float:
        for keyword in keywords:
            match = re.search(rf"{keyword}\s*(?:=|:|of)?\s*(\d+(?:\.\d+)?)", p)
            if match:
                return float(match.group(1))
        return default

    width = number_for(["width", "span"], 80)
    height = number_for(["height"], 50)
    thickness = number_for(["thickness", "depth"], 6)
    holes = number_for(["holes", "hole count"], 4)

    return [
        ParameterControl(key="width", label="Width", min=20, max=400, step=1, value=width),
        ParameterControl(key="height", label="Height", min=20, max=400, step=1, value=height),
        ParameterControl(key="thickness", label="Thickness", min=1, max=80, step=0.5, value=thickness),
        ParameterControl(key="holes", label="Hole Count", min=0, max=24, step=1, value=holes),
    ]
