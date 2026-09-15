"""Real-storage verification for the workflow event contract used by the CLI."""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.tests._operator_scope_fakes import (
    build_inward_operator_scope_ports_for_active_route,
)
from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.storage.certificate_secret_backend import build_certificate_secret_backend
from cadrumo.adapters.persistence.storage.sql.engine import dispose_engine
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import open_test_profile_session
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.auth.operator import logout_operator_auth, reset_operator_auth
from cadrumo.application.auth.tests.operator_projection_test_support import configure_operator_auth
from cadrumo.application.workflow.persistence import workflow_state_repository

_OPERATOR_SCOPE_PORTS = build_inward_operator_scope_ports_for_active_route()

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

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


def test_auth_bucket_events_survive_workflow_repository_reload() -> None:
    # Seeded through a detached WorkflowState, never a repository read: the
    # capsule publishes by an atomic no-replace rename onto
    # ``buckets/<profile-id>``, which a workflow-state repository
    # construction would otherwise materialise first and collide with. The
    # repository this test actually mutates is opened only afterward.
    register_minimal_profile(profile_id=_BUCKET_ID, display_name=_PROFILE_LABEL)
    repository = workflow_state_repository()

    configured = configure_operator_auth("certificate", operator_scope_ports=_OPERATOR_SCOPE_PORTS)
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
    logged_out = logout_operator_auth(
        provider="certificate",
        certificate_secret_backend_factory=build_certificate_secret_backend,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )
    reset = reset_operator_auth(
        provider="certificate",
        certificate_secret_backend_factory=build_certificate_secret_backend,
        operator_scope_ports=_OPERATOR_SCOPE_PORTS,
    )

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
