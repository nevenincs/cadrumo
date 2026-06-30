"""Per-scope tests for ``aeat config reset``."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "11111111-1111-4111-8111-111111111111"
_PROFILE_LABEL = "operator"


@contextmanager
def _isolated_workflow(tmp_path: Path) -> Iterator[None]:
    """Isolate workflow state behind a real active profile custody span."""

    from ...tests.secure_sql import isolated_profile_storage_root
    from ..user_profile._orchestration import profile_create_storage_span

    with (
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_PROFILE_ID),
    ):
        yield


def _profile_facts(overrides: Mapping[str, object] | None = None):
    from ...domain.user_profile import UserProfileFact

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


def _register_profile(label: str, *, overrides: Mapping[str, object] | None = None) -> None:
    from ..user_profile._orchestration import register_active_profile
    from ..workflow._persistence import workflow_state_repository

    workflow_state_repository().update(
        lambda current: register_active_profile(
            current,
            profile_id=_PROFILE_ID,
            display_name=label,
            facts=_profile_facts(overrides),
        ),
    )


def _profile_exists(profile_id: str, *, bucket_id: str | None = None) -> bool:
    from ..user_profile import UserProfileLifecycleRepository

    return UserProfileLifecycleRepository(bucket_id=bucket_id or profile_id).exists(profile_id)


def _registered_profile_names() -> tuple[str, ...]:
    from ..workflow._profile_bucket_scan import list_profile_buckets

    return tuple(sorted(pointer.label for pointer in list_profile_buckets().values()))


def test_reset_config_refuses_without_confirmation(
    tmp_path: Path,
) -> None:
    """The function must raise ConfigResetUnconfirmedError when confirmed=False."""
    from ..config_reset import ConfigResetScope, ConfigResetUnconfirmedError, reset_config

    with (
        _isolated_workflow(tmp_path),
        pytest.raises(ConfigResetUnconfirmedError) as excinfo,
    ):
        reset_config(ConfigResetScope.ALL, confirmed=False)
    from ...core.errors import build_error_envelope, resolve_error_message

    rendered = resolve_error_message(excinfo.value)
    assert excinfo.value.translated_message == "errors.refused.refused_config_reset_unconfirmed"
    assert excinfo.value.context == {"scope": "ALL"}
    assert rendered != excinfo.value.translated_message
    assert "refused_config_reset_unconfirmed" not in rendered
    assert "config reset refused" not in rendered.lower()

    envelope = build_error_envelope(excinfo.value, trace_id=None)
    assert envelope.code == "REFUSED_CONFIG_RESET_UNCONFIRMED"
    assert envelope.message == rendered


def test_reset_profile_only_clears_active_profile_record(
    tmp_path: Path,
) -> None:
    """PROFILE scope removes all profile entries but leaves auth state in place."""
    from ..config_reset import ConfigResetReport, ConfigResetScope, reset_config
    from ..workflow._models import AuthState
    from ..workflow._persistence import workflow_state_repository

    with _isolated_workflow(tmp_path):
        repository = workflow_state_repository()
        _register_profile(_PROFILE_LABEL, overrides={"identity.name": "Design Operator"})
        repository.update(lambda current: current.model_copy(update={"auth": AuthState(provider="clave_movil")}))

        report = reset_config(ConfigResetScope.PROFILE, confirmed=True)
        assert isinstance(report, ConfigResetReport)
        assert report.scope is ConfigResetScope.PROFILE
        assert _PROFILE_ID in report.removed_profile_ids
        assert report.removed_auth_session is False

        assert _registered_profile_names() == ()
        assert not _profile_exists(_PROFILE_ID)


def test_reset_auth_only_clears_session(
    tmp_path: Path,
) -> None:
    """AUTH scope clears the session but leaves profile entries intact."""
    from ..config_reset import ConfigResetScope, reset_config
    from ..workflow._models import AuthState
    from ..workflow._persistence import workflow_state_repository

    with _isolated_workflow(tmp_path):
        repository = workflow_state_repository()
        _register_profile(_PROFILE_LABEL, overrides={"identity.name": "Design Operator"})
        repository.update(lambda current: current.model_copy(update={"auth": AuthState(provider="clave_movil")}))

        report = reset_config(ConfigResetScope.AUTH, confirmed=True)
        assert report.scope is ConfigResetScope.AUTH
        assert report.removed_auth_session is True
        assert report.removed_profile_ids == ()

        state_after = workflow_state_repository().load()
        assert state_after.auth.provider is None
        assert _PROFILE_LABEL in _registered_profile_names()
        assert _profile_exists(_PROFILE_ID)


def test_reset_profile_deletes_registered_bucket_record(
    tmp_path: Path,
) -> None:
    """PROFILE scope deletes the persisted bucket record, not just a state key."""
    from ..config_reset import ConfigResetScope, reset_config

    with _isolated_workflow(tmp_path):
        _register_profile(_PROFILE_LABEL)
        assert _profile_exists(_PROFILE_ID)

        report = reset_config(ConfigResetScope.PROFILE, confirmed=True)

        assert _PROFILE_ID in report.removed_profile_ids
        assert not _profile_exists(_PROFILE_ID)
        assert _registered_profile_names() == ()


def test_reset_data_invokes_quarantine_pipeline(
    tmp_path: Path,
) -> None:
    """DATA scope returns a quarantine count; profile + auth untouched."""
    from ..config_reset import ConfigResetScope, reset_config

    with _isolated_workflow(tmp_path):
        _register_profile(_PROFILE_LABEL)

        report = reset_config(ConfigResetScope.DATA, confirmed=True)
        assert report.scope is ConfigResetScope.DATA
        assert report.removed_profile_ids == ()
        assert report.removed_auth_session is False
        # No unreadable rows in a fresh temp DB -> quarantine count is 0.
        assert report.quarantined_namespace_count == 0

        assert _PROFILE_LABEL in _registered_profile_names()
        assert _profile_exists(_PROFILE_ID)


def test_reset_all_combines_all_scopes(
    tmp_path: Path,
) -> None:
    """ALL scope clears profile + auth + invokes quarantine."""
    from ..config_reset import ConfigResetScope, reset_config
    from ..workflow._models import AuthState
    from ..workflow._persistence import workflow_state_repository

    with _isolated_workflow(tmp_path):
        repository = workflow_state_repository()
        _register_profile(_PROFILE_LABEL, overrides={"identity.name": "Design Operator"})
        repository.update(lambda current: current.model_copy(update={"auth": AuthState(provider="clave_movil")}))

        report = reset_config(ConfigResetScope.ALL, confirmed=True)
        assert report.scope is ConfigResetScope.ALL
        assert _PROFILE_ID in report.removed_profile_ids
        assert report.removed_auth_session is True

        assert _registered_profile_names() == ()
        assert not _profile_exists(_PROFILE_ID)
