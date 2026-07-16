"""Real-storage coverage for target-scoped operator auth logout and reset."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import SecretStr

from ....adapters.outbound.aeat.auth import _session_store
from ....adapters.persistence.storage import has_active_bucket_session
from ....adapters.persistence.storage.master_key import current_active_bucket_session
from ....application.wizard import WIZARD_FLOWS
from ....core.config import override_settings
from ....core.errors import ERROR_REGISTRY, build_error_envelope, resolve_error_message
from ....domain.contribuyente import required_profile_keys
from ....tests.secure_sql import isolated_profile_storage_root
from ...user_profile import (
    profile_create_storage_span,
    profile_storage_session,
    register_minimal_profile,
)
from ...workflow import workflow_state_repository
from .. import AuthProviderKind
from .._acquisition_lock import acquire_auth_acquisition_lock, auth_acquisition_lock_path
from .._certificate_sources_operator import (
    register_operator_certificate_source,
    resolve_certificate_source_secret,
    set_operator_certificate_source_secret,
)
from .._operator import configure_operator_auth, logout_operator_auth, reset_operator_auth
from .._operator_results import AuthOperationScopeConflictError, AuthProviderNotConfiguredError
from .._sessions import storage_state_paths

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_A = "11111111-1111-4111-8111-111111111111"
_PROFILE_B = "22222222-2222-4222-8222-222222222222"


def _create_profile(profile_id: str, *, provider: str | None = None) -> None:
    assert WIZARD_FLOWS
    assert required_profile_keys()
    with profile_create_storage_span(profile_id):
        workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id=profile_id))
        if provider is not None:
            configure_operator_auth(provider)


def test_logout_reopens_pointer_profile_and_is_idempotent(tmp_path: Path) -> None:
    """Logout clears readiness, preserves configuration, and does not rewrite a second time."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile(_PROFILE_A, provider="certificate")
        with profile_storage_session(_PROFILE_A):
            repository = workflow_state_repository()
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

        assert has_active_bucket_session() is False
        first = logout_operator_auth(provider="certificate")
        assert has_active_bucket_session() is False

        with profile_storage_session(_PROFILE_A):
            after_first = workflow_state_repository().load()
        second = logout_operator_auth(provider="certificate")
        with profile_storage_session(_PROFILE_A):
            after_second = workflow_state_repository().load()

        assert first.cleared_session_state is True
        assert first.removed_sessions == 0
        assert second.cleared_session_state is False
        assert second.removed_sessions == 0
        assert after_first.auth.provider == "certificate"
        assert after_first.auth.authenticated_at is None
        assert after_first.auth.subject is None
        assert after_second == after_first


def test_logout_and_reset_require_unambiguous_scope(tmp_path: Path) -> None:
    """An omitted provider needs configured state; provider and all are mutually exclusive."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile(_PROFILE_A)

        with pytest.raises(AuthProviderNotConfiguredError):
            logout_operator_auth()
        with pytest.raises(AuthProviderNotConfiguredError):
            reset_operator_auth()
        with pytest.raises(AuthOperationScopeConflictError):
            logout_operator_auth(provider="certificate", all_providers=True)
        with pytest.raises(AuthOperationScopeConflictError):
            reset_operator_auth(provider="certificate", all_providers=True)


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (
            AuthOperationScopeConflictError(
                translated_message="application.auth.operator.errors.scope_conflict",
            ),
            "REFUSED_AUTH_OPERATION_SCOPE_CONFLICT",
        ),
        (
            AuthProviderNotConfiguredError(
                translated_message="application.auth.operator.errors.provider_not_configured",
            ),
            "REFUSED_AUTH_PROVIDER_NOT_CONFIGURED",
        ),
    ],
)
def test_auth_scope_errors_have_canonical_registry_envelopes(error: Exception, code: str) -> None:
    """Auth scope refusals are first-class central registry entries."""
    assert code in ERROR_REGISTRY
    envelope = build_error_envelope(error)
    assert envelope.code == code
    assert envelope.message == resolve_error_message(error)


def test_reserved_provider_reset_is_an_idempotent_noop(tmp_path: Path) -> None:
    """Known reserved providers are valid targets and never clear another configured provider."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile(_PROFILE_A, provider="certificate")

        first = reset_operator_auth(provider="clave_pin")
        second = reset_operator_auth(provider="clave_pin")
        with profile_storage_session(_PROFILE_A):
            state = workflow_state_repository().load()

        assert first.cleared_provider_configuration is False
        assert second == first
        assert state.auth.provider == "certificate"


