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

_DIMENSION_LABELS = ("width", "height", "thickness", "diameter", "length", "depth", "span")
_CATEGORY_HINTS = (
    ("support_bracket", ("bracket", "support", "mount")),
    ("flange", ("flange",)),
    ("adapter", ("adapter", "coupler")),
    ("plate", ("plate", "backplate", "back plate")),
    ("shaft_collar", ("shaft", "collar", "bushing")),
    ("tube_interface", ("tube", "pipe", "hose")),
)
_FEATURE_HINTS = (
    ("mounting_holes", ("hole", "holes", "bolt", "bolts", "screw", "screws")),
    ("slots", ("slot", "slots")),
    ("tabs", ("tab", "tabs", "mounting tab", "mounting tabs")),
    ("ribs", ("rib", "ribs", "gusset", "gussets")),
    ("bosses", ("boss", "bosses")),
    ("flanges", ("flange", "flanges")),
    ("tube_interfaces", ("tube", "pipe", "hose")),
)
_STYLE_HINTS = ("industrial", "structural", "heavy-duty", "machined", "cast", "printed", "sheet metal")


def _extract_dimensions(prompt: str) -> dict[str, float]:
    text = prompt.lower()
    dimensions: dict[str, float] = {}

    triplet = re.search(
        r"\b(\d+(?:\.\d+)?)\s*(?:mm)?\s*[x×]\s*(\d+(?:\.\d+)?)\s*(?:mm)?\s*[x×]\s*(\d+(?:\.\d+)?)\b",
        text,
    )
    if triplet:
        dimensions.update({
            "width": float(triplet.group(1)),
            "height": float(triplet.group(2)),
            "thickness": float(triplet.group(3)),
        })

    for label in _DIMENSION_LABELS:
        patterns = (
            rf"\b{label}\b\s*(?:=|:|of|to|is)?\s*(\d+(?:\.\d+)?)\s*(?:mm|millimeters?)?\b",
            rf"\b(\d+(?:\.\d+)?)\s*(?:mm|millimeters?)?\s*{label}\b",
        )
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                dimensions[label] = float(match.group(1))
                break
    return dimensions


def _feature_count(text: str, keyword: str) -> int | None:
    singular = re.escape(keyword.rstrip("s"))
    plural = re.escape(keyword if keyword.endswith("s") else f"{keyword}s")
    match = re.search(rf"\b(\d+)\s+(?:{singular}|{plural})\b", text)
    return int(match.group(1)) if match else None


def _infer_category(text: str) -> str:
    for category, hints in _CATEGORY_HINTS:
        if any(hint in text for hint in hints):
            return category
    return "unspecified"


def _infer_symmetry(text: str) -> str:
    if "asymmetric" in text or "asymmetrical" in text:
        return "asymmetric"
    if any(token in text for token in ("symmetric", "symmetrical", "mirror", "mirrored")):
        return "symmetric"
    return "unspecified"


def _infer_interfaces(text: str) -> list[str]:
    interfaces = []
    for name, hints in (
        ("wall_mount", ("wall", "mount")),
        ("tube_interface", ("tube", "pipe", "hose")),
        ("shaft_interface", ("shaft", "axle")),
        ("bolt_pattern", ("bolt", "screw", "fastener")),
    ):
        if any(hint in text for hint in hints):
            interfaces.append(name)
    return interfaces


def _infer_features(text: str, dimensions: dict[str, float]) -> tuple[list[dict[str, Any]], list[str]]:
    features: list[dict[str, Any]] = []
    primitive_strategy: list[str] = []
    for feature_type, hints in _FEATURE_HINTS:
        if not any(hint in text for hint in hints):
            continue
        feature: dict[str, Any] = {"name": feature_type, "feature_type": feature_type}
        count = next((_feature_count(text, hint.split()[-1]) for hint in hints if _feature_count(text, hint.split()[-1]) is not None), None)
        if count is not None:
            feature["count"] = count
        attrs: dict[str, Any] = {}
        if feature_type == "mounting_holes":
            if "diameter" in dimensions:
                attrs["diameter_mm"] = dimensions["diameter"]
            metric_match = re.search(r"\bm(\d+(?:\.\d+)?)\b", text)
            if metric_match:
                attrs["thread_major_diameter_mm"] = float(metric_match.group(1))
            primitive_strategy.extend(["extrude", "boolean_subtract"])
        elif feature_type in {"slots", "tabs", "flanges"}:
            primitive_strategy.extend(["extrude", "boolean_union"])
        elif feature_type in {"ribs", "bosses"}:
            primitive_strategy.extend(["extrude", "boolean_union"])
        elif feature_type == "tube_interfaces":
            if "diameter" in dimensions:
                attrs["interface_diameter_mm"] = dimensions["diameter"]
            primitive_strategy.extend(["revolve", "boolean_subtract"])
        if attrs:
            feature["attributes"] = attrs
        features.append(feature)
    return features, sorted(set(primitive_strategy or ["extrude"]))


