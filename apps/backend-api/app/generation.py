from __future__ import annotations

import time
from typing import Any

import httpx

from .config import settings
from .models import GenerationRunResponse, PartSpec, ProjectResponse
from .repository import derive_legacy_spec, extract_slider_controls
from .storage import SupabaseImageStorage


def _worker_request(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    if not settings.cad_worker_url:
        return _mock_worker(action, payload)
    headers = {"Content-Type": "application/json"}
    if settings.cad_worker_api_key:
        headers["x-api-key"] = settings.cad_worker_api_key
    with httpx.Client(timeout=240.0) as client:
        response = client.post(settings.cad_worker_url, headers=headers, json={"action": action, **payload})
    response.raise_for_status()
    return response.json()


def _mock_worker(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    if action == "resolve_spec":
        parent = payload.get("parent_spec")
        spec = PartSpec(**parent) if parent else derive_legacy_spec(
            payload["message"], payload["mode"], payload["output_type"]
        )
        if parent:
            spec = spec.model_copy(update={"intent": payload["message"]})
        return {
            "ready_to_generate": True,
            "spec": spec.model_dump(),
            "spec_delta": [{"op": "refine", "path": "/intent", "value": payload["message"]}],
            "change_summary": "Updated the structured part intent.",
            "clarification_questions": [],
            "model": "local/spec-mock",
            "usage": {},
        }
    return {
        "success": True, "urls": {}, "generated_code": "", "model": "local/cad-mock", "usage": {}
    }


def process_generation(repo: Any, run_id: str, project: ProjectResponse) -> None:
    run = repo.get_run(project.id, run_id)
    if not run or run.status not in {"submitted", "awaiting_clarification"}:
        return
    started = time.monotonic()
    try:
        run = repo.update_run(project.id, run.id, status="resolving_spec", error=None)
        parent = repo.get_version(project.id, run.parent_version_id) if run.parent_version_id else None
        parent_spec = parent.spec if parent and parent.spec else (
            derive_legacy_spec(parent.prompt, project.mode, project.output_type) if parent else None
        )
        storage = SupabaseImageStorage()
        image_urls: list[str] = []
        for attachment_id in run.attachment_ids:
            attachment = repo.get_attachment(project.id, attachment_id)
            if not attachment or attachment.status != "ready" or not attachment.sanitized_storage_key:
                raise ValueError("Every selected attachment must be ready before generation")
            image_urls.append(storage.create_signed_read(attachment.sanitized_storage_key, expires_in=600))

        spec_started = time.monotonic()
        resolution = _worker_request("resolve_spec", {
            "parent_spec": parent_spec.model_dump() if parent_spec else None,
            "message": run.message, "mode": project.mode, "output_type": project.output_type,
            "image_urls": image_urls, "model": settings.spec_model,
        })
        spec = PartSpec.model_validate(resolution["spec"])
        telemetry = {
            "spec_model": resolution.get("model", settings.spec_model),
            "spec_latency_ms": int((time.monotonic() - spec_started) * 1000),
            "spec_usage": resolution.get("usage", {}),
        }
        common = {
            "draft_spec": spec,
            "spec_delta": resolution.get("spec_delta", []),
            "change_summary": resolution.get("change_summary", ""),
            "clarification_questions": resolution.get("clarification_questions", []),
            "telemetry": telemetry,
        }
        if not resolution.get("ready_to_generate", False):
            repo.update_run(project.id, run.id, status="awaiting_clarification", **common)
            questions = "\n".join(resolution.get("clarification_questions") or ["What should be clarified?"])
            repo.create_message(project_id=project.id, role="assistant", content=questions, run_id=run.id)
            return

        repo.update_run(project.id, run.id, status="generating_code", **common)
        cad_started = time.monotonic()
        generated: dict[str, Any] = {}
        published: dict[str, Any] = {}
        execution_error: str | None = None
        for _ in range(3):
            generated = _worker_request("generate_code", {
                "spec": spec.model_dump(), "model": settings.cad_model,
                "execution_error": execution_error,
            })
            if not generated.get("success"):
                execution_error = generated.get("error") or "Code generation failed"
                continue
            repo.update_run(project.id, run.id, status="executing", telemetry=telemetry)
            published = _worker_request("execute_and_publish", {
                "generated_code": generated.get("generated_code", ""),
                "output_type": project.output_type,
            })
            if published.get("success"):
                break
            execution_error = published.get("error") or "CAD execution failed"
        telemetry.update({
            "cad_model": generated.get("model", settings.cad_model),
            "cad_latency_ms": int((time.monotonic() - cad_started) * 1000),
            "cad_usage": generated.get("usage", {}),
        })
        if not published.get("success"):
            raise RuntimeError(execution_error or "CAD generation failed")
        repo.update_run(project.id, run.id, status="publishing", telemetry=telemetry)
        version = repo.create_version(
            project_id=project.id, prompt=run.message, profile=run.profile,
            model=generated.get("model", settings.cad_model), artifacts=published.get("urls", {}),
            generated_code=generated.get("generated_code", ""), status="completed", error=None,
            parent_version_id=run.parent_version_id, parameters=extract_slider_controls(run.message),
            spec=spec, spec_delta=resolution.get("spec_delta", []),
            change_summary=resolution.get("change_summary", "Generated a new CAD version."),
        )
        telemetry["total_latency_ms"] = int((time.monotonic() - started) * 1000)
        repo.update_run(project.id, run.id, status="completed", version_id=version.id, telemetry=telemetry)
        repo.create_message(
            project_id=project.id, role="assistant",
            content=version.change_summary or "Generated a new CAD version.", run_id=run.id, version_id=version.id,
        )
    except Exception as exc:  # workflow failures must become inspectable terminal state
        repo.update_run(project.id, run.id, status="failed", error=str(exc)[:500])
        repo.create_message(project_id=project.id, role="assistant", content="Generation failed. Please retry.", run_id=run.id)
