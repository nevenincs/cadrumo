"""Per-scope tests for reset behavior exposed through ``aeat config``."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _isolate_workflow(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from aeat.adapters.persistence.storage.sql import dispose_engine

    dispose_engine()
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'reset.db').as_posix()}")


def _profile_facts(overrides: Mapping[str, object] | None = None):
    from aeat.domain.user_profile import UserProfileFact

    values: dict[str, object] = {
        "identity.tax_id": "00000000T",
        "identity.name": "Test Operator",
        "tax_residence.ccaa": "madrid",
        "tax_residence.jurisdiction_scope": "common_regime",
        "iva.regime": "GENERAL",
        "provenance.source": "manual_cli",
    }
    if overrides:
        values.update(overrides)
    return tuple(UserProfileFact.model_validate({"path": path, "value": value}) for path, value in values.items())


def _register_profile(profile_id: str, *, overrides: Mapping[str, object] | None = None) -> None:
    from .user_profile._orchestration import register_active_profile
    from .workflow._persistence import workflow_state_repository

    workflow_state_repository().update(
        lambda current: register_active_profile(
            current,
            profile_id=profile_id,
            display_name=profile_id,
            facts=_profile_facts(overrides),
        )
    )


def _save_profile_in_bucket(*, profile_id: str, bucket_id: str) -> None:
    from aeat.domain.user_profile import UserProfileRecord

    from .user_profile import UserProfileLifecycleRepository

    UserProfileLifecycleRepository(bucket_id=bucket_id).save(
        UserProfileRecord(profile_id=profile_id, display_name=profile_id, facts=_profile_facts())
    )


def _profile_exists(profile_id: str, *, bucket_id: str | None = None) -> bool:
    from .user_profile import UserProfileLifecycleRepository

    return UserProfileLifecycleRepository(bucket_id=bucket_id or profile_id).exists(profile_id)


def test_reset_setup_refuses_without_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The function must raise SetupResetUnconfirmedError when confirmed=False."""
    from .setup_reset import SetupResetScope, SetupResetUnconfirmedError, reset_setup

    _isolate_workflow(monkeypatch, tmp_path)
    with pytest.raises(SetupResetUnconfirmedError, match=r"config reset|confirmed must be True"):
        reset_setup(SetupResetScope.ALL, confirmed=False)


def test_reset_profile_only_clears_active_profile_record(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """PROFILE scope removes all profile entries but leaves auth state in place."""
    from .setup_reset import SetupResetReport, SetupResetScope, reset_setup
    from .workflow._models import AuthState
    from .workflow._persistence import workflow_state_repository

    _isolate_workflow(monkeypatch, tmp_path)
    repository = workflow_state_repository()
    _register_profile("operator", overrides={"identity.name": "Design Operator"})
    repository.update(lambda current: current.model_copy(update={"auth": AuthState(provider="clave_movil")}))

    report = reset_setup(SetupResetScope.PROFILE, confirmed=True)
    assert isinstance(report, SetupResetReport)
    assert report.scope is SetupResetScope.PROFILE
    assert "operator" in report.removed_profile_names
    assert report.removed_auth_session is False

    state_after = workflow_state_repository().load()
    assert state_after.profiles == {}
    assert state_after.active_profile is None
    assert state_after.auth.provider == "clave_movil"
    assert not _profile_exists("operator")


def test_reset_auth_only_clears_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AUTH scope clears the session but leaves profile entries intact."""
    from .setup_reset import SetupResetScope, reset_setup
    from .workflow._models import AuthState
    from .workflow._persistence import workflow_state_repository

    _isolate_workflow(monkeypatch, tmp_path)
    repository = workflow_state_repository()
    _register_profile("operator", overrides={"identity.name": "Design Operator"})
    repository.update(lambda current: current.model_copy(update={"auth": AuthState(provider="clave_movil")}))

    report = reset_setup(SetupResetScope.AUTH, confirmed=True)
    assert report.scope is SetupResetScope.AUTH
    assert report.removed_auth_session is True
    assert report.removed_profile_names == ()

    state_after = workflow_state_repository().load()
    assert state_after.auth.provider is None
    assert "operator" in state_after.profiles
    assert _profile_exists("operator")


def test_reset_profile_deletes_bucket_id_when_profile_key_differs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """PROFILE scope removes the stored bucket id, not just the profile-map key."""
    from .setup_reset import SetupResetScope, reset_setup
    from .workflow._models import WorkflowState
    from .workflow._persistence import workflow_state_repository

    _isolate_workflow(monkeypatch, tmp_path)
    _save_profile_in_bucket(profile_id="alias", bucket_id="actual-bucket")
    workflow_state_repository().save(
        WorkflowState.model_validate(
            {
                "profiles": {"alias": {"bucket_id": "actual-bucket"}},
            }
        )
    )

    report = reset_setup(SetupResetScope.PROFILE, confirmed=True)

    assert "alias" in report.removed_profile_names
    assert not _profile_exists("alias", bucket_id="actual-bucket")


def test_reset_data_invokes_quarantine_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """DATA scope returns a quarantine count; profile + auth untouched."""
    from .setup_reset import SetupResetScope, reset_setup
    from .workflow._persistence import workflow_state_repository

    _isolate_workflow(monkeypatch, tmp_path)
    _register_profile("operator")

    report = reset_setup(SetupResetScope.DATA, confirmed=True)
    assert report.scope is SetupResetScope.DATA
    assert report.removed_profile_names == ()
    assert report.removed_auth_session is False
    # No unreadable rows in a fresh temp DB -> quarantine count is 0.
    assert report.quarantined_namespace_count == 0

    state_after = workflow_state_repository().load()
    assert "operator" in state_after.profiles
    assert _profile_exists("operator")


def test_reset_all_combines_all_scopes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """ALL scope clears profile + auth + invokes quarantine."""
    from .setup_reset import SetupResetScope, reset_setup
    from .workflow._models import AuthState
    from .workflow._persistence import workflow_state_repository

    _isolate_workflow(monkeypatch, tmp_path)
    repository = workflow_state_repository()
    _register_profile("operator", overrides={"identity.name": "Design Operator"})
    repository.update(lambda current: current.model_copy(update={"auth": AuthState(provider="clave_movil")}))

    report = reset_setup(SetupResetScope.ALL, confirmed=True)
    assert report.scope is SetupResetScope.ALL
    assert "operator" in report.removed_profile_names
    assert report.removed_auth_session is True

    state_after = workflow_state_repository().load()
    assert state_after.profiles == {}
    assert state_after.auth.provider is None
    assert not _profile_exists("operator")
