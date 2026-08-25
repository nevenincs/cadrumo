"""Real-storage coverage for target-scoped operator auth logout and reset."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr

from cadrumo.application.workflow.persistence import workflow_state_repository

from ....adapters.outbound.aeat.auth import session_store
from ....adapters.persistence.storage import has_active_bucket_session
from ....adapters.persistence.storage.bucket import (
    BucketBusyError,
    acquire_lock,
    bucket_paths,
    release_lock,
)
from ....adapters.persistence.storage.master_key import current_active_bucket_session
from ....application.wizard import WIZARD_FLOWS
from ....core import AuthProviderKind
from ....core.config import load_settings, override_settings
from ....core.errors import ERROR_REGISTRY, build_error_envelope, resolve_error_message
from ....domain.contribuyente import required_profile_keys
from ....tests.profile_capsule import open_test_profile_session
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile
from ..acquisition_lock import acquire_auth_acquisition_lock, auth_acquisition_lock_path
from ..certificate_source_operations import (
    register_operator_certificate_source,
    select_operator_certificate_source,
    set_operator_certificate_source_secret,
)
from ..credentials import resolve_certificate_source_secret
from ..operator import configure_operator_auth, logout_operator_auth, reset_operator_auth
from ..operator_results import AuthOperationScopeConflictError, AuthProviderNotConfiguredError
from ..operator_scope import auth_mutation_span
from ..sessions import load_persisted_session, storage_state_paths

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_A = "11111111-1111-4111-8111-111111111111"
_PROFILE_B = "22222222-2222-4222-8222-222222222222"


def _create_profile(profile_id: str, *, provider: str | None = None) -> None:
    assert WIZARD_FLOWS
    assert required_profile_keys()
    with open_test_profile_session(profile_id):
        register_minimal_profile(profile_id=profile_id)
        if provider is not None:
            configure_operator_auth(provider)


def _logout(*, unlock: str | None = None, **kwargs):
    """Revoke with the profile unlocked, which is what the operator must now do.

    The AEAT session is an encrypted row inside the profile's own store, so
    revoking it requires the profile open -- there is no key-free half to
    perform from a cold pointer. Every result assertion in this module is
    unchanged; only the premise moved, from "no session is bound" to "the
    operator has unlocked the profile they are revoking".
    """
    with open_test_profile_session(unlock or kwargs.get("target_bucket_id") or _PROFILE_A):
        return logout_operator_auth(**kwargs)


def _reset(*, unlock: str | None = None, **kwargs):
    """Reset with the profile unlocked, for the same reason as :func:`_logout`.

    An explicit ``target_bucket_id`` names the profile being revoked, so that is
    the one unlocked -- revoking B while only A is open is precisely what the
    custody guard refuses.
    """
    with open_test_profile_session(unlock or kwargs.get("target_bucket_id") or _PROFILE_A):
        return reset_operator_auth(**kwargs)


def test_auth_mutation_uses_canonical_bucket_lock(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile(_PROFILE_A)
        settings = load_settings().model_copy(
            update={"cadrumo_file_lock_timeout_s": 0.05},
        )
        paths = bucket_paths(settings.cadrumo_local_storage_root, _PROFILE_A)

        def attempt_auth_mutation() -> None:
            with auth_mutation_span(settings=settings, bucket_id=_PROFILE_A):
                pass

        acquire_lock(paths)
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                blocked = executor.submit(attempt_auth_mutation)
                with pytest.raises(BucketBusyError):
                    blocked.result(timeout=5)
        finally:
            release_lock(paths)


def test_logout_reopens_pointer_profile_and_is_idempotent(tmp_path: Path) -> None:
    """Logout clears readiness, preserves configuration, and does not rewrite a second time."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile(_PROFILE_A, provider="certificate")
        with open_test_profile_session(_PROFILE_A):
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

        # The revocation opens and closes its own session; the caller's
        # context holds none before or after, which is what stops a mutation
        # leaking an unlocked profile into whatever runs next.
        assert has_active_bucket_session() is False
        first = _logout(provider="certificate")
        assert has_active_bucket_session() is False

        with open_test_profile_session(_PROFILE_A):
            after_first = workflow_state_repository().load()
        second = _logout(provider="certificate")
        with open_test_profile_session(_PROFILE_A):
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
            _logout()
        with pytest.raises(AuthProviderNotConfiguredError):
            _reset()
        with pytest.raises(AuthOperationScopeConflictError):
            _logout(provider="certificate", all_providers=True)
        with pytest.raises(AuthOperationScopeConflictError):
            _reset(provider="certificate", all_providers=True)


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


