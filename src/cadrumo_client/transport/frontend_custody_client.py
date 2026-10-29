"""Bounded frontend access to one native-verified profile runtime connection."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal
from uuid import UUID, uuid4

from cadrumo.application.bucket_deletion_contracts import BucketDeletionFingerprint
from cadrumo.application.user_profile.automation_custody_port import AutomationSecretStore
from cadrumo.application.user_profile.automation_enrollment import AutomationReceiptProjection, EnrollmentStage

from ..contracts.access_management import (
    ProfileRecoveryPrepare,
    ProfileRecoveryPrepared,
    ProfileResume,
    ProfileResumed,
)
from ..contracts.automation_codes import AutomationCustodyCode
from ..contracts.automation_lifecycle import AutomationResumeReceipt
from ..contracts.bootstrap import (
    PasswordReset,
    PasswordResetCompleted,
    PasswordResetPrepare,
    PasswordResetPrepared,
    PasswordResetRefused,
)
from ..contracts.bootstrap_delete import (
    ProfileDelete,
    ProfileDeleted,
    ProfileDeletePrepare,
    ProfileDeletePrepared,
    ProfileDeleteRefused,
)
from ..contracts.contracts import RefusalCode, RefusalError
from ..contracts.deadline_budget import (
    MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS,
    deadline_after,
)
from ..contracts.enrollment_access import EnrollmentPrepare, EnrollmentPrepared, EnrollmentReconcile, EnrollmentRecorded
from ..contracts.sign_in_outcomes import ProfileLoginThrottledError
from .frontend_client_contracts import FrontendRefusedError
from .frontend_profile_view_client import ProfileViewFrontend

if TYPE_CHECKING:
    from .enrollment_client import NativeEnrollmentClient


class FrontendCustodyClient(ProfileViewFrontend):
    """Handle profile custody and enrollment on the bound frontend connection."""

    _connection_purpose: Literal["fresh", "admission", "recovery", "enrollment", "bootstrap", "attendance"]

    def delete_profile(
        self, fingerprint: BucketDeletionFingerprint, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
    ) -> ProfileDeleted:
        """Confirm the named target's preflight on a fresh bootstrap connection."""
        if self._connection_purpose != "fresh" or self._session_id is not None:
            raise FrontendRefusedError(AutomationCustodyCode.CONFLICT.value)
        self._connection_purpose = "bootstrap"
        deadline = deadline_after(timeout)
        prepared = self._connection.delete_profile(
            ProfileDeletePrepare(
                request_id=uuid4(),
                profile_id=self.profile_id,
                frontend=self.frontend,
                fingerprint=fingerprint,
            ),
            deadline=deadline,
        )
        if isinstance(prepared, ProfileDeleteRefused):
            raise FrontendRefusedError(prepared.code)
        preparation = self._reply(prepared, ProfileDeletePrepared)
        try:
            completed = self._connection.delete_profile(
                ProfileDelete(
                    request_id=uuid4(),
                    profile_id=self.profile_id,
                    frontend=self.frontend,
                    confirmation=preparation.confirmation,
                ),
                deadline=deadline,
            )
            if isinstance(completed, ProfileDeleteRefused):
                raise FrontendRefusedError(
                    completed.code,
                    custody_transaction_id=preparation.confirmation.transaction_id,
                )
            return self._reply(completed, ProfileDeleted)
        except FrontendRefusedError as error:
            raise FrontendRefusedError(
                error.reason,
                sign_in=error.sign_in,
                custody_transaction_id=preparation.confirmation.transaction_id,
            ) from error
        except RefusalError as error:
            raise FrontendRefusedError(
                error.reason.value,
                custody_transaction_id=preparation.confirmation.transaction_id,
            ) from error

    def reset_password(
        self,
        *,
        recovery_code: bytearray,
        new_passphrase: bytearray,
        new_passphrase_confirmation: bytearray,
        timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS,
    ) -> PasswordResetCompleted:
        """Use recovery proof without local DEK custody or a live human session."""
        from cadrumo.application.user_profile.recovery_custody import ProfileRecoveryError
        from cadrumo.core.hashing import canonical_json_bytes

        payload = bytearray()
        try:
            if self._connection_purpose != "fresh" or self._session_id is not None:
                raise FrontendRefusedError(AutomationCustodyCode.CONFLICT.value)
            self._connection_purpose = "bootstrap"
            deadline = deadline_after(timeout)
            prepared = self._reply(
                self._connection.password_reset_prepare(
                    PasswordResetPrepare(request_id=uuid4(), profile_id=self.profile_id, frontend=self.frontend),
                    deadline=deadline,
                ),
                PasswordResetPrepared,
            )
            payload.extend(
                canonical_json_bytes(
                    {
                        "recovery_code": recovery_code.decode("utf-8"),
                        "new_passphrase": new_passphrase.decode("utf-8"),
                        "new_passphrase_confirmation": new_passphrase_confirmation.decode("utf-8"),
                    }
                )
            )
            reply = self._connection.password_reset(
                PasswordReset(
                    request_id=uuid4(),
                    profile_id=self.profile_id,
                    envelope_digest=prepared.envelope_digest,
                ),
                payload,
                deadline=deadline,
            )
            if isinstance(reply, PasswordResetRefused):
                if reply.code == "throttled":
                    if reply.remaining_seconds is None:
                        raise RefusalError(RefusalCode.INVALID_FRAME)
                    raise ProfileLoginThrottledError(remaining_seconds=int(reply.remaining_seconds))
                refusal = reply.password_refusal
                if reply.code == "invalid_password":
                    if refusal is None:
                        raise RefusalError(RefusalCode.INVALID_FRAME)
                    raise ProfileRecoveryError(
                        translated_message=refusal.translated_message,
                        context=dict(refusal.context),
                        password_refusal=refusal,
                    )
                raise ProfileRecoveryError(translated_message="application.user_profile.errors." + reply.code)
            return self._reply(reply, PasswordResetCompleted)
        finally:
            payload[:] = bytes(len(payload))
            recovery_code[:] = bytes(len(recovery_code))
            new_passphrase[:] = bytes(len(new_passphrase))
            new_passphrase_confirmation[:] = bytes(len(new_passphrase_confirmation))

    def recover_profile(
        self,
        password: bytearray,
        *,
        grants: frozenset[UUID] = frozenset(),
        timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS,
    ) -> AutomationResumeReceipt:
        """Resume selected grants on a dedicated unadmitted connection with one proof."""
        try:
            if self._connection_purpose != "fresh" or self._session_id is not None:
                raise FrontendRefusedError(AutomationCustodyCode.CONFLICT.value)
            self._connection_purpose = "recovery"
            deadline = deadline_after(timeout)
            prepared = self._reply(
                self._connection.recovery_prepare(
                    ProfileRecoveryPrepare(request_id=uuid4(), profile_id=self.profile_id, frontend=self.frontend),
                    deadline=deadline,
                ),
                ProfileRecoveryPrepared,
            )
            request = ProfileResume(
                request_id=uuid4(),
                profile_id=self.profile_id,
                frontend=self.frontend,
                lock_generation=prepared.lock_generation,
                grants=grants,
            )
            reply = self._reply(self._connection.resume_profile(request, password, deadline=deadline), ProfileResumed)
            return reply.receipt
        finally:
            password[:] = bytes(len(password))

    def prepare_enrollment(
        self, secrets_store: AutomationSecretStore, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
    ) -> NativeEnrollmentClient:
        """Prepare one pre-unlock client handoff on a fresh verified connection."""
        # Every runtime client imports this module; only an enrollment needs the credential custody stack.
        from .enrollment_client import NativeEnrollmentClient

        if self._connection_purpose != "fresh" or self._session_id is not None:
            raise FrontendRefusedError(AutomationCustodyCode.CONFLICT.value)
        self._connection_purpose = "enrollment"
        prepared = self._reply(
            self._connection.enrollment_prepare(
                EnrollmentPrepare(request_id=uuid4(), profile_id=self.profile_id, frontend=self.frontend),
                deadline=deadline_after(timeout),
            ),
            EnrollmentPrepared,
        )
        return NativeEnrollmentClient(connection=self._connection, prepared=prepared, secrets_store=secrets_store)

    def prepare_grant_change(
        self, secrets_store: AutomationSecretStore, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
    ) -> NativeEnrollmentClient:
        """Request review for this root key's grant without extending its lease.

        Rotation uses the same protected delivery protocol as first enrollment.
        Renewal and scope approval invalidate old leases; a fresh key login is
        required after the human's canonical approval receipt confirms the change.
        """
        from .enrollment_client import NativeEnrollmentClient

        if self._connection_purpose != "admission":
            raise FrontendRefusedError(AutomationCustodyCode.CONFLICT.value)
        prepared = self._reply(
            self._connection.enrollment_prepare(
                EnrollmentPrepare(
                    request_id=uuid4(),
                    profile_id=self.profile_id,
                    frontend=self.frontend,
                    session_id=self._session(),
                ),
                deadline=deadline_after(timeout),
            ),
            EnrollmentPrepared,
        )
        return NativeEnrollmentClient(connection=self._connection, prepared=prepared, secrets_store=secrets_store)

    def reconcile_enrollment(
        self, request_id: UUID, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
    ) -> AutomationReceiptProjection:
        """Recover terminal own-grant metadata without restoring an old offer.

        The runtime requires current root API-key authority. A receipt grants
        no authority and this call cannot submit, approve or redeliver a key.
        """
        request = EnrollmentReconcile(
            request_id=uuid4(),
            profile_id=self.profile_id,
            session_id=self._session(),
            enrollment_request_id=request_id,
        )
        reply = self._reply(
            self._connection.enrollment_inspect(request, deadline=deadline_after(timeout)), EnrollmentRecorded
        )
        if reply.receipt.stage not in {EnrollmentStage.COMPLETE, EnrollmentStage.DECLINED}:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return reply.receipt
