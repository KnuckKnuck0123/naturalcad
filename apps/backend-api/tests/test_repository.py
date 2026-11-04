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


def test_legacy_spec_extracts_reverse_order_and_triplet_dimensions() -> None:
    spec = derive_legacy_spec("Make a bracket 80 width with 50 height and 80x50x6 overall", "part", "3d_solid")
    assert spec.dimensions["width"] == 80.0
    assert spec.dimensions["height"] == 50.0
    assert spec.dimensions["thickness"] == 6.0


def test_legacy_spec_extracts_labeled_dimensions_with_units() -> None:
    spec = derive_legacy_spec("diameter 12 mm tube adapter with length 40 mm and thickness 3.5", "part", "3d_solid")
    assert spec.dimensions["diameter"] == 12.0
    assert spec.dimensions["length"] == 40.0
    assert spec.dimensions["thickness"] == 3.5


def test_legacy_spec_captures_feature_constraints_and_family_hints() -> None:
    spec = derive_legacy_spec(
        "Make a symmetric wall bracket with 4 holes for M8 bolts and 0.2 mm clearance",
        "part",
        "3d_solid",
    )
    assert spec.semantic_part["category"] == "support_bracket"
    assert spec.semantic_part["symmetry"] == "symmetric"
    assert "wall_mount" in spec.semantic_part["interfaces"]
    assert spec.family_hint["generation_mode"] == "extend"
    assert any(feature["feature_type"] == "mounting_holes" for feature in spec.geometry["features"])
    assert any(item["kind"] == "clearance" and item["value"] == 0.2 for item in spec.constraints)
    assert any("fit-critical" in note.lower() for note in spec.notes)


def test_legacy_spec_flags_missing_fit_critical_dimensions() -> None:
    spec = derive_legacy_spec("tube adapter for a press fit shaft", "part", "3d_solid")
    assert any("interface diameter" in item.lower() for item in spec.uncertainties)
    assert any("tolerance or clearance" in item.lower() for item in spec.uncertainties)
