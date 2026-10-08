"""Runtime-owned bootstrap custody over the existing verified native connection."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from ...adapters.local_runtime.runtime_frame_io import decode_document, read_secret, write_document
from ...adapters.persistence.storage.custody.acceleration_receipt import ReceiptDeletion
from ...adapters.persistence.storage.errors import StorageError
from ...adapters.persistence.storage.profile_persistence_composition import composed_profile_persistence_ports
from ...application.operations.registry import OperationFrontendProjection
from ...application.runtime.bootstrap import (
    RuntimePasswordReset,
    RuntimePasswordResetCompleted,
    RuntimePasswordResetPrepare,
    RuntimePasswordResetPrepared,
    RuntimePasswordResetRefused,
    RuntimePasswordResetSecrets,
)
from ...application.runtime.contracts import RuntimeByteChannel, RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.profile_access import RuntimeAccessRefusal, RuntimeSecretReady
from ...application.runtime.transport import RuntimeConnectionContext
from ...application.user_profile.access_contracts import Availability
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...application.user_profile.automation_lifecycle_service import HumanSignInRevocationResult
from ...application.user_profile.custody_ports import load_profile_custody_password_material
from ...application.user_profile.custody_repository import profile_custody_transaction_lock
from ...application.user_profile.custody_transactions import ProfileCustodyTransactionError
from ...application.user_profile.login_session import ProfileLoginThrottledError
from ...application.user_profile.recovery_custody import ProfileRecoveryError, reset_profile_passphrase_with_recovery
from ...application.user_profile.session_retirement import SessionRetirementKind
from ...domain.calculations.registry.authority import bundled_indexed_authority

if TYPE_CHECKING:
    from .profile_connections import RuntimeProfileConnections


class RuntimeBootstrapMixin:
    """Retain transaction ownership through client disconnect and final output."""

    def bootstrap(
        self: RuntimeProfileConnections,
        context: RuntimeConnectionContext,
        channel: RuntimeByteChannel,
        request: RuntimePasswordResetPrepare | RuntimePasswordReset,
    ) -> None:
        """Never admit a session or send a profile key through this proof-only door."""
        coordinates = dict(
            request_id=request.request_id,
            runtime_boot_id=self.boot,
            connection_id=context.connection_id,
            profile_id=request.profile_id,
        )
        try:
            if isinstance(request, RuntimePasswordResetPrepare):
                if request.frontend not in {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}:
                    raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
                connection, host = self._prepare_unadmitted(context, channel, request, method="bootstrap-reset")
                with host.guard, composed_profile_persistence_ports(automation_secrets_store=self._secret_store()):
                    self._validate_access_connection(connection, host)
                    with profile_custody_transaction_lock(self.root, request.profile_id):
                        material = load_profile_custody_password_material(request.profile_id, root=self.root)
                        connection.bootstrap_digest = material.envelope.self_digest
                result = RuntimePasswordResetPrepared.model_validate(
                    {
                        **coordinates,
                        "envelope_digest": connection.bootstrap_digest,
                    }
                )
            else:
                if context.runtime_boot_id != self.boot or context.peer != channel.peer:
                    raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
                connection = self._connected(context.connection_id)
                with self._guard:
                    host = self._profiles.get(request.profile_id)
                if (
                    host is None
                    or connection.context != context
                    or connection.profile_id != request.profile_id
                    or connection.method != "bootstrap-reset"
                    or connection.session_id is not None
                ):
                    raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
                with host.guard:
                    self._validate_access_connection(connection, host)
                    if connection.bootstrap_digest != request.envelope_digest:
                        raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
                    connection.bootstrap_digest = None
                write_document(
                    channel,
                    RuntimeSecretReady(
                        request_id=request.request_id,
                        runtime_boot_id=self.boot,
                        connection_id=context.connection_id,
                    ),
                    deadline=time.monotonic() + 5,
                )
                with read_secret(channel, deadline=time.monotonic() + 10) as secret:
                    payload = decode_document(bytes(secret), RuntimePasswordResetSecrets)
                cleanup: HumanSignInRevocationResult | None = None

                def revoke() -> None:
                    nonlocal cleanup
                    # The custody owner holds root then profile here. Reobserve
                    # native facts without acquiring the connection-map guard:
                    # another host may hold that guard while awaiting root.
                    observed = connection.login.observe(credential_facilities=Availability.UNAVAILABLE)
                    if (
                        not self._admitting()
                        or not observed.active
                        or not observed.unlocked
                        or observed.os_owner_id != context.peer.os_owner_id
                    ):
                        raise AutomationCustodyError(AutomationCustodyCode.NEEDS_USER)
                    deletion, _ = host.revoke_human_sign_in(kind=SessionRetirementKind.REVOKED)
                    cleanup = HumanSignInRevocationResult(
                        receipt_removed=deletion is not ReceiptDeletion.RECEIPT_RETAINED,
                        keychain_removed=deletion in {ReceiptDeletion.DELETED, ReceiptDeletion.NOT_REQUIRED},
                    )

                try:
                    with host.guard, composed_profile_persistence_ports(automation_secrets_store=self._secret_store()):
                        self._validate_access_connection(connection, host)
                        with bundled_indexed_authority().operation() as operation:
                            outcome = reset_profile_passphrase_with_recovery(
                                profile_id=request.profile_id,
                                root=self.root,
                                recovery_code=payload.recovery_code.get_secret_value(),
                                new_passphrase=payload.new_passphrase.get_secret_value(),
                                new_passphrase_confirmation=payload.new_passphrase_confirmation.get_secret_value(),
                                profile_decode_context=operation.profile_decode_context(),
                                expected_envelope_digest=request.envelope_digest,
                                before_replace=revoke,
                            )
                    if cleanup is None:
                        raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
                    result = RuntimePasswordResetCompleted.model_validate(
                        {
                            **coordinates,
                            "outcome": outcome,
                            "human_sign_in_revocation": cleanup,
                        }
                    )
                finally:
                    del payload
                    self._synchronize_profile_sessions(host)
        except ProfileLoginThrottledError as error:
            result = RuntimePasswordResetRefused.model_validate(
                {
                    **coordinates,
                    "code": "throttled",
                    "remaining_seconds": error.remaining_seconds,
                }
            )
        except ProfileRecoveryError as error:
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
            result = RuntimePasswordResetRefused.model_validate(
                {
                    **coordinates,
                    "code": code,
                    "password_refusal": error.password_refusal,
                }
            )
        except (AutomationCustodyError, RuntimeRefusalError) as error:
            result = RuntimeAccessRefusal(
                request_id=request.request_id,
                runtime_boot_id=self.boot,
                connection_id=context.connection_id,
                code=error.reason,
            )
        except (OSError, StorageError, ProfileCustodyTransactionError):
            # A storage/publication refusal leaves its existing custody fence
            # authoritative. Do not turn a retryable target failure into loss
            # of every other profile's runtime, or claim a committed outcome.
            result = RuntimeAccessRefusal(
                request_id=request.request_id,
                runtime_boot_id=self.boot,
                connection_id=context.connection_id,
                code=AutomationCustodyCode.UNAVAILABLE,
            )
        # Completion does not depend on a surviving client. The serving owner
        # retains this call through all custody effects; only output may fail.
        write_document(channel, result, deadline=time.monotonic() + 5)