def test_auth_scope_conflict_has_explicit_no_recovery() -> None:
    """The shared logout/reset scope error carries no untyped recovery command."""
    error = AuthOperationScopeConflictError(
        translated_message="application.auth.operator.errors.scope_conflict",
    )

    assert build_error_envelope(error).action is None


def test_reserved_provider_reset_is_an_idempotent_noop(tmp_path: Path) -> None:
    """Known reserved providers are valid targets and never clear another configured provider."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile(_PROFILE_A, provider="certificate")

        first = _reset(provider="clave_pin")
        second = _reset(provider="clave_pin")
        with open_test_profile_session(_PROFILE_A):
            state = workflow_state_repository().load()

        assert first.cleared_provider_configuration is False
        assert second == first
        assert state.auth.provider == "certificate"


def test_logout_deletes_real_clave_permanente_session(tmp_path: Path) -> None:
    """Cl@ve Permanente uses its production storage stem and is deleted by logout."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile(_PROFILE_A, provider="clave_permanente")
        with open_test_profile_session(_PROFILE_A):
            path = storage_state_paths(AuthProviderKind.CLAVE_PERMANENTE).storage_state
            session_store.save(path, storage_state={}, metadata={"provider_kind": "clave_permanente"})
            assert session_store.exists(path)

        result = _logout(provider="clave_permanente")

        with open_test_profile_session(_PROFILE_A):
            assert session_store.exists(path) is False
        assert result.removed_sessions == 1


def test_certificate_logout_removes_session_and_preserves_certificate_configuration(
    tmp_path: Path,
) -> None:
    """Certificate logout removes only the persisted session, not its configured custody."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        certificate_path = tmp_path / "personal.p12"
        certificate_path.write_bytes(b"real-storage-certificate-fixture")
        _create_profile(_PROFILE_A, provider="certificate")

        with open_test_profile_session(_PROFILE_A):
            register_operator_certificate_source(
                name="personal",
                certificate_path=certificate_path,
                friendly_name="Personal certificate",
            )
            select_operator_certificate_source(name="personal")
            set_operator_certificate_source_secret(
                name="personal",
                secret=SecretStr("certificate-passphrase"),
            )
            repository = workflow_state_repository()
            before = repository.load()
            session_path = storage_state_paths(AuthProviderKind.CERTIFICATE).storage_state
            authenticated_at = datetime.now(UTC)
            session_store.save(
                session_path,
                storage_state={"cookies": [], "origins": []},
                metadata={
                    "provider_kind": "certificate",
                    "identity_nif": "12345678Z",
                    "authenticated_at": authenticated_at.isoformat(),
                    "idle_deadline": (authenticated_at + timedelta(minutes=30)).isoformat(),
                },
            )
            assert session_store.exists(session_path)
            persisted_before = load_persisted_session(
                load_settings(),
                AuthProviderKind.CERTIFICATE,
            )
            secret_before = resolve_certificate_source_secret(
                name="personal",
                bucket_id=_PROFILE_A,
            )

        assert persisted_before is not None
        assert persisted_before.provider_kind is AuthProviderKind.CERTIFICATE
        assert persisted_before.identity_nif == "12345678Z"
        assert secret_before is not None
        provider_configuration_before = (
            before.auth.provider,
            before.auth.configured_at,
        )
        certificate_path_before = before.auth.certificate_path
        active_source_before = before.auth.active_certificate_source
        source_registration_before = before.auth.certificate_sources["personal"]
        secret_value_before = secret_before.get_secret_value()

        result = _logout(provider="certificate")

        with open_test_profile_session(_PROFILE_A):
            after = workflow_state_repository().load()
            secret_after = resolve_certificate_source_secret(
                name="personal",
                bucket_id=_PROFILE_A,
            )
            assert session_store.exists(session_path) is False

        assert result.removed_sessions == 1
        assert (after.auth.provider, after.auth.configured_at) == provider_configuration_before
        assert after.auth.certificate_path == certificate_path_before
        assert after.auth.active_certificate_source == active_source_before
        assert after.auth.certificate_sources["personal"] == source_registration_before
        assert secret_after is not None
        assert secret_after.get_secret_value() == secret_value_before


def test_logout_all_emits_events_only_for_affected_providers(tmp_path: Path) -> None:
    """An all-provider sweep never claims unrelated providers had session artefacts."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile(_PROFILE_A, provider="certificate")
        with open_test_profile_session(_PROFILE_A):
            repository = workflow_state_repository()
            before = repository.load()
            path = storage_state_paths(AuthProviderKind.CLAVE_PERMANENTE).storage_state
            session_store.save(path, storage_state={}, metadata={"provider_kind": "clave_permanente"})

        result = _logout(all_providers=True)
        with open_test_profile_session(_PROFILE_A):
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
        with open_test_profile_session(_PROFILE_A):
            register_operator_certificate_source(name="personal", certificate_path=cert_path)
            set_operator_certificate_source_secret(name="personal", secret=SecretStr("do-not-leak"))
            assert resolve_certificate_source_secret(name="personal", bucket_id=_PROFILE_A) is not None

        first = _reset(provider="certificate")
        second = _reset(provider="certificate")
        with open_test_profile_session(_PROFILE_A):
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
        with open_test_profile_session(_PROFILE_A):
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

        result = _reset(provider="certificate")
        with open_test_profile_session(_PROFILE_A):
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
        with override_settings(cadrumo_token_dir=token_dir) as settings, open_test_profile_session(_PROFILE_A):
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
                result = _reset(provider="certificate", settings=settings)
                assert lock_path.exists() is False

        assert result.cleared_locks == 1


