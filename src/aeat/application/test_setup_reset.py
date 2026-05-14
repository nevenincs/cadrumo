"""Per-scope tests for reset behavior exposed through ``aeat config``."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def _isolate_workflow(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from aeat.adapters.persistence.storage.sql import dispose_engine

    dispose_engine()
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'reset.db').as_posix()}")


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
    from .profile._actions import set_active_profile, set_profile_values
    from .profile._repository import profile_bucket_repository
    from .setup_reset import SetupResetReport, SetupResetScope, reset_setup
    from .workflow._models import AuthState
    from .workflow._persistence import workflow_state_repository

    _isolate_workflow(monkeypatch, tmp_path)
    repository = workflow_state_repository()
    repository.update(
        lambda current: set_profile_values(
            set_active_profile(current, "kent"),
            "kent",
            {"tax.id": "00000000T", "activity": "design"},
        )
    )
    repository.update(lambda current: current.model_copy(update={"auth": AuthState(provider="clave_movil")}))

    report = reset_setup(SetupResetScope.PROFILE, confirmed=True)
    assert isinstance(report, SetupResetReport)
    assert report.scope is SetupResetScope.PROFILE
    assert "kent" in report.removed_profile_names
    assert report.removed_auth_session is False

    state_after = workflow_state_repository().load()
    assert state_after.profiles == {}
    assert state_after.active_profile is None
    assert state_after.auth.provider == "clave_movil"
    assert profile_bucket_repository().load("kent") is None


def test_reset_auth_only_clears_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """AUTH scope clears the session but leaves profile entries intact."""
    from .profile._actions import set_active_profile, set_profile_values
    from .profile._repository import profile_bucket_repository
    from .setup_reset import SetupResetScope, reset_setup
    from .workflow._models import AuthState
    from .workflow._persistence import workflow_state_repository

    _isolate_workflow(monkeypatch, tmp_path)
    repository = workflow_state_repository()
    repository.update(
        lambda current: set_profile_values(
            set_active_profile(current, "kent"),
            "kent",
            {"tax.id": "00000000T", "activity": "design"},
        )
    )
    repository.update(lambda current: current.model_copy(update={"auth": AuthState(provider="clave_movil")}))

    report = reset_setup(SetupResetScope.AUTH, confirmed=True)
    assert report.scope is SetupResetScope.AUTH
    assert report.removed_auth_session is True
    assert report.removed_profile_names == ()

    state_after = workflow_state_repository().load()
    assert state_after.auth.provider is None
    assert "kent" in state_after.profiles
    assert profile_bucket_repository().load("kent") is not None


def test_reset_profile_deletes_bucket_id_when_profile_key_differs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """PROFILE scope removes the stored bucket id, not just the profile-map key."""
    from .profile._models import ProfileRecord
    from .profile._repository import profile_bucket_repository
    from .setup_reset import SetupResetScope, reset_setup
    from .workflow._models import WorkflowState
    from .workflow._persistence import workflow_state_repository

    _isolate_workflow(monkeypatch, tmp_path)
    profile_bucket_repository().save(ProfileRecord(name="actual-bucket", values={"tax.id": "00000000T"}))
    workflow_state_repository().save(
        WorkflowState.model_validate(
            {
                "active_profile": "alias",
                "profiles": {"alias": {"bucket_id": "actual-bucket"}},
            }
        )
    )

    report = reset_setup(SetupResetScope.PROFILE, confirmed=True)

    assert "alias" in report.removed_profile_names
    assert profile_bucket_repository().load("actual-bucket") is None


def test_reset_data_invokes_quarantine_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """DATA scope returns a quarantine count; profile + auth untouched."""
    from .profile._actions import set_active_profile, set_profile_values
    from .profile._repository import profile_bucket_repository
    from .setup_reset import SetupResetScope, reset_setup
    from .workflow._persistence import workflow_state_repository

    _isolate_workflow(monkeypatch, tmp_path)
    repository = workflow_state_repository()
    repository.update(
        lambda current: set_profile_values(
            set_active_profile(current, "kent"),
            "kent",
            {"tax.id": "00000000T"},
        )
    )

    report = reset_setup(SetupResetScope.DATA, confirmed=True)
    assert report.scope is SetupResetScope.DATA
    assert report.removed_profile_names == ()
    assert report.removed_auth_session is False
    # No unreadable rows in a fresh temp DB -> quarantine count is 0.
    assert report.quarantined_namespace_count == 0

    state_after = workflow_state_repository().load()
    assert "kent" in state_after.profiles
    assert profile_bucket_repository().load("kent") is not None


def test_reset_all_combines_all_scopes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """ALL scope clears profile + auth + invokes quarantine."""
    from .profile._actions import set_active_profile, set_profile_values
    from .profile._repository import profile_bucket_repository
    from .setup_reset import SetupResetScope, reset_setup
    from .workflow._models import AuthState
    from .workflow._persistence import workflow_state_repository

    _isolate_workflow(monkeypatch, tmp_path)
    repository = workflow_state_repository()
    repository.update(
        lambda current: set_profile_values(
            set_active_profile(current, "kent"),
            "kent",
            {"tax.id": "00000000T", "activity": "design"},
        )
    )
    repository.update(lambda current: current.model_copy(update={"auth": AuthState(provider="clave_movil")}))

    report = reset_setup(SetupResetScope.ALL, confirmed=True)
    assert report.scope is SetupResetScope.ALL
    assert "kent" in report.removed_profile_names
    assert report.removed_auth_session is True

    state_after = workflow_state_repository().load()
    assert state_after.profiles == {}
    assert state_after.auth.provider is None
    assert profile_bucket_repository().load("kent") is None
