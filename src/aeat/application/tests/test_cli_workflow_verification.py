"""Real-behavior verification for the CLI workflow contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from ...adapters.persistence.storage.sql import dispose_engine
from ...tests.secure_sql import isolated_profile_storage_root
from ..auth import clear_operator_auth, configure_operator_auth
from ..operator_surface import require_accepted_root
from ..user_profile._orchestration import profile_create_storage_span
from ..user_profile._testing import register_minimal_profile
from ..workflow import workflow_state_repository

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(autouse=True)
def _isolated_workflow_backend(tmp_path: Path):  # pyright: ignore[reportUnusedFunction]
    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("operator"),
    ):
        try:
            yield
        finally:
            dispose_engine()


def test_root_contract_service_accepts_canonical_roots() -> None:
    assert require_accepted_root("config").name.value == "config"
    assert require_accepted_root("app").name.value == "app"


def test_auth_bucket_events_survive_workflow_repository_reload() -> None:
    repository = workflow_state_repository()
    repository.update(lambda state: register_minimal_profile(state, profile_id="operator"))

    configured = configure_operator_auth("certificate")
    cleared = clear_operator_auth(provider="certificate")

    reloaded = workflow_state_repository().load()
    events = [(event.action, event.bucket_id, event.object_id) for event in reloaded.bucket_events]

    assert configured.provider == "certificate"
    assert cleared.cleared_workflow_state is True
    assert ("auth.provider.configured", "operator", "certificate") in events
    assert ("auth.provider.cleared", "operator", "certificate") in events
    assert events.index(("auth.provider.configured", "operator", "certificate")) < events.index(
        ("auth.provider.cleared", "operator", "certificate"),
    )
