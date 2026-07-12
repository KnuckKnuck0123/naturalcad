from __future__ import annotations

from app.generation import _mock_worker, process_generation
from app.models import ParameterControl
from app.repository import InMemoryRepo, derive_legacy_spec
from app.repository_supabase import SupabaseRepo


def project_fixture():
    repo = InMemoryRepo()
    session = repo.create_guest_session(5)
    project = repo.create_project(session.session_id, "Test", "part", "3d_solid")
    return repo, session, project


def test_process_generation_completes_via_legacy_fallback(monkeypatch) -> None:
    repo, session, project = project_fixture()
    run, _ = repo.create_run(
        project_id=project.id,
        session_id=session.session_id,
        parent_version_id=None,
        idempotency_key="legacy-fallback-request",
        message="Make a simple mounting bracket",
        attachment_ids=[],
        profile="balanced",
    )

    calls: list[str] = []

    def fake_worker_request(action: str, payload: dict):
        calls.append(action)
        if action == "resolve_spec":
            raise RuntimeError("structured spec worker unavailable")
        if action == "legacy_generate":
            assert payload["prompt"] == "Make a simple mounting bracket"
            return {
                "success": True,
                "urls": {"step": "https://example.test/bracket.step"},
                "generated_code": "result = bracket",
                "model": "mock/legacy-cad",
                "usage": {"total_tokens": 42},
            }
        raise AssertionError(f"Unexpected worker action: {action}")

    monkeypatch.setattr("app.generation._worker_request", fake_worker_request)

    process_generation(repo, run.id, project)

    completed_run = repo.get_run(project.id, run.id)
    assert completed_run is not None
    assert completed_run.status == "completed"
    assert completed_run.version_id is not None
    assert completed_run.telemetry["fallback"] == "legacy_generate"
    assert calls == ["resolve_spec", "legacy_generate"]

    versions = repo.list_versions(project.id)
    assert len(versions) == 1
    version = versions[0]
    assert version.spec is None
    assert version.artifacts["step"] == "https://example.test/bracket.step"
    assert version.change_summary == "Generated a new CAD version via legacy worker fallback."
    assert version.spec_delta == [{"op": "legacy_fallback", "value": "structured spec worker unavailable"}]

    messages = repo.list_messages(project.id)
    assert messages[-1].content == "Generated a new CAD version via legacy worker fallback."


def _make_run(repo, session, project, key: str = "claim-test"):
    run, _ = repo.create_run(
        project_id=project.id,
        session_id=session.session_id,
        parent_version_id=None,
        idempotency_key=key,
        message="Make a simple mounting bracket",
        attachment_ids=[],
        profile="balanced",
    )
    return run


def test_claim_run_is_exclusive_until_stale() -> None:
    repo, session, project = project_fixture()
    run = _make_run(repo, session, project)

    token = repo.claim_run(project.id, run.id, stale_seconds=600)
    assert token is not None
    # A second claimant (e.g. recovery loop re-enqueue) must be rejected while fresh.
    assert repo.claim_run(project.id, run.id, stale_seconds=600) is None
    assert repo.refresh_run_claim(project.id, run.id, token) is True

    # Simulate a dead worker: age the claim past the stale threshold.
    claimed_at, _ = repo.run_claims[run.id]
    repo.run_claims[run.id] = (claimed_at - 601, token)
    stolen = repo.claim_run(project.id, run.id, stale_seconds=600)
    assert stolen is not None and stolen != token
    # The old owner must lose its claim and stop writing.
    assert repo.refresh_run_claim(project.id, run.id, token) is False
    assert repo.refresh_run_claim(project.id, run.id, stolen) is True


def test_process_generation_aborts_when_run_already_claimed(monkeypatch) -> None:
    repo, session, project = project_fixture()
    run = _make_run(repo, session, project)

    def fail_worker(action: str, payload: dict):
        raise AssertionError("worker must not be called for a claimed run")

    monkeypatch.setattr("app.generation._worker_request", fail_worker)

    assert repo.claim_run(project.id, run.id, stale_seconds=600) is not None
    process_generation(repo, run.id, project)

    unchanged = repo.get_run(project.id, run.id)
    assert unchanged is not None
    assert unchanged.status == "submitted"
    assert repo.list_versions(project.id) == []


def test_supabase_jsonable_converts_nested_models() -> None:
    spec = derive_legacy_spec("Bracket width 80 and thickness 6", "part", "3d_solid")
    payload = {
        "draft_spec": spec,
        "parameters": [
            ParameterControl(key="width", label="Width", min=20, max=400, step=1, value=80),
        ],
        "telemetry": {
            "nested_spec": spec,
            "raw": "ok",
        },
    }

    result = SupabaseRepo._jsonable(payload)

    assert result["draft_spec"]["intent"] == "Bracket width 80 and thickness 6"
    assert result["parameters"][0]["key"] == "width"
    assert result["telemetry"]["nested_spec"]["dimensions"]["width"] == 80.0
    assert result["telemetry"]["raw"] == "ok"


def test_mock_resolve_spec_merges_parent_dimensions() -> None:
    parent = derive_legacy_spec("base bracket 80x50x6", "part", "3d_solid")

    result = _mock_worker("resolve_spec", {
        "parent_spec": parent.model_dump(),
        "message": "make it 120 width",
        "mode": "part",
        "output_type": "3d_solid",
    })

    assert result["spec"]["dimensions"]["width"] == 120.0
    assert result["spec"]["dimensions"]["height"] == 50.0
    assert result["spec"]["dimensions"]["thickness"] == 6.0
    assert {"op": "set", "path": "/dimensions/width", "value": 120.0} in result["spec_delta"]


def test_mock_resolve_spec_carries_richer_prompt_architecture() -> None:
    result = _mock_worker("resolve_spec", {
        "parent_spec": None,
        "message": "Industrial wall bracket with 4 holes for M8 bolts, 0.2 mm clearance, and symmetric ribs",
        "mode": "part",
        "output_type": "3d_solid",
    })

    spec = result["spec"]
    assert spec["semantic_part"]["category"] == "support_bracket"
    assert spec["family_hint"]["name"] == "support_bracket"
    assert any(feature["feature_type"] == "mounting_holes" for feature in spec["geometry"]["features"])
    assert any(item["kind"] == "clearance" for item in spec["constraints"])
    assert "industrial" in spec["style"]["keywords"]