def _infer_constraints(text: str, dimensions: dict[str, float]) -> list[dict[str, Any]]:
    constraints: list[dict[str, Any]] = []
    tolerance_match = re.search(r"(?:\+/-|±)\s*(\d+(?:\.\d+)?)\s*(?:mm|millimeters?)?", text)
    if tolerance_match:
        constraints.append({"kind": "tolerance", "target": "global", "value": float(tolerance_match.group(1)), "units": "mm"})
    clearance_match = re.search(
        r"(?:\bclearance\b(?:\s*(?:of|=|:|is))?\s*(\d+(?:\.\d+)?)|\b(\d+(?:\.\d+)?)\s*(?:mm|millimeters?)?\s+clearance\b)",
        text,
    )
    if clearance_match:
        value = clearance_match.group(1) or clearance_match.group(2)
        constraints.append({"kind": "clearance", "target": "interface", "value": float(value), "units": "mm"})
    if any(token in text for token in ("press fit", "slip fit", "interference fit")):
        fit = "press_fit" if "press fit" in text else "slip_fit" if "slip fit" in text else "interference_fit"
        constraints.append({"kind": "fit", "target": "interface", "value": fit})
    if "thickness" in dimensions:
        constraints.append({"kind": "driving_dimension", "target": "thickness", "value": dimensions["thickness"], "units": "mm"})
    return constraints


def _infer_style(text: str, symmetry: str) -> dict[str, Any]:
    keywords = [keyword for keyword in _STYLE_HINTS if keyword in text]
    manufacturing_bias = "machined" if "machined" in text else "cast" if "cast" in text else "printed" if "printed" in text else "unspecified"
    return {"keywords": keywords, "symmetry": symmetry, "manufacturing_bias": manufacturing_bias}


def _infer_family_hint(category: str, features: list[dict[str, Any]]) -> dict[str, Any]:
    names = {feature["feature_type"] for feature in features}
    generation_mode = "new"
    confidence = 0.35
    if category == "support_bracket":
        generation_mode = "extend"
        confidence = 0.72
    elif category in {"flange", "adapter", "plate"}:
        generation_mode = "reuse"
        confidence = 0.68
    if "ribs" in names or "tube_interfaces" in names:
        confidence = min(0.9, confidence + 0.08)
    return {
        "name": category,
        "generation_mode": generation_mode,
        "confidence": round(confidence, 2),
        "novelty_score": 0.55 if generation_mode == "reuse" else 0.72 if generation_mode == "extend" else 0.84,
    }


def _infer_uncertainties(text: str, dimensions: dict[str, float], interfaces: list[str], features: list[dict[str, Any]]) -> list[str]:
    uncertainties: list[str] = []
    if any(feature["feature_type"] == "mounting_holes" for feature in features) and "diameter" not in dimensions and not re.search(r"\bm\d+(?:\.\d+)?\b", text):
        uncertainties.append("Hole size was referenced but no explicit diameter or fastener size was given.")
    if "tube_interface" in interfaces and "diameter" not in dimensions:
        uncertainties.append("Tube or pipe interface mentioned without an explicit interface diameter.")
    if any(token in text for token in ("fit", "clearance", "tolerance")) and not re.search(r"(?:\+/-|±|\bclearance\b)", text):
        uncertainties.append("Fit-critical language was used without an explicit tolerance or clearance value.")
    return uncertainties


def _infer_notes(category: str, constraints: list[dict[str, Any]]) -> list[str]:
    notes = [f"Treat {category} as a concept-to-CAD part specification until fabrication details are confirmed."]
    if any(item["kind"] in {"tolerance", "clearance", "fit"} for item in constraints):
        notes.append("Preserve fit-critical constraints through later refinement turns.")
    return notes


