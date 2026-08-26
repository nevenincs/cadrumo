"""Real-behavior verification for the CLI workflow contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.application.workflow.persistence import workflow_state_repository

from ...adapters.persistence.storage.sql import dispose_engine
from ...tests.profile_capsule import open_test_profile_session
from ...tests.secure_sql import isolated_profile_storage_root
from ...tests.user_profile import register_minimal_profile
from ..auth.operator import configure_operator_auth, logout_operator_auth, reset_operator_auth
from ..operator_surface import require_accepted_root
from ..wizard import compiler as _wizard  # noqa: F401 - registers compiled profile keys

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "11111111-1111-4111-8111-111111111111"
_PROFILE_LABEL = "operator"


@pytest.fixture(autouse=True)
def isolated_workflow_backend(tmp_path: Path):
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        open_test_profile_session(_BUCKET_ID),
    ):
        try:
            yield
        finally:
            dispose_engine()


def test_root_contract_service_accepts_canonical_roots() -> None:
    assert require_accepted_root("config").name.value == "config"
    assert require_accepted_root("app").name.value == "app"


def test_auth_bucket_events_survive_workflow_repository_reload() -> None:
    # Seeded through a detached WorkflowState, never a repository read: the
    # capsule publishes by an atomic no-replace rename onto
    # ``buckets/<profile-id>``, which a workflow-state repository
    # construction would otherwise materialise first and collide with. The
    # repository this test actually mutates is opened only afterward.
    register_minimal_profile(profile_id=_BUCKET_ID, display_name=_PROFILE_LABEL)
    repository = workflow_state_repository()

    configured = configure_operator_auth("certificate")
    repository.update(
        lambda state: state.model_copy(
            update={
                "auth": state.auth.model_copy(
                    update={
                        "authenticated_at": state.updated_at,
                        "subject": "CN=Operator",
                    },
                ),
            },
        ),
    )
    logged_out = logout_operator_auth(provider="certificate")
    reset = reset_operator_auth(provider="certificate")

    reloaded = workflow_state_repository().load()
    events = [(event.action, event.bucket_id, event.object_id) for event in reloaded.bucket_events]

    assert configured.provider == "certificate"
    assert logged_out.cleared_session_state is True
    assert reset.cleared_provider_configuration is True
    assert ("auth.provider.configured", _BUCKET_ID, "certificate") in events
    assert ("auth.session.cleared", _BUCKET_ID, "certificate") in events
    assert ("auth.provider.cleared", _BUCKET_ID, "certificate") in events
    assert events.index(("auth.provider.configured", _BUCKET_ID, "certificate")) < events.index(
        ("auth.session.cleared", _BUCKET_ID, "certificate"),
    )
    assert events.index(("auth.session.cleared", _BUCKET_ID, "certificate")) < events.index(
        ("auth.provider.cleared", _BUCKET_ID, "certificate"),
    )
