"""Real supervisor proofs for the canonical auth operation registrations."""

from __future__ import annotations

import asyncio
import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest

from ....adapters.persistence.operations.journal import OperationJournalRepository
from ....adapters.persistence.operations.lease import OperationLeaseFilesystemRepository
from ....adapters.persistence.operations.secure_references import operation_secure_reference_repository
from ....adapters.persistence.storage import SecureObjectRepository
from ....core.auth_provider import AuthProviderKind
from ....core.operations import (
    OperationEffect,
    OperationLifecycle,
    OperationTerminalCondition,
)
from ....tests.secure_sql import isolated_profile_storage_root, isolated_runtime_profile
from ...operations.capabilities import OperationRequestStoragePolicy
from ...operations.models import OperationRequest
from ...operations.registry import OperationRegistry
from ...operations.supervisor import OperationSupervisor
from ...user_profile.custody_ports import profile_custody_secure_object_repository
from ...user_profile.login_session import login_profile, logout_active_profile
from ...user_profile.registration import register_profile_with_credentials
from ..operation_definitions import (
    AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
    AUTH_LOGOUT_OPERATION_DEFINITION_ID,
    AUTH_OPERATION_DEFINITIONS,
    AUTH_RESET_OPERATION_DEFINITION_ID,
    AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID,
    PROFILE_LOGIN_OPERATION_DEFINITION_ID,
    PROFILE_PASSPHRASE_ROTATION_OPERATION_DEFINITION_ID,
    AuthConfigureOperationRequest,
    AuthSessionAcquireOperationRequest,
    AuthTeardownOperationRequest,
    ProfileLoginOperationRequest,
    ProfilePassphraseRotationOperationRequest,
    build_auth_operation_registrations,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_CURRENT = "s39-current-profile-passphrase"
_REPLACEMENT = "s39-replacement-profile-passphrase"


def _supervisor(
    root: Path,
    *,
    profile_objects: SecureObjectRepository | None = None,
    clock: Callable[[], datetime] | None = None,
    owner_id: str = "1" * 64,
    lease_token: str = "2" * 64,
) -> OperationSupervisor:
    journal = OperationJournalRepository(storage_root=root)
    operands = None if profile_objects is None else operation_secure_reference_repository(objects=profile_objects)
    return OperationSupervisor(
        registry=OperationRegistry(
            definitions=AUTH_OPERATION_DEFINITIONS,
            public_registrations=build_auth_operation_registrations(AUTH_OPERATION_DEFINITIONS),
        ),
        journal=journal,
        event_stream=journal,
        leases=OperationLeaseFilesystemRepository(storage_root=root),
        operands=operands,
        owner_id=owner_id,
        lease_token_factory=lambda: lease_token,
        clock=(lambda: datetime.now(UTC)) if clock is None else clock,
        lease_duration=timedelta(minutes=6),
    )


def _register_profile() -> UUID:
    registered = register_profile_with_credentials(
        label="S39 Auth Operation Subject",
        passphrase=_CURRENT,
        recovery_handover=lambda enrollment: enrollment.recovery_key.mnemonic,
    )
    return UUID(registered.profile_id)


def _assert_not_durable(root: Path, secret: bytes) -> None:
    derivative = hashlib.sha256(secret).hexdigest().encode("ascii")
    for path in root.rglob("*"):
        if path.is_file():
            contents = path.read_bytes()
            assert secret not in contents, path
            assert derivative not in contents, path


def _run_secret_operation(
    *,
    supervisor: OperationSupervisor,
    definition_id: str,
    subject_ref: str,
    payload: ProfileLoginOperationRequest | ProfilePassphraseRotationOperationRequest,
    operation_id: str,
    secret: bytes,
):
    request = OperationRequest(definition_id=definition_id, subject_ref=subject_ref, payload=payload)
    created_id = asyncio.run(supervisor.submit(request, operation_id=operation_id))
    created = asyncio.run(supervisor.inspect(created_id))
    assert created.secret_requirement is not None
    submission = bytearray(secret)
    asyncio.run(supervisor.submit_ephemeral_secret(created.secret_requirement, submission))
    assert submission == bytearray(len(secret))
    return asyncio.run(supervisor.start(created_id))


def test_auth_families_have_one_canonical_registered_operation_each() -> None:
    registry = OperationRegistry(definitions=AUTH_OPERATION_DEFINITIONS)
    definition_ids = tuple(definition.definition_id for definition in AUTH_OPERATION_DEFINITIONS)
    assert definition_ids == (
        PROFILE_LOGIN_OPERATION_DEFINITION_ID,
        AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
        AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID,
        AUTH_LOGOUT_OPERATION_DEFINITION_ID,
        AUTH_RESET_OPERATION_DEFINITION_ID,
        PROFILE_PASSPHRASE_ROTATION_OPERATION_DEFINITION_ID,
    )
    assert len(set(definition_ids)) == len(definition_ids)
    assert {
        definition_id
        for definition_id in definition_ids
        if registry.lookup(definition_id).capabilities.request_storage
        is OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL
    } == {
        PROFILE_LOGIN_OPERATION_DEFINITION_ID,
    }
    assert all(
        registry.lookup(definition_id).capabilities.request_storage is OperationRequestStoragePolicy.SECURE_REFERENCE
        for definition_id in (
            AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
            AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID,
            AUTH_LOGOUT_OPERATION_DEFINITION_ID,
            AUTH_RESET_OPERATION_DEFINITION_ID,
            PROFILE_PASSPHRASE_ROTATION_OPERATION_DEFINITION_ID,
        )
    )
    assert registry.lookup(PROFILE_LOGIN_OPERATION_DEFINITION_ID).ephemeral_secret is not None
    assert registry.lookup(PROFILE_PASSPHRASE_ROTATION_OPERATION_DEFINITION_ID).ephemeral_secret is not None
    assert all(
        registry.lookup(definition_id).ephemeral_secret is None
        for definition_id in (
            AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
            AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID,
            AUTH_LOGOUT_OPERATION_DEFINITION_ID,
            AUTH_RESET_OPERATION_DEFINITION_ID,
        )
    )


def test_profile_login_uses_a_requirement_bound_secret_without_durable_secret_bytes(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        profile_id = _register_profile()
        login_profile(name=str(profile_id), passphrase_callback=lambda: _CURRENT)
        assert logout_active_profile() == str(profile_id)
        terminal = _run_secret_operation(
            supervisor=_supervisor(root),
            definition_id=PROFILE_LOGIN_OPERATION_DEFINITION_ID,
            subject_ref=f"profile:{profile_id}",
            payload=ProfileLoginOperationRequest(profile_id=profile_id),
            operation_id="3" * 64,
            secret=_CURRENT.encode("utf-8"),
        )
        assert terminal.lifecycle is OperationLifecycle.TERMINAL
        assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert terminal.effect is OperationEffect.UPDATED
        assert terminal.terminal_receipt is not None
        assert terminal.terminal_receipt.result_ref == f"profile:{profile_id}"
        _assert_not_durable(root, _CURRENT.encode("utf-8"))


def test_profile_login_secret_wait_rejects_mismatch_and_settles_cancel_or_restart_before_entry(tmp_path: Path) -> None:
    observed_at = [datetime(2026, 8, 24, 12, tzinfo=UTC)]
    supervisor = _supervisor(tmp_path, clock=lambda: observed_at[0])
    profile_id = UUID("11111111-1111-4111-8111-111111111111")
    request = OperationRequest(
        definition_id=PROFILE_LOGIN_OPERATION_DEFINITION_ID,
        subject_ref=f"profile:{profile_id}",
        payload=ProfileLoginOperationRequest(profile_id=profile_id),
    )
    cancelled_id = asyncio.run(supervisor.submit(request, operation_id="a" * 64))
    requirement = asyncio.run(supervisor.inspect(cancelled_id)).secret_requirement
    assert requirement is not None
    mismatch = requirement.model_copy(
        update={"identity": requirement.identity.model_copy(update={"subject_ref": "profile:wrong"})}
    )
    rejected = bytearray(_CURRENT.encode("utf-8"))
    with pytest.raises(ValueError, match="does not match"):
        asyncio.run(supervisor.submit_ephemeral_secret(mismatch, rejected))
    assert rejected == bytearray(len(rejected))
    cancelled = asyncio.run(supervisor.request_cancel(cancelled_id))
    assert cancelled.terminal_condition is OperationTerminalCondition.CANCELLED
    assert cancelled.effect is OperationEffect.NONE

    restart_id = asyncio.run(supervisor.submit(request, operation_id="b" * 64))
    asyncio.run(supervisor.shutdown())
    observed_at[0] += timedelta(minutes=7)
    replacement = _supervisor(
        tmp_path,
        clock=lambda: observed_at[0],
        owner_id="c" * 64,
        lease_token="d" * 64,
    )
    interrupted = asyncio.run(replacement.reconcile(restart_id))
    assert interrupted.terminal_condition is OperationTerminalCondition.INTERRUPTED
    assert interrupted.effect is OperationEffect.NONE
    _assert_not_durable(tmp_path, _CURRENT.encode("utf-8"))


def test_passphrase_rotation_uses_one_ephemeral_payload_and_changes_real_custody(tmp_path: Path) -> None:
    with isolated_profile_storage_root(tmp_path=tmp_path) as root:
        profile_id = _register_profile()
        login_profile(name=str(profile_id), passphrase_callback=lambda: _CURRENT)
        secret = json.dumps(
            {
                "current_passphrase": _CURRENT,
                "new_passphrase": _REPLACEMENT,
                "new_passphrase_confirmation": _REPLACEMENT,
            }
        ).encode("utf-8")
        with profile_custody_secure_object_repository(profile_id=profile_id, dek=b"", root=root) as objects:
            assert isinstance(objects, SecureObjectRepository)
            supervisor = _supervisor(root, profile_objects=objects)
            terminal = _run_secret_operation(
                supervisor=supervisor,
                definition_id=PROFILE_PASSPHRASE_ROTATION_OPERATION_DEFINITION_ID,
                subject_ref=f"profile:{profile_id}",
                payload=ProfilePassphraseRotationOperationRequest(profile_id=profile_id),
                operation_id="4" * 64,
                secret=secret,
            )
        assert terminal.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert terminal.effect is OperationEffect.UPDATED
        assert terminal.terminal_receipt is not None
        assert terminal.terminal_receipt.result_ref == f"profile:{profile_id}"
        _assert_not_durable(root, secret)
        assert logout_active_profile() == str(profile_id)

        relogin = _run_secret_operation(
            supervisor=_supervisor(root),
            definition_id=PROFILE_LOGIN_OPERATION_DEFINITION_ID,
            subject_ref=f"profile:{profile_id}",
            payload=ProfileLoginOperationRequest(profile_id=profile_id),
            operation_id="5" * 64,
            secret=_REPLACEMENT.encode("utf-8"),
        )
        assert relogin.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert relogin.effect is OperationEffect.UPDATED
        _assert_not_durable(root, _REPLACEMENT.encode("utf-8"))


def test_configure_acquire_logout_and_reset_execute_through_real_active_profile_storage(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        supervisor = _supervisor(profile.storage_root, profile_objects=profile.repository)
        subject_ref = f"profile:{profile.bucket_id}"

        configured_id = asyncio.run(
            supervisor.submit(
                OperationRequest(
                    definition_id=AUTH_CONFIGURE_OPERATION_DEFINITION_ID,
                    subject_ref=subject_ref,
                    payload=AuthConfigureOperationRequest(provider=AuthProviderKind.CERTIFICATE),
                ),
                operation_id="6" * 64,
            )
        )
        configured = asyncio.run(supervisor.start(configured_id))
        assert configured.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert configured.effect is OperationEffect.UPDATED
        assert configured.terminal_receipt is not None
        assert configured.terminal_receipt.result_ref is not None

        acquired_id = asyncio.run(
            supervisor.submit(
                OperationRequest(
                    definition_id=AUTH_SESSION_ACQUIRE_OPERATION_DEFINITION_ID,
                    subject_ref=subject_ref,
                    payload=AuthSessionAcquireOperationRequest(provider=AuthProviderKind.CERTIFICATE),
                ),
                operation_id="7" * 64,
            )
        )
        acquired = asyncio.run(supervisor.start(acquired_id))
        assert acquired.terminal_condition is OperationTerminalCondition.REFUSED
        assert acquired.effect is OperationEffect.UNKNOWN

        logout_id = asyncio.run(
            supervisor.submit(
                OperationRequest(
                    definition_id=AUTH_LOGOUT_OPERATION_DEFINITION_ID,
                    subject_ref=subject_ref,
                    payload=AuthTeardownOperationRequest(provider=AuthProviderKind.CERTIFICATE),
                ),
                operation_id="8" * 64,
            )
        )
        logged_out = asyncio.run(supervisor.start(logout_id))
        assert logged_out.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert logged_out.effect is OperationEffect.NONE
        assert logged_out.terminal_receipt is not None
        assert logged_out.terminal_receipt.result_ref is not None

        reset_id = asyncio.run(
            supervisor.submit(
                OperationRequest(
                    definition_id=AUTH_RESET_OPERATION_DEFINITION_ID,
                    subject_ref=subject_ref,
                    payload=AuthTeardownOperationRequest(provider=AuthProviderKind.CERTIFICATE),
                ),
                operation_id="9" * 64,
            )
        )
        reset = asyncio.run(supervisor.start(reset_id))
        assert reset.terminal_condition is OperationTerminalCondition.SUCCEEDED
        assert reset.effect is OperationEffect.UPDATED
        assert reset.terminal_receipt is not None
        assert reset.terminal_receipt.result_ref is not None
