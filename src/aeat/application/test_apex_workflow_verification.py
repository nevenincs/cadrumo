"""Real-behavior verification for the apex CLI workflow contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from aeat.adapters.persistence.storage.sql import dispose_engine
from aeat.application.auth import clear_operator_auth, configure_operator_auth
from aeat.application.operator_surface import require_accepted_root, retired_surface_suggestion
from aeat.application.operator_surface._errors import OperatorSurfaceContractError
from aeat.application.user_profile._testing import register_minimal_profile
from aeat.application.workflow import workflow_state_repository

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_workflow_backend(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    dispose_engine()
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
    try:
        yield
    finally:
        dispose_engine()


def test_root_contract_service_rejects_retired_surfaces_with_canonical_suggestions() -> None:
    assert require_accepted_root("config").name.value == "config"
    assert require_accepted_root("app").name.value == "app"

    for retired, suggestion in {
        "setup": "aeat config profile create NAME",
        "archive": "aeat config bucket",
        "invoice": "aeat app ledger",
        "declaration": "aeat app modelo",
        "topic": "aeat app registry citations",
    }.items():
        contract = retired_surface_suggestion(retired)
        assert contract is not None
        assert contract.suggestion == suggestion
        with pytest.raises(OperatorSurfaceContractError, match=r"operator|surface|contract") as exc_info:
            require_accepted_root(retired)
        assert exc_info.value.suggestion == suggestion


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
        ("auth.provider.cleared", "operator", "certificate")
    )
