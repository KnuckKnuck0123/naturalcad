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
            refined = derive_legacy_spec(payload["message"], payload["mode"], payload["output_type"])
            merged_dimensions = {**spec.dimensions, **refined.dimensions}
            semantic_part = {**spec.semantic_part, "last_user_request": payload["message"]}
            iteration_memory = dict(spec.iteration_memory)
            iteration_memory.update({
                "turn_index": int(iteration_memory.get("turn_index", 0)) + 1,
                "last_user_request": payload["message"],
                "active_dimensions": sorted(merged_dimensions.keys()),
            })
            spec = spec.model_copy(update={"intent": payload["message"], "dimensions": merged_dimensions, "semantic_part": semantic_part, "iteration_memory": iteration_memory})
        spec_delta = [{"op": "refine", "path": "/intent", "value": payload["message"]}]
        for label, value in spec.dimensions.items():
            if parent and isinstance(parent, dict) and (parent.get("dimensions") or {}).get(label) != value:
                spec_delta.append({"op": "set", "path": f"/dimensions/{label}", "value": value})
        return {
            "ready_to_generate": True,
            "spec": spec.model_dump(),
            "spec_delta": spec_delta,
            "change_summary": "Updated the structured part intent and merged dimensional edits." if len(spec_delta) > 1 else "Updated the structured part intent.",
            "clarification_questions": [],
            "model": "local/spec-mock",
            "usage": {},
        }
    return {
        "success": True, "urls": {}, "generated_code": "", "model": "local/cad-mock", "usage": {}
    }


def _legacy_prompt(message: str, project: ProjectResponse, parent: Any, image_urls: list[str]) -> str:
    prompt = message
    if parent:
        prompt = (
            f"Continue from previous version {parent.id}. "
            f"Previous prompt: {parent.prompt}\n\n"
            f"User refinement: {message}"
        )
    if image_urls:
        refs = "\n".join(f"- {url}" for url in image_urls)
        prompt = f"{prompt}\n\nReference images:\n{refs}"
    return prompt


def _process_generation_legacy(
    repo: Any,
    project: ProjectResponse,
    run: GenerationRunResponse,
    parent: Any,
    image_urls: list[str],
    legacy_error: Exception,
    claim_token: str,
) -> None:
    prompt = _legacy_prompt(run.message, project, parent, image_urls)
    worker = _worker_request("legacy_generate", {
        "prompt": prompt,
        "mode": project.mode,
        "output_type": project.output_type,
    })
    success = bool(worker.get("success")) and not worker.get("error")
    if not success:
        raise RuntimeError(worker.get("error") or str(legacy_error))
    if not repo.refresh_run_claim(project.id, run.id, claim_token):
        return  # claim stolen; the new owner is responsible for terminal state
    version = repo.create_version(
        project_id=project.id,
        prompt=run.message,
        profile=run.profile,
        model=worker.get("model", settings.cad_model),
        artifacts=worker.get("urls", {}),
        generated_code=worker.get("generated_code", ""),
        status="completed",
        error=None,
        parent_version_id=run.parent_version_id,
        parameters=extract_slider_controls(run.message),
        spec=None,
        spec_delta=[{
            "op": "legacy_fallback",
            "value": str(legacy_error)[:300],
        }],
        change_summary="Generated a new CAD version via legacy worker fallback.",
    )
    repo.update_run(
        project.id,
        run.id,
        status="completed",
        version_id=version.id,
        change_summary=version.change_summary,
        telemetry={
            "fallback": "legacy_generate",
            "legacy_error": str(legacy_error)[:300],
            "cad_model": worker.get("model", settings.cad_model),
            "cad_usage": worker.get("usage", {}),
        },
    )
    repo.create_message(
        project_id=project.id,
        role="assistant",
        content=version.change_summary,
        run_id=run.id,
        version_id=version.id,
    )


RUN_CLAIM_STALE_SECONDS = 600


def process_generation(repo: Any, run_id: str, project: ProjectResponse) -> None:
    run = repo.get_run(project.id, run_id)
    if not run or run.status not in {"submitted", "awaiting_clarification"}:
        return
    # Exclusive claim prevents the poll-triggered recovery loop from double-executing
    # a run whose original background task is still alive (duplicate versions + LLM spend).
    claim_token = repo.claim_run(project.id, run_id, stale_seconds=RUN_CLAIM_STALE_SECONDS)
    if claim_token is None:
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
        try:
            resolution = _worker_request("resolve_spec", {
                "parent_spec": parent_spec.model_dump() if parent_spec else None,
                "message": run.message, "mode": project.mode, "output_type": project.output_type,
                "image_urls": image_urls,
                "model": settings.spec_model,
                "vision_model": settings.vision_model,
                "vision_max_tokens": settings.vision_summary_max_tokens,
            })
        except Exception as legacy_error:
            _process_generation_legacy(repo, project, run, parent, image_urls, legacy_error, claim_token)
            return
        spec = PartSpec.model_validate(resolution["spec"])
        telemetry = {
            "spec_model": resolution.get("model", settings.spec_model),
            "vision_model": resolution.get("vision_model"),
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
            if not repo.refresh_run_claim(project.id, run.id, claim_token):
                return  # claim stolen; abort before spending more LLM calls
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
        if not repo.refresh_run_claim(project.id, run.id, claim_token):
            return  # claim stolen; the new owner publishes terminal state
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
        if not repo.refresh_run_claim(project.id, run.id, claim_token):
            return  # claim stolen; do not clobber the new owner's terminal state
        repo.update_run(project.id, run.id, status="failed", error=str(exc)[:500])
        repo.create_message(project_id=project.id, role="assistant", content="Generation failed. Please retry.", run_id=run.id)