def test_explicit_target_bucket_restores_unrelated_ambient_session(tmp_path: Path) -> None:
    """Reset bucket B through a nested span and restore ambient bucket A unchanged."""
    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile(_PROFILE_A, provider="certificate")
        _create_profile(_PROFILE_B, provider="clave_movil")

        with open_test_profile_session(_PROFILE_A):
            ambient_before = current_active_bucket_session()
            assert ambient_before is not None
            assert ambient_before.bucket_id == _PROFILE_A
            state_a_before = workflow_state_repository().load()

            result = _reset(
                provider="clave_movil",
                target_bucket_id=_PROFILE_B,
            )

            ambient_after = current_active_bucket_session()
            assert ambient_after is ambient_before
            assert workflow_state_repository().load() == state_a_before

        with open_test_profile_session(_PROFILE_B):
            state_b = workflow_state_repository().load()

        assert result.bucket_id == _PROFILE_B
        assert result.cleared_provider_configuration is True
        assert state_b.auth.provider is None


def test_revoking_a_locked_profile_refuses_and_says_the_session_is_still_live(tmp_path: Path) -> None:
    """The contract that replaced the cold-pointer premise, pinned rather than implied.

    An AEAT session is an encrypted row inside the profile's own store, so
    revoking it requires the profile open. There is no key-free half to perform
    first: clearing locks revokes nothing, and a partial that reported success
    would tell the operator their session was gone while the row survived on
    disk. The refusal is therefore the honest surface, and what it must carry is
    the fact the operator cannot otherwise discover -- that the session is still
    usable -- rather than that the profile is locked, which they already know.
    """
    from ....core.errors import resolve_error_message
    from ..operator_results import AuthOperationRequiresCustodySessionError

    with isolated_profile_storage_root(tmp_path=tmp_path):
        _create_profile(_PROFILE_A, provider="certificate")

        with override_settings(cadrumo_active_profile=_PROFILE_A):
            assert has_active_bucket_session() is False

            with pytest.raises(AuthOperationRequiresCustodySessionError) as raised:
                logout_operator_auth(provider="certificate")

    message = resolve_error_message(raised.value)
    assert _PROFILE_A in message
    assert "aeat config login" in message