def _build_iteration_memory(
    *,
    prior: dict[str, Any] | None,
    dimensions: dict[str, float],
    constraints: list[dict[str, Any]],
    features: list[dict[str, Any]],
    uncertainties: list[str],
    message: str,
) -> dict[str, Any]:
    turn_index = int((prior or {}).get("turn_index", 0)) + 1
    return {
        "turn_index": turn_index,
        "last_user_request": message.strip(),
        "active_dimensions": sorted(dimensions.keys()),
        "preserved_constraints": [item.get("kind", "unknown") for item in constraints],
        "tracked_features": [feature.get("name") or feature.get("feature_type") for feature in features],
        "unresolved_questions": uncertainties[:3],
    }


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
        self.ip_quotas: dict[str, QuotaState] = {}
        self.run_claims: dict[str, tuple[float, str]] = {}
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

    def check_and_consume_ip_quota(self, ip_hash: str, *, kind: str, max_events: int, window_seconds: int) -> tuple[bool, int]:
        with self._lock:
            state = self.ip_quotas.setdefault(f"{ip_hash}:{kind}", QuotaState(bucket=deque()))
            now = time.time()
            cutoff = now - window_seconds
            while state.bucket and state.bucket[0] < cutoff:
                state.bucket.popleft()
            if len(state.bucket) >= max_events:
                return False, 0
            state.bucket.append(now)
            return True, max_events - len(state.bucket)

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

    def claim_run(self, project_id: str, run_id: str, *, stale_seconds: int) -> str | None:
        """Atomically claim exclusive processing of a run. Returns a claim token, or None if
        another worker holds a fresh claim. Stale claims (dead workers) can be stolen."""
        with self._lock:
            if not self.get_run(project_id, run_id):
                return None
            now = time.time()
            existing = self.run_claims.get(run_id)
            if existing and now - existing[0] < stale_seconds:
                return None
            token = uuid.uuid4().hex
            self.run_claims[run_id] = (now, token)
            return token

    def refresh_run_claim(self, project_id: str, run_id: str, token: str) -> bool:
        """Heartbeat an existing claim. Returns False if the claim was stolen."""
        with self._lock:
            existing = self.run_claims.get(run_id)
            if not existing or existing[1] != token:
                return False
            self.run_claims[run_id] = (time.time(), token)
            return True

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
    text = prompt.lower()
    dimensions = _extract_dimensions(prompt)
    category = _infer_category(text)
    symmetry = _infer_symmetry(text)
    interfaces = _infer_interfaces(text)
    features, primitive_strategy = _infer_features(text, dimensions)
    constraints = _infer_constraints(text, dimensions)
    style = _infer_style(text, symmetry)
    uncertainties = _infer_uncertainties(text, dimensions, interfaces, features)
    notes = _infer_notes(category, constraints)
    iteration_memory = _build_iteration_memory(
        prior=None,
        dimensions=dimensions,
        constraints=constraints,
        features=features,
        uncertainties=uncertainties,
        message=prompt,
    )
    return PartSpec(
        intent=prompt.strip(), mode=mode, output_type=output_type,
        semantic_part={
            "category": category,
            "function": prompt.strip(),
            "topology": [feature["name"] for feature in features],
            "symmetry": symmetry,
            "interfaces": interfaces,
        },
        family_hint=_infer_family_hint(category, features),
        geometry={"primitive_strategy": primitive_strategy, "features": features},
        dimensions=dimensions,
        constraints=constraints,
        style=style,
        iteration_memory=iteration_memory,
        assumptions=["Legacy prompt converted to a draft structured specification."],
        uncertainties=uncertainties,
        notes=notes,
    )


def extract_slider_controls(prompt: str) -> list[ParameterControl]:
    spec = derive_legacy_spec(prompt, "part", "3d_solid")
    values = spec.dimensions
    return [
        ParameterControl(key="width", label="Width", min=20, max=400, step=1, value=values.get("width", 80)),
        ParameterControl(key="height", label="Height", min=20, max=400, step=1, value=values.get("height", 50)),
        ParameterControl(key="thickness", label="Thickness", min=1, max=80, step=0.5, value=values.get("thickness", 6)),
    ]
