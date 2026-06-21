from __future__ import annotations

from fastapi.testclient import TestClient

from app import main
from app.repository import InMemoryRepo


def setup_function() -> None:
    main.repo = InMemoryRepo()


def create_session(client: TestClient) -> str:
    response = client.post("/v1/auth/guest", json={})
    assert response.status_code == 200
    return response.json()["session_id"]


def create_project(client: TestClient, session_id: str) -> str:
    response = client.post(
        "/v1/projects",
        headers={"x-session-id": session_id},
        json={"title": "Private project", "mode": "part", "output_type": "3d_solid"},
    )
    assert response.status_code == 200
    return response.json()["id"]


def test_project_access_is_scoped_to_session() -> None:
    with TestClient(main.app) as client:
        owner = create_session(client)
        attacker = create_session(client)
        project_id = create_project(client, owner)
        owner_response = client.get(f"/v1/projects/{project_id}", headers={"x-session-id": owner})
        assert "owner_session_id" not in owner_response.json()["project"]
        assert owner not in owner_response.text
        response = client.get(f"/v1/projects/{project_id}", headers={"x-session-id": attacker})
        assert response.status_code == 403


def test_state_change_rejects_untrusted_browser_origin() -> None:
    with TestClient(main.app) as client:
        response = client.post(
            "/v1/auth/guest", headers={"origin": "https://attacker.example"}, json={},
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
        first = client.post(f"/v1/projects/{project_id}/generations", headers={"x-session-id": session}, json=payload)
        second = client.post(f"/v1/projects/{project_id}/generations", headers={"x-session-id": session}, json=payload)
        assert first.status_code == 202
        assert second.status_code == 202
        assert first.json()["id"] == second.json()["id"]
