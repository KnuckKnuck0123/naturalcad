from __future__ import annotations

from app.repository import InMemoryRepo, derive_legacy_spec
import pytest


def project_fixture():
    repo = InMemoryRepo()
    session = repo.create_guest_session(5)
    project = repo.create_project(session.session_id, "Test", "part", "3d_solid")
    return repo, session, project


def test_guest_session_is_high_entropy_and_expiring() -> None:
    repo = InMemoryRepo()
    session = repo.create_guest_session(5)
    assert len(session.session_id.removeprefix("guest_")) == 32
    assert session.expires_at > session.created_at


def test_generation_idempotency_and_explicit_parent() -> None:
    repo, session, project = project_fixture()
    run, created = repo.create_run(
        project_id=project.id, session_id=session.session_id, parent_version_id="ver_parent",
        idempotency_key="request-123", message="make it wider", attachment_ids=[], profile="balanced",
    )
    duplicate, duplicate_created = repo.create_run(
        project_id=project.id, session_id=session.session_id, parent_version_id=None,
        idempotency_key="request-123", message="duplicate", attachment_ids=[], profile="quality",
    )
    assert created is True
    assert duplicate_created is False
    assert duplicate.id == run.id
    assert duplicate.parent_version_id == "ver_parent"


def test_versions_are_newest_first_and_branchable() -> None:
    repo, _, project = project_fixture()
    first = repo.create_version(
        project_id=project.id, prompt="base", profile="balanced", model="mock", artifacts={},
        generated_code="", status="completed", error=None, parent_version_id=None, parameters=[],
        spec=derive_legacy_spec("80 width bracket", "part", "3d_solid"),
    )
    branch = repo.create_version(
        project_id=project.id, prompt="branch", profile="balanced", model="mock", artifacts={},
        generated_code="", status="completed", error=None, parent_version_id=first.id, parameters=[],
        spec=derive_legacy_spec("90 width bracket", "part", "3d_solid"),
    )
    versions = repo.list_versions(project.id)
    assert [version.id for version in versions] == [branch.id, first.id]
    assert branch.parent_version_id == first.id


def test_quota_reservation_is_bounded() -> None:
    repo, session, _ = project_fixture()
    assert repo.check_and_consume_quota(session.session_id, max_runs=1, window_seconds=60) == (True, 0)
    assert repo.check_and_consume_quota(session.session_id, max_runs=1, window_seconds=60) == (False, 0)


def test_attachment_reservation_is_bounded_atomically() -> None:
    repo, session, project = project_fixture()
    repo.create_attachment(
        project_id=project.id, session_id=session.session_id, content_type="image/png", size_bytes=10,
        storage_key="one", upload_url=None, max_active=1,
    )
    with pytest.raises(ValueError, match="limit"):
        repo.create_attachment(
            project_id=project.id, session_id=session.session_id, content_type="image/png", size_bytes=10,
            storage_key="two", upload_url=None, max_active=1,
        )
