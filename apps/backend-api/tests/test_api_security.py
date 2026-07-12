from __future__ import annotations

from fastapi.testclient import TestClient

from app import main
from app.config import settings
from app.repository import InMemoryRepo


def setup_function() -> None:
    main.repo = InMemoryRepo()


def api_headers(**extra: str) -> dict[str, str]:
    headers = dict(extra)
    if settings.api_shared_secret:
        headers["x-api-key"] = settings.api_shared_secret
    return headers


def create_session(client: TestClient) -> str:
    response = client.post("/v1/auth/guest", headers=api_headers(), json={})
    assert response.status_code == 200
    return response.json()["session_id"]


def create_project(client: TestClient, session_id: str) -> str:
    response = client.post(
        "/v1/projects",
        headers=api_headers(**{"x-session-id": session_id}),
        json={"title": "Private project", "mode": "part", "output_type": "3d_solid"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def override_settings(**updates: int):
    previous = {key: getattr(settings, key) for key in updates}
    for key, value in updates.items():
        object.__setattr__(settings, key, value)
    return previous


def restore_settings(previous: dict[str, int]) -> None:
    for key, value in previous.items():
        object.__setattr__(settings, key, value)


def test_project_access_is_scoped_to_session() -> None:
    with TestClient(main.app) as client:
        owner = create_session(client)
        attacker = create_session(client)
        project_id = create_project(client, owner)
        owner_response = client.get(f"/v1/projects/{project_id}", headers=api_headers(**{"x-session-id": owner}))
        assert "owner_session_id" not in owner_response.json()["project"]
        assert owner not in owner_response.text
        response = client.get(f"/v1/projects/{project_id}", headers=api_headers(**{"x-session-id": attacker}))
        assert response.status_code == 403


def test_state_change_rejects_untrusted_browser_origin() -> None:
    with TestClient(main.app) as client:
        response = client.post(
            "/v1/auth/guest", headers=api_headers(origin="https://attacker.example"), json={},
        )
        assert response.status_code == 403


def test_generation_uses_explicit_parent_and_is_idempotent() -> None:
    with TestClient(main.app) as client:
        session = create_session(client)
        project_id = create_project(client, session)
        payload = {
            "message": "A bracket 80 width and 6 thickness",
            "parent_version_id": None,
            "attachment_ids": [],
            "profile": "balanced",
            "idempotency_key": "same-request-key",
        }
        headers = api_headers(**{"x-session-id": session})
        first = client.post(f"/v1/projects/{project_id}/generations", headers=headers, json=payload)
        second = client.post(f"/v1/projects/{project_id}/generations", headers=headers, json=payload)
        assert first.status_code == 202
        assert second.status_code == 202
        assert first.json()["id"] == second.json()["id"]


def test_generation_rejects_message_beyond_profile_limit() -> None:
    with TestClient(main.app) as client:
        session = create_session(client)
        project_id = create_project(client, session)
        payload = {
            "message": "x" * 1201,
            "parent_version_id": None,
            "attachment_ids": [],
            "profile": "balanced",
            "idempotency_key": "too-long-balanced",
        }
        headers = api_headers(**{"x-session-id": session})
        response = client.post(f"/v1/projects/{project_id}/generations", headers=headers, json=payload)
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["profile"] == "balanced"
        assert detail["max_prompt_chars"] == 1200


def test_legacy_generate_rejects_prompt_beyond_profile_limit() -> None:
    with TestClient(main.app) as client:
        session = create_session(client)
        project_id = create_project(client, session)
        headers = api_headers(**{"x-session-id": session})
        response = client.post(
            f"/v1/projects/{project_id}/generate",
            headers=headers,
            json={"prompt": "x" * 701, "profile": "fast"},
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["profile"] == "fast"
        assert detail["max_prompt_chars"] == 700


def test_clarification_rejects_message_beyond_profile_limit() -> None:
    with TestClient(main.app) as client:
        session = create_session(client)
        project_id = create_project(client, session)
        run, _ = main.repo.create_run(
            project_id=project_id,
            session_id=session,
            parent_version_id=None,
            idempotency_key="awaiting-clarification",
            message="x" * 1190,
            attachment_ids=[],
            profile="balanced",
        )
        main.repo.update_run(project_id, run.id, status="awaiting_clarification", clarification_questions=["Need one detail"])
        headers = api_headers(**{"x-session-id": session})
        response = client.post(
            f"/v1/projects/{project_id}/generations/{run.id}/clarification",
            headers=headers,
            json={"answer": "y" * 50},
        )
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["profile"] == "balanced"
        assert detail["max_prompt_chars"] == 1200


def test_guest_project_generation_cap_is_enforced_per_project() -> None:
    previous = override_settings(guest_project_generation_cap=1, guest_runs_per_window=10)
    try:
        with TestClient(main.app) as client:
            session = create_session(client)
            project_id = create_project(client, session)
            headers = api_headers(**{"x-session-id": session})
            first = client.post(
                f"/v1/projects/{project_id}/generations",
                headers=headers,
                json={
                    "message": "Base bracket 80x50x6",
                    "parent_version_id": None,
                    "attachment_ids": [],
                    "profile": "balanced",
                    "idempotency_key": "project-cap-first",
                },
            )
            assert first.status_code == 202

            second = client.post(
                f"/v1/projects/{project_id}/generations",
                headers=headers,
                json={
                    "message": "Refine the same bracket with 4 holes",
                    "parent_version_id": None,
                    "attachment_ids": [],
                    "profile": "balanced",
                    "idempotency_key": "project-cap-second",
                },
            )
            assert second.status_code == 429
            detail = second.json()["detail"]
            assert detail["limit_type"] == "project_generation_cap"
            assert detail["project_generation_cap"] == 1
    finally:
        restore_settings(previous)


def test_guest_project_token_cap_blocks_additional_runs() -> None:
    previous = override_settings(
        guest_project_token_cap=1000,
        vision_summary_max_tokens=220,
        guest_runs_per_window=10,
    )
    try:
        with TestClient(main.app) as client:
            session = create_session(client)
            project_id = create_project(client, session)
            run, _ = main.repo.create_run(
                project_id=project_id,
                session_id=session,
                parent_version_id=None,
                idempotency_key="token-cap-existing-run",
                message="Initial bracket",
                attachment_ids=[],
                profile="balanced",
            )
            main.repo.update_run(
                project_id,
                run.id,
                status="completed",
                telemetry={"spec_usage": {"total_tokens": 650}, "cad_usage": {"total_tokens": 500}},
            )

            response = client.post(
                f"/v1/projects/{project_id}/generations",
                headers=api_headers(**{"x-session-id": session}),
                json={
                    "message": "Make it a little taller",
                    "parent_version_id": None,
                    "attachment_ids": [],
                    "profile": "balanced",
                    "idempotency_key": "token-cap-next-run",
                },
            )
            assert response.status_code == 429
            detail = response.json()["detail"]
            assert detail["limit_type"] == "project_token_cap"
            assert detail["project_token_cap"] == 1000
            assert detail["used_tokens"] == 1150
    finally:
        restore_settings(previous)
