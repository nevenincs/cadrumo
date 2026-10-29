"""Runtime-owned bootstrap custody over the existing verified native connection."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from cadrumo.adapters.persistence.storage.custody.acceleration_receipt import ReceiptDeletion
from cadrumo.adapters.persistence.storage.errors import StorageError
from cadrumo.adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from cadrumo.application.user_profile.automation_custody_port import AutomationSecretStore
from cadrumo.application.user_profile.custody_ports import load_profile_custody_password_material
from cadrumo.application.user_profile.custody_repository import profile_custody_transaction_lock
from cadrumo.application.user_profile.custody_transactions import ProfileCustodyTransactionError
from cadrumo.application.user_profile.recovery_custody import (
    ProfileRecoveryError,
    reset_profile_passphrase_with_recovery,
)
from cadrumo.application.user_profile.session_retirement import SessionRetirementKind
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo_client.contracts.access_vocabulary import Availability
from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError
from cadrumo_client.contracts.automation_lifecycle import HumanSignInRevocationResult
from cadrumo_client.contracts.bootstrap import (
    PasswordReset,
    PasswordResetCompleted,
    PasswordResetPrepare,
    PasswordResetPrepared,
    PasswordResetRefused,
    PasswordResetSecrets,
)
from cadrumo_client.contracts.contracts import ByteChannel, RefusalCode, RefusalError
from cadrumo_client.contracts.profile_access import AccessRefusal, SecretReady
from cadrumo_client.contracts.sign_in_outcomes import ProfileLoginThrottledError
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.transport.frame_io import decode_document, read_secret, write_document

from .profile_connection import ProfileConnection
from .profile_host import RuntimeProfileHost

if TYPE_CHECKING:
    from .profile_connections import RuntimeProfileConnections


def recovery_refusal(error: ProfileRecoveryError, coordinates: Mapping[str, UUID]) -> PasswordResetRefused:
    """Translate only the established recovery refusals, propagating unknown failures."""
    code = (
        "invalid_password"
        if error.password_refusal is not None
        else (error.translated_message or "").removeprefix("application.user_profile.errors.")
    )
    if code not in {
        "invalid_password",
        "recovery_code_rejected",
        "recovery_not_enrolled",
        "passphrase_confirmation_mismatch",
    }:
        raise
    return PasswordResetRefused.model_validate(
        {
            **coordinates,
            "code": code,
            "password_refusal": error.password_refusal,
        }
    )


def reset_connection_matches(connection: ProfileConnection, context: ConnectionContext, request: PasswordReset) -> bool:
    """Require the exact unadmitted reset connection before reading secrets."""
    return (
        connection.context == context
        and connection.profile_id == request.profile_id
        and connection.method == "bootstrap-reset"
        and connection.session_id is None
    )


def revoke_reset_sign_in(
    connection: ProfileConnection, host: RuntimeProfileHost, context: ConnectionContext, admitting: Callable[[], bool]
) -> HumanSignInRevocationResult:
    """Reobserve native authority without acquiring the connection-map guard."""
    observed = connection.login.observe(credential_facilities=Availability.UNAVAILABLE)
    if (
        not admitting()
        or not observed.active
        or not observed.unlocked
        or observed.os_owner_id != context.peer.os_owner_id
    ):
        raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)
    deletion, _ = host.revoke_human_sign_in(kind=SessionRetirementKind.REVOKED)
    return HumanSignInRevocationResult(
        receipt_removed=deletion is not ReceiptDeletion.RECEIPT_RETAINED,
        keychain_removed=deletion in {ReceiptDeletion.DELETED, ReceiptDeletion.NOT_REQUIRED},
    )


def complete_reset(
    context: ConnectionContext,
    channel: ByteChannel,
    request: PasswordReset,
    coordinates: Mapping[str, UUID],
    *,
    boot: UUID,
    root: Path,
    connected: Callable[[UUID], ProfileConnection],
    profile: Callable[[UUID], RuntimeProfileHost | None],
    validate: Callable[[ProfileConnection, RuntimeProfileHost], None],
    secret_store: Callable[[], AutomationSecretStore],
    admitting: Callable[[], bool],
    synchronize: Callable[[RuntimeProfileHost], None],
) -> PasswordResetCompleted:
    """Keep proof, transaction and session cleanup under the original owner."""
    if context.runtime_boot_id != boot or context.peer != channel.peer:
        raise RefusalError(RefusalCode.PEER_UNTRUSTED)
    connection = connected(context.connection_id)
    host = profile(request.profile_id)
    if host is None or not reset_connection_matches(connection, context, request):
        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
    with host.guard:
        validate(connection, host)
        if connection.bootstrap_digest != request.envelope_digest:
            raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
        connection.bootstrap_digest = None
    write_document(
        channel,
        SecretReady(
            request_id=request.request_id,
            runtime_boot_id=boot,
            connection_id=context.connection_id,
        ),
        deadline=time.monotonic() + 5,
    )
    with read_secret(channel, deadline=time.monotonic() + 10) as secret:
        payload = decode_document(bytes(secret), PasswordResetSecrets)
    cleanup: HumanSignInRevocationResult | None = None

    def revoke() -> None:
        nonlocal cleanup
        cleanup = revoke_reset_sign_in(connection, host, context, admitting)

    try:
        with host.guard, composed_profile_persistence_ports(automation_secrets_store=secret_store()):
            validate(connection, host)
            with bundled_indexed_authority().operation() as operation:
                outcome = reset_profile_passphrase_with_recovery(
                    profile_id=request.profile_id,
                    root=root,
                    recovery_code=payload.recovery_code.get_secret_value(),
                    new_passphrase=payload.new_passphrase.get_secret_value(),
                    new_passphrase_confirmation=payload.new_passphrase_confirmation.get_secret_value(),
                    profile_decode_context=operation.profile_decode_context(),
                    expected_envelope_digest=request.envelope_digest,
                    before_replace=revoke,
                )
        if cleanup is None:
            raise RefusalError(RefusalCode.UNAVAILABLE)
        return PasswordResetCompleted.model_validate(
            {
                **coordinates,
                "outcome": outcome,
                "human_sign_in_revocation": cleanup,
            }
        )
    finally:
        del payload
        synchronize(host)


class RuntimeBootstrapMixin:
    """Retain transaction ownership through client disconnect and final output."""

    def bootstrap(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        channel: ByteChannel,
        request: PasswordResetPrepare | PasswordReset,
    ) -> None:
        """Never admit a session or send a profile key through this proof-only door."""
        named = request.frontend if isinstance(request, PasswordResetPrepare) else None
        if self._refused_as_persons_act(
            context, channel, request_id=request.request_id, frontend=named or self._connection_frontend(context)
        ):
            return
        coordinates = dict(
            request_id=request.request_id,
            runtime_boot_id=self.boot,
            connection_id=context.connection_id,
            profile_id=request.profile_id,
        )
        try:
            if isinstance(request, PasswordResetPrepare):
                connection, host = self._prepare_unadmitted(context, channel, request, method="bootstrap-reset")
                with host.guard, composed_profile_persistence_ports(automation_secrets_store=self._secret_store()):
                    self._validate_access_connection(connection, host)
                    with profile_custody_transaction_lock(self.root, request.profile_id):
                        material = load_profile_custody_password_material(request.profile_id, root=self.root)
                        connection.bootstrap_digest = material.envelope.self_digest
                result = PasswordResetPrepared.model_validate(
                    {
                        **coordinates,
                        "envelope_digest": connection.bootstrap_digest,
                    }
                )
            else:

                def profile(profile_id: UUID) -> RuntimeProfileHost | None:
                    with self._guard:
                        return self._profiles.get(profile_id)

                result = complete_reset(
                    context,
                    channel,
                    request,
                    coordinates,
                    boot=self.boot,
                    root=self.root,
                    connected=self._connected,
                    profile=profile,
                    validate=self._validate_access_connection,
                    secret_store=self._secret_store,
                    admitting=self._admitting,
                    synchronize=self._synchronize_profile_sessions,
                )
        except ProfileLoginThrottledError as error:
            result = PasswordResetRefused.model_validate(
                {
                    **coordinates,
                    "code": "throttled",
                    "remaining_seconds": error.remaining_seconds,
                }
            )
        except ProfileRecoveryError as error:
            result = recovery_refusal(error, coordinates)
        except (AutomationCustodyError, RefusalError) as error:
            result = AccessRefusal(
                request_id=request.request_id,
                runtime_boot_id=self.boot,
                connection_id=context.connection_id,
                code=error.reason,
            )
        except (OSError, StorageError, ProfileCustodyTransactionError):
            # A storage/publication refusal leaves its existing custody fence
            # authoritative. Do not turn a retryable target failure into loss
            # of every other profile's runtime, or claim a committed outcome.
            result = AccessRefusal(
                request_id=request.request_id,
                runtime_boot_id=self.boot,
                connection_id=context.connection_id,
                code=AutomationCustodyCode.UNAVAILABLE,
            )
        # Completion does not depend on a surviving client. The serving owner
        # retains this call through all custody effects; only output may fail.
        write_document(channel, result, deadline=time.monotonic() + 5)
