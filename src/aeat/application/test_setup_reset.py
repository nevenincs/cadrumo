"""Per-scope tests for reset behavior exposed through ``aeat config``."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@contextmanager
def _isolated_workflow(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Isolate the workflow store and bind an active bucket session.

    The column-level encrypt path resolves its DEK through the active
    :class:`BucketSession`; ``EphemeralMasterKeyProvider`` opens and
    activates one for the duration of the block.
    """

    from aeat.adapters.persistence.storage import EphemeralMasterKeyProvider
    from aeat.adapters.persistence.storage.sql import dispose_engine

    dispose_engine()
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'reset.db').as_posix()}")
    with EphemeralMasterKeyProvider():
        try:
            yield
        finally:
            dispose_engine()


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


def _profile_exists(profile_id: str, *, bucket_id: str | None = None) -> bool:
    from .user_profile import UserProfileLifecycleRepository

    return UserProfileLifecycleRepository(bucket_id=bucket_id or profile_id).exists(profile_id)


def _registered_profile_names() -> tuple[str, ...]:
    from .workflow._profile_bucket_scan import list_profile_buckets

    return tuple(sorted(list_profile_buckets()))


def test_reset_setup_refuses_without_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The function must raise SetupResetUnconfirmedError when confirmed=False."""
    from .setup_reset import SetupResetScope, SetupResetUnconfirmedError, reset_setup

    with (
        _isolated_workflow(monkeypatch, tmp_path),
        pytest.raises(SetupResetUnconfirmedError, match=r"config reset|confirmed must be True"),
    ):
        reset_setup(SetupResetScope.ALL, confirmed=False)


def test_reset_profile_only_clears_active_profile_record(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """PROFILE scope removes all profile entries but leaves auth state in place."""
    from .setup_reset import SetupResetReport, SetupResetScope, reset_setup
    from .workflow._models import AuthState
    from .workflow._persistence import workflow_state_repository

    with _isolated_workflow(monkeypatch, tmp_path):
        repository = workflow_state_repository()
        _register_profile("operator", overrides={"identity.name": "Design Operator"})
        repository.update(lambda current: current.model_copy(update={"auth": AuthState(provider="clave_movil")}))

        report = reset_setup(SetupResetScope.PROFILE, confirmed=True)
        assert isinstance(report, SetupResetReport)
        assert report.scope is SetupResetScope.PROFILE
        assert "operator" in report.removed_profile_names
        assert report.removed_auth_session is False

        state_after = workflow_state_repository().load()
        assert _registered_profile_names() == ()
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

    with _isolated_workflow(monkeypatch, tmp_path):
        repository = workflow_state_repository()
        _register_profile("operator", overrides={"identity.name": "Design Operator"})
        repository.update(lambda current: current.model_copy(update={"auth": AuthState(provider="clave_movil")}))

        report = reset_setup(SetupResetScope.AUTH, confirmed=True)
        assert report.scope is SetupResetScope.AUTH
        assert report.removed_auth_session is True
        assert report.removed_profile_names == ()

        state_after = workflow_state_repository().load()
        assert state_after.auth.provider is None
        assert "operator" in _registered_profile_names()
        assert _profile_exists("operator")


def test_reset_profile_deletes_registered_bucket_record(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """PROFILE scope deletes the persisted bucket record, not just a state key."""
    from .setup_reset import SetupResetScope, reset_setup

    with _isolated_workflow(monkeypatch, tmp_path):
        _register_profile("operator")
        assert _profile_exists("operator")

        report = reset_setup(SetupResetScope.PROFILE, confirmed=True)

        assert "operator" in report.removed_profile_names
        assert not _profile_exists("operator")
        assert _registered_profile_names() == ()


def test_reset_data_invokes_quarantine_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """DATA scope returns a quarantine count; profile + auth untouched."""
    from .setup_reset import SetupResetScope, reset_setup

    with _isolated_workflow(monkeypatch, tmp_path):
        _register_profile("operator")

        report = reset_setup(SetupResetScope.DATA, confirmed=True)
        assert report.scope is SetupResetScope.DATA
        assert report.removed_profile_names == ()
        assert report.removed_auth_session is False
        # No unreadable rows in a fresh temp DB -> quarantine count is 0.
        assert report.quarantined_namespace_count == 0

        assert "operator" in _registered_profile_names()
        assert _profile_exists("operator")


def test_reset_all_combines_all_scopes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """ALL scope clears profile + auth + invokes quarantine."""
    from .setup_reset import SetupResetScope, reset_setup
    from .workflow._models import AuthState
    from .workflow._persistence import workflow_state_repository

    with _isolated_workflow(monkeypatch, tmp_path):
        repository = workflow_state_repository()
        _register_profile("operator", overrides={"identity.name": "Design Operator"})
        repository.update(lambda current: current.model_copy(update={"auth": AuthState(provider="clave_movil")}))

        report = reset_setup(SetupResetScope.ALL, confirmed=True)
        assert report.scope is SetupResetScope.ALL
        assert "operator" in report.removed_profile_names
        assert report.removed_auth_session is True

        state_after = workflow_state_repository().load()
        assert _registered_profile_names() == ()
        assert state_after.auth.provider is None
        assert not _profile_exists("operator")
