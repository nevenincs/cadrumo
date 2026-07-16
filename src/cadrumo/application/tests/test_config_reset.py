"""Per-scope tests for ``aeat config reset``."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

import pytest
from pydantic import SecretStr

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "11111111-1111-4111-8111-111111111111"
_PROFILE_B_ID = "22222222-2222-4222-8222-222222222222"
_PROFILE_LABEL = "operator"


@contextmanager
def _isolated_workflow(tmp_path: Path) -> Iterator[None]:
    """Isolate workflow state behind a real active profile custody span."""

    from ...tests.secure_sql import isolated_profile_storage_root
    from ..user_profile import profile_create_storage_span

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


def _register_profile(
    label: str,
    *,
    profile_id: str = _PROFILE_ID,
    overrides: Mapping[str, object] | None = None,
) -> None:
    from ..user_profile import register_active_profile
    from ..workflow import workflow_state_repository

    workflow_state_repository().update(
        lambda current: register_active_profile(
            current,
            profile_id=profile_id,
            display_name=label,
            facts=_profile_facts(overrides),
        ),
    )


def _profile_exists(profile_id: str, *, bucket_id: str | None = None) -> bool:
    from ..user_profile import UserProfileLifecycleRepository

    return UserProfileLifecycleRepository(bucket_id=bucket_id or profile_id).exists(profile_id)


def _registered_profile_names() -> tuple[str, ...]:
    from ..workflow import list_profile_buckets

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
    """PROFILE scope removes all profile entries."""
    from ..config_reset import ConfigResetReport, ConfigResetScope, reset_config

    with _isolated_workflow(tmp_path):
        _register_profile(_PROFILE_LABEL, overrides={"identity.name": "Design Operator"})

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
    """AUTH scope uses canonical auth reset for sessions, sources, and secrets."""
    from ...adapters.outbound.aeat.auth import _session_store
    from ..auth import AuthProviderKind, configure_operator_auth
    from ..auth._certificate_sources_operator import (
        register_operator_certificate_source,
        resolve_certificate_source_secret,
        set_operator_certificate_source_secret,
    )
    from ..auth._sessions import storage_state_paths
    from ..config_reset import ConfigResetScope, reset_config
    from ..wizard import WIZARD_FLOWS
    from ..workflow import workflow_state_repository

    with _isolated_workflow(tmp_path):
        assert WIZARD_FLOWS
        _register_profile(_PROFILE_LABEL, overrides={"identity.name": "Design Operator"})
        certificate_path = tmp_path / "operator.p12"
        certificate_path.write_bytes(b"test certificate")
        configure_operator_auth("certificate", certificate_path=certificate_path)
        register_operator_certificate_source(
            name="personal",
            certificate_path=certificate_path,
        )
        set_operator_certificate_source_secret(
            name="personal",
            secret=SecretStr("test-passphrase"),
        )
        session_path = storage_state_paths(AuthProviderKind.CERTIFICATE).storage_state
        _session_store.save(
            session_path,
            storage_state={},
            metadata={"provider_kind": "certificate"},
        )
        state_before = workflow_state_repository().load()
        assert _session_store.exists(session_path)
        assert resolve_certificate_source_secret(name="personal", bucket_id=_PROFILE_ID) is not None

        report = reset_config(ConfigResetScope.AUTH, confirmed=True)
        assert report.scope is ConfigResetScope.AUTH
        assert report.removed_auth_session is True
        assert report.removed_profile_ids == ()

        state_after = workflow_state_repository().load()
        assert state_after.auth.provider is None
        assert state_after.auth.certificate_sources == {}
        assert _session_store.exists(session_path) is False
        assert resolve_certificate_source_secret(name="personal", bucket_id=_PROFILE_ID) is None
        new_events = state_after.bucket_events[len(state_before.bucket_events) :]
        assert ("auth.provider.cleared", "certificate") in [
            (event.action, event.object_id) for event in new_events
        ]
        assert ("auth.session.cleared", "certificate") in [
            (event.action, event.object_id) for event in new_events
        ]
        assert ("auth.certificate_source.removed", "personal") in [
            (event.action, event.object_id) for event in new_events
        ]
        assert _PROFILE_LABEL in _registered_profile_names()
        assert _profile_exists(_PROFILE_ID)


def test_reset_auth_without_active_bucket_refuses_through_canonical_auth_error(
    tmp_path: Path,
) -> None:
    """AUTH scope never falls through to ambient or cold-bootstrap state."""
    from ...tests.secure_sql import isolated_profile_storage_root
    from ..auth import AuthConfigureNoActiveBucketError
    from ..config_reset import ConfigResetScope, reset_config

    with isolated_profile_storage_root(tmp_path=tmp_path):
        with pytest.raises(AuthConfigureNoActiveBucketError):
            reset_config(ConfigResetScope.AUTH, confirmed=True)
        assert _registered_profile_names() == ()


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
    """ALL scope clears target auth custody before deleting every profile."""
    from ...adapters.persistence.storage.bucket import bucket_paths
    from ...core.config import load_settings
    from ..auth import AuthProviderKind, configure_operator_auth
    from ..auth._acquisition_lock import acquire_auth_acquisition_lock, auth_acquisition_lock_path
    from ..config_reset import ConfigResetScope, reset_config
    from ..user_profile import (
        delete_profile_with_lifecycle_span,
        profile_create_storage_span,
        profile_storage_session,
    )
    from ..wizard import WIZARD_FLOWS
    from ..workflow import list_profile_buckets

    with _isolated_workflow(tmp_path):
        assert WIZARD_FLOWS
        _register_profile(_PROFILE_LABEL, overrides={"identity.name": "Design Operator"})
        configure_operator_auth("certificate")
        with profile_create_storage_span(_PROFILE_B_ID):
            _register_profile(
                "second-operator",
                profile_id=_PROFILE_B_ID,
                overrides={
                    "identity.name": "Second Operator",
                    "identity.tax_id": "00000001R",
                },
            )
            configure_operator_auth("clave_permanente")
        delete_profile_with_lifecycle_span(_PROFILE_B_ID)
        assert _PROFILE_B_ID in list_profile_buckets(include_tombstoned=True)
        assert _PROFILE_B_ID not in list_profile_buckets()

        settings = load_settings()
        second_lock_path = auth_acquisition_lock_path(
            settings,
            AuthProviderKind.CLAVE_PERMANENTE,
            bucket_id=_PROFILE_B_ID,
        )
        with (
            profile_storage_session(_PROFILE_B_ID),
            acquire_auth_acquisition_lock(
                settings,
                AuthProviderKind.CLAVE_PERMANENTE,
                ttl_seconds=60,
                operation="test-config-reset-all",
            ),
        ):
            assert second_lock_path.is_file()
            report = reset_config(ConfigResetScope.ALL, confirmed=True)
            assert second_lock_path.exists() is False

        assert report.scope is ConfigResetScope.ALL
        assert _PROFILE_ID in report.removed_profile_ids
        assert _PROFILE_B_ID in report.removed_profile_ids
        assert report.removed_auth_session is True

        assert _registered_profile_names() == ()
        assert bucket_paths(settings.cadrumo_local_storage_root, _PROFILE_ID).bucket_dir.exists() is False
        assert bucket_paths(settings.cadrumo_local_storage_root, _PROFILE_B_ID).bucket_dir.exists() is False


def test_reset_all_refuses_dangling_pointer_without_recreating_target(
    tmp_path: Path,
) -> None:
    """ALL scope leaves a missing pointer target absent for later S62/S65 repair."""
    from ...adapters.persistence.storage import StorageValidationError
    from ...adapters.persistence.storage.bucket import bucket_paths
    from ...core import BucketPointer, pointer_path, write_pointer
    from ...core.config import load_settings
    from ...tests.secure_sql import isolated_profile_storage_root
    from ..config_reset import ConfigResetScope, reset_config

    missing_bucket_id = "33333333-3333-4333-8333-333333333333"
    with isolated_profile_storage_root(tmp_path=tmp_path):
        settings = load_settings()
        write_pointer(
            settings.cadrumo_local_storage_root,
            BucketPointer(bucket_id=missing_bucket_id, schema_version=1),
        )
        pointer_before = pointer_path(settings.cadrumo_local_storage_root).read_bytes()
        missing_bucket = bucket_paths(
            settings.cadrumo_local_storage_root,
            missing_bucket_id,
        ).bucket_dir

        with pytest.raises(StorageValidationError):
            reset_config(ConfigResetScope.ALL, confirmed=True)

        assert missing_bucket.exists() is False
        assert pointer_path(settings.cadrumo_local_storage_root).read_bytes() == pointer_before