def test_logout_deletes_real_clave_permanente_session(tmp_path: Path) -> None:
    """Cl@ve Permanente uses its production storage stem and is deleted by logout."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile(_PROFILE_A, provider="clave_permanente")
        with profile_storage_session(_PROFILE_A):
            path = storage_state_paths(AuthProviderKind.CLAVE_PERMANENTE).storage_state
            _session_store.save(path, storage_state={}, metadata={"provider_kind": "clave_permanente"})
            assert _session_store.exists(path)

        result = logout_operator_auth(provider="clave_permanente")

        with profile_storage_session(_PROFILE_A):
            assert _session_store.exists(path) is False
        assert result.removed_sessions == 1


def test_logout_all_emits_events_only_for_affected_providers(tmp_path: Path) -> None:
    """An all-provider sweep never claims unrelated providers had session artefacts."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile(_PROFILE_A, provider="certificate")
        with profile_storage_session(_PROFILE_A):
            repository = workflow_state_repository()
            before = repository.load()
            path = storage_state_paths(AuthProviderKind.CLAVE_PERMANENTE).storage_state
            _session_store.save(path, storage_state={}, metadata={"provider_kind": "clave_permanente"})

        result = logout_operator_auth(all_providers=True)
        with profile_storage_session(_PROFILE_A):
            after = workflow_state_repository().load()

        new_events = after.bucket_events[len(before.bucket_events) :]
        assert result.removed_sessions == 1
        assert [(event.action, event.object_id) for event in new_events] == [
            ("auth.session.cleared", "clave_permanente"),
        ]


def test_reset_removes_certificate_registry_and_secure_secret(tmp_path: Path) -> None:
    """Certificate reset removes registrations and canonical secure-storage secrets."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        cert_path = tmp_path / "operator.p12"
        cert_path.write_bytes(b"placeholder")
        _create_profile(_PROFILE_A, provider="certificate")
        with profile_storage_session(_PROFILE_A):
            register_operator_certificate_source(name="personal", certificate_path=cert_path)
            set_operator_certificate_source_secret(name="personal", secret=SecretStr("do-not-leak"))
            assert resolve_certificate_source_secret(name="personal", bucket_id=_PROFILE_A) is not None

        first = reset_operator_auth(provider="certificate")
        second = reset_operator_auth(provider="certificate")
        with profile_storage_session(_PROFILE_A):
            state = workflow_state_repository().load()
            secret = resolve_certificate_source_secret(name="personal", bucket_id=_PROFILE_A)

        assert first.cleared_provider_configuration is True
        assert first.removed_certificate_sources == 1
        assert first.removed_certificate_secrets == 1
        assert second.cleared_provider_configuration is False
        assert second.removed_certificate_sources == 0
        assert second.removed_certificate_secrets == 0
        assert state.auth.provider is None
        assert state.auth.certificate_sources == {}
        assert secret is None


def test_certificate_reset_clears_path_without_removing_other_provider(tmp_path: Path) -> None:
    """Certificate configuration is removed even when another provider is active."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile(_PROFILE_A, provider="clave_movil")
        with profile_storage_session(_PROFILE_A):
            repository = workflow_state_repository()
            repository.update(
                lambda state: state.model_copy(
                    update={
                        "auth": state.auth.model_copy(
                            update={"certificate_path": str(tmp_path / "detached.p12")},
                        ),
                    },
                ),
            )

        result = reset_operator_auth(provider="certificate")
        with profile_storage_session(_PROFILE_A):
            state = workflow_state_repository().load()

        assert result.cleared_provider_configuration is True
        assert state.auth.provider == "clave_movil"
        assert state.auth.certificate_path is None
        assert ("auth.provider.cleared", "certificate") in [
            (event.action, event.object_id) for event in state.bucket_events
        ]


def test_reset_uses_token_directory_from_supplied_settings(tmp_path: Path) -> None:
    """A supplied Settings object routes acquisition-lock cleanup to its token root."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile(_PROFILE_A, provider="certificate")
        token_dir = tmp_path / "target-tokens"
        with override_settings(cadrumo_token_dir=token_dir) as settings, profile_storage_session(_PROFILE_A):
            lock_path = auth_acquisition_lock_path(
                settings,
                AuthProviderKind.CERTIFICATE,
                bucket_id=_PROFILE_A,
            )
            with acquire_auth_acquisition_lock(
                settings,
                AuthProviderKind.CERTIFICATE,
                ttl_seconds=60,
                operation="test-reset-token-root",
            ):
                assert lock_path.is_file()
                result = reset_operator_auth(provider="certificate", settings=settings)
                assert lock_path.exists() is False

        assert result.cleared_locks == 1


def test_explicit_target_bucket_restores_unrelated_ambient_session(tmp_path: Path) -> None:
    """Reset bucket B through a nested span and restore ambient bucket A unchanged."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile(_PROFILE_A, provider="certificate")
        _create_profile(_PROFILE_B, provider="clave_movil")

        with profile_storage_session(_PROFILE_A):
            ambient_before = current_active_bucket_session()
            assert ambient_before is not None
            assert ambient_before.bucket_id == _PROFILE_A
            state_a_before = workflow_state_repository().load()

            result = reset_operator_auth(
                provider="clave_movil",
                target_bucket_id=_PROFILE_B,
            )

            ambient_after = current_active_bucket_session()
            assert ambient_after is ambient_before
            assert workflow_state_repository().load() == state_a_before

        with profile_storage_session(_PROFILE_B):
            state_b = workflow_state_repository().load()

        assert result.bucket_id == _PROFILE_B
        assert result.cleared_provider_configuration is True
        assert state_b.auth.provider is None
