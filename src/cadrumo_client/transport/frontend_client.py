"""Bounded frontend access to one native-verified profile runtime connection."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from threading import RLock
from typing import Final, Literal, Self
from uuid import UUID, uuid4

from cadrumo.application.bucket_deletion_contracts import BucketDeletionFingerprint
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.operations.secret_submission import OperationSecretRequirement
from cadrumo.application.user_profile.access_contracts import (
    AccessDenialCode,
    AccessScope,
    DisclosurePage,
    DisclosurePageRequest,
)
from cadrumo.application.user_profile.access_projections import PublicAccessSession
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationSecretStore
from cadrumo.application.user_profile.automation_enrollment import AutomationReceiptProjection, EnrollmentStage
from cadrumo.application.user_profile.automation_lifecycle import AutomationDenialKind, AutomationDenialReceipt
from cadrumo.core.async_cleanup import await_cancellation_complete
from cadrumo.core.profile_session import ProfileSessionRefusalReason

from ..contracts.access_management import (
    AutomationDenied,
    AutomationDeny,
    ProfileRecoveryPrepare,
    ProfileRecoveryPrepared,
    ProfileResume,
    ProfileResumed,
    SessionInventory,
    SessionInventoryReply,
)
from ..contracts.attendance import (
    AttendanceAsk,
    AttendanceDecide,
    AttendanceDecided,
    AttendanceInventory,
    AttendancePending,
)
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
from ..contracts.deadline_budget import MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS, deadline_after
from ..contracts.enrollment_access import EnrollmentPrepare, EnrollmentPrepared, EnrollmentReconcile, EnrollmentRecorded
from ..contracts.operation_access import OperationAcknowledged, OperationSecret
from ..contracts.profile_access import (
    PROFILE_ADMISSION_TIMEOUT_SECONDS,
    ProfileDisclosurePage,
    ProfileDisclosurePageRequest,
    ProfileLogin,
    ProfileStatus,
    SessionRequest,
    SessionsLocked,
)
from ..contracts.service_access import ServiceAdmission, ServiceConnected
from ..contracts.session_events import ConnectionEvent, LifecycleNotice
from ..contracts.sign_in import HumanSignedOut, SignInStatusReply, SignInStatusRequest
from .enrollment_client import NativeEnrollmentClient
from .framing import VerifiedConnection
from .frontend_client_contracts import FrontendRefusedError
from .frontend_profile_view_client import ProfileViewFrontend
from .startup import LaunchDoor
from .transport_cleanup import TransportCleanup

_CONNECTION_RECEIPT_REFUSALS: Final[dict[str, ProfileSessionRefusalReason]] = {
    # The runtime deleted a receipt that no longer signs this login in.
    AccessDenialCode.AUTHENTICATION_REQUIRED.value: ProfileSessionRefusalReason.ABSENT,
    # The denial does not distinguish idle from absolute expiry.
    AccessDenialCode.SESSION_EXPIRED.value: ProfileSessionRefusalReason.EXPIRED_IDLE,
    AccessDenialCode.CUSTODY_CHANGED.value: ProfileSessionRefusalReason.CUSTODY_CHANGED,
    AutomationCustodyCode.CREDENTIAL_REJECTED.value: ProfileSessionRefusalReason.TAMPERED,
}
"""Runtime denials of a presented receipt, as the receipt refusals callers already handle."""


class FrontendClient(ProfileViewFrontend):
    """Own one exact profile/frontend connection and its connection-bound lease.

    The caller retains this object only for its frontend session. Every method
    derives the profile and session coordinates from a successful native login;
    copied IDs and ambient profile selection cannot retarget it. Blocking wire
    methods should be called off a UI event loop.
    """

    def __init__(
        self,
        connection: VerifiedConnection,
        *,
        profile_id: UUID,
        frontend: OperationFrontendProjection,
        scope: AccessScope | None = None,
    ) -> None:
        """Bind one verified connection to an explicit immutable frontend target."""
        self._connection = connection
        self._profile_id = profile_id
        self._frontend = frontend
        self._scope = scope
        self._session_id: UUID | None = None
        self._connection_purpose: Literal["fresh", "admission", "recovery", "enrollment", "bootstrap", "attendance"] = (
            "fresh"
        )
        self._event_guard = RLock()
        self._retirement_epoch = 0
        self._retirement_receivers: list[Callable[[], None]] = []
        self._event_subscription: Callable[[], None] | None = None
        self._notice_receivers: list[Callable[[LifecycleNotice], None]] = []
        self._lifecycle_notice: LifecycleNotice | None = None

    def _session_retired(self, event: ConnectionEvent) -> None:
        if isinstance(event, LifecycleNotice):
            with self._event_guard:
                self._lifecycle_notice = event
                receivers = tuple(self._notice_receivers)
            for receive_notice in receivers:
                receive_notice(event)
            return
        if event.profile_id != self.profile_id:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        with self._event_guard:
            self._retirement_epoch += 1
            if self._session_id != event.session_id:
                return
            self._session_id = None
            receivers = tuple(self._retirement_receivers)
        for receive in receivers:
            receive()

    def _connection_failed(self) -> None:
        with self._event_guard:
            self._retirement_epoch += 1
            self._session_id = None
            receivers = tuple(self._retirement_receivers)
        for receive in receivers:
            receive()

    def subscribe_session_retirement(self, receive: Callable[[], None]) -> Callable[[], None]:
        """Subscribe a nonblocking private-view clearing callback, never a proof consumer."""
        if self._event_subscription is None:
            self._event_subscription = self._connection.subscribe_session_events(
                self._session_retired, disconnected=self._connection_failed
            )
        with self._event_guard:
            self._retirement_receivers.append(receive)
            inactive = self._session_id is None
        if inactive:
            receive()

        def unsubscribe() -> None:
            with self._event_guard:
                if receive in self._retirement_receivers:
                    self._retirement_receivers.remove(receive)

        return unsubscribe

    def subscribe_lifecycle_notices(self, receive: Callable[[LifecycleNotice], None]) -> Callable[[], None]:
        """Observe nonsecret notices without changing authentication or requesting manager actions."""
        if self._event_subscription is None:
            self._event_subscription = self._connection.subscribe_session_events(
                self._session_retired, disconnected=self._connection_failed
            )
        with self._event_guard:
            self._notice_receivers.append(receive)
            retained = self._lifecycle_notice
        if retained is not None:
            receive(retained)

        def unsubscribe() -> None:
            with self._event_guard:
                if receive in self._notice_receivers:
                    self._notice_receivers.remove(receive)

        return unsubscribe

    @classmethod
    async def open(
        cls,
        launch: LaunchDoor,
        *,
        profile_id: UUID,
        frontend: OperationFrontendProjection,
        timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS,
        scope: AccessScope | None = None,
    ) -> Self:
        """Use the canonical owner-verified launch door before any credential."""
        return cls(await launch.open(timeout=timeout), profile_id=profile_id, frontend=frontend, scope=scope)

    def __enter__(self) -> Self:
        """Retain this owned connection for a synchronous frontend scope."""
        return self

    def __exit__(self, *_exc: object) -> None:
        """Close this frontend's owned connection."""
        self.close()

    async def __aenter__(self) -> Self:
        """Retain this owned connection for an asynchronous frontend scope."""
        return self

    async def __aexit__(self, *_exc: object) -> None:
        """Close this frontend's owned connection."""
        await await_cancellation_complete(asyncio.to_thread(self.close), task_name="frontend-runtime-close")

    def close(self) -> None:
        """End this connection's lease without stopping the shared runtime."""
        self._session_id = None
        self._connection.close()

    def cleanup_owner(self, *, primary_error: BaseException | None) -> TransportCleanup:
        """Fence this client and retain one owner for its exact connection."""
        self._session_id = None
        retained = None if primary_error is None else primary_error.__dict__.get("_transport_cleanup")
        if isinstance(retained, TransportCleanup) and (
            retained.resource is self or retained.resource is self._connection
        ):
            # The failed exchange already owns this native release. Rebinding
            # that same owner also clears frontend state without duplicating
            # the connection's retry path in a merged cleanup attachment.
            retained.resource = self
            return retained
        return TransportCleanup(self)

    def _login(self, method: str, secret: bytearray, *, timeout: float, persist_receipt: bool = False) -> ProfileStatus:
        try:
            if self._connection_purpose in {"recovery", "enrollment", "bootstrap"}:
                raise FrontendRefusedError(AutomationCustodyCode.CONFLICT.value)
            if self._session_id is not None:
                raise FrontendRefusedError(AutomationCustodyCode.CONFLICT.value)
            self._connection_purpose = "admission"
            document: dict[str, object] = {
                "request_id": uuid4(),
                "profile_id": self.profile_id,
                "frontend": self.frontend,
                "method": method,
                "persist_receipt": persist_receipt,
            }
            if self._scope is not None:
                document["scope"] = self._scope.model_dump(mode="python")
            request = ProfileLogin.model_validate(document)
            with self._event_guard:
                epoch = self._retirement_epoch
            reply = self._reply(
                self._connection.login(request, secret, deadline=deadline_after(timeout)), ProfileStatus
            )
            status = reply.status
            if (
                status.denial is not None
                or not status.connected
                or not status.credential_authenticated
                or not status.profile_bound
                or status.profile_id != self.profile_id
                or status.session_id is None
            ):
                raise FrontendRefusedError(
                    status.denial.value if status.denial is not None else AccessDenialCode.PROFILE_MISMATCH.value
                )
            if self._event_subscription is None:
                self._event_subscription = self._connection.subscribe_session_events(
                    self._session_retired, disconnected=self._connection_failed
                )
            with self._event_guard:
                if epoch != self._retirement_epoch:
                    raise FrontendRefusedError(AccessDenialCode.SESSION_INACTIVE.value)
                self._session_id = status.session_id
            return reply
        finally:
            secret[:] = bytes(len(secret))

    def login_password(
        self, secret: bytearray, *, timeout: float = PROFILE_ADMISSION_TIMEOUT_SECONDS, persist_receipt: bool = False
    ) -> ProfileStatus:
        """Consume an explicit password only on the one-use verified secret frame."""
        return self._login("password", secret, timeout=timeout, persist_receipt=persist_receipt)

    def login_api_key(self, secret: bytearray, *, timeout: float = PROFILE_ADMISSION_TIMEOUT_SECONDS) -> ProfileStatus:
        """Consume an explicit key without attempting human receipt fallback."""
        return self._login("api_key", secret, timeout=timeout)

    def resume_receipt(self, *, timeout: float = PROFILE_ADMISSION_TIMEOUT_SECONDS) -> ProfileStatus:
        """Present the exact profile's keychain-held receipt proof on one verified frame.

        This process reads only the proof and the receipt locator. It never
        unwraps, extends or deletes the receipt: the runtime verifies the
        proof against this connection's login and the current sign-in
        generation, and deletes a receipt it refuses. A runtime refusal of the
        receipt returns as :class:`ProfileReceiptRefusedError`, like a local
        one, so callers keep one fallback path.
        """
        from cadrumo.application.user_profile.login_session import (
            ProfileReceiptRefusedError,
            borrow_profile_receipt_key,
        )

        with borrow_profile_receipt_key(bucket_id=self.profile_id) as proof:
            try:
                return self._login("receipt", proof, timeout=timeout)
            except FrontendRefusedError as error:
                reason = (
                    error.sign_in.reason
                    if error.sign_in is not None and isinstance(error.sign_in.reason, ProfileSessionRefusalReason)
                    else _CONNECTION_RECEIPT_REFUSALS.get(error.reason)
                )
                if reason is None:
                    raise
                raise ProfileReceiptRefusedError(
                    reason, binding=None if error.sign_in is None else error.sign_in.binding
                ) from error

    def request_attendance(
        self, *, timeout: float = PROFILE_ADMISSION_TIMEOUT_SECONDS
    ) -> AttendancePending | ProfileStatus:
        """Ask to be attended by the person's held sign-in; nothing is admitted until the person decides.

        A connection the person already approved under a sign-in that is
        still live is admitted again at once, and the status says so.
        """
        return self._attendance(self._attendance_ask("attendance_request", None), timeout=timeout)

    def attendance_status(
        self, attendance_id: UUID, *, timeout: float = PROFILE_ADMISSION_TIMEOUT_SECONDS
    ) -> AttendancePending | ProfileStatus:
        """Observe this connection's own ask; an approved one binds the attended session here."""
        return self._attendance(self._attendance_ask("attendance_status", attendance_id), timeout=timeout)

    def service_admission(
        self, recipient_connection_id: UUID, service_id: str, *, request_id: UUID | None = None, timeout: float = 10
    ) -> ServiceConnected:
        """Approve an exact verified installed peer under this held human session."""
        reply = self._connection.service_access(
            ServiceAdmission(
                request_id=request_id or uuid4(),
                profile_id=self.profile_id,
                session_id=self._session(),
                recipient_connection_id=recipient_connection_id,
                service_id=service_id,
            ),
            deadline=deadline_after(timeout),
        )
        return self._reply(reply, ServiceConnected)

    def attendance_inventory(self, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS) -> AttendanceInventory:
        """List the asks pending for this person's profile, as the holder of its live sign-in."""
        return self._reply(
            self._connection.attendance(
                AttendanceDecide(
                    action="attendance_inventory",
                    request_id=uuid4(),
                    profile_id=self.profile_id,
                    session_id=self._session(),
                ),
                deadline=deadline_after(timeout),
            ),
            AttendanceInventory,
        )

    def decide_attendance(
        self, attendance_id: UUID, *, approve: bool, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
    ) -> AttendanceDecided:
        """Approve or decline one exact ask under this connection's own human session."""
        return self._reply(
            self._connection.attendance(
                AttendanceDecide(
                    action="attendance_decision",
                    request_id=uuid4(),
                    profile_id=self.profile_id,
                    session_id=self._session(),
                    attendance_id=attendance_id,
                    approve=approve,
                ),
                deadline=deadline_after(timeout),
            ),
            AttendanceDecided,
        )

    def _attendance_ask(
        self, action: Literal["attendance_request", "attendance_status"], attendance_id: UUID | None
    ) -> AttendanceAsk:
        if self._connection_purpose not in {"fresh", "attendance"} or (
            self._session_id is not None and self._connection_purpose != "attendance"
        ):
            raise FrontendRefusedError(AutomationCustodyCode.CONFLICT.value)
        # An attended connection asks again when its short lease ends. The runtime answers with the
        # child it still holds, or issues a new one under the same approval while the person's session lives.
        self._session_id = None
        self._connection_purpose = "attendance"
        return AttendanceAsk(
            action=action,
            request_id=uuid4(),
            profile_id=self.profile_id,
            frontend=self.frontend,
            scope=self._scope,
            attendance_id=attendance_id,
        )

    def _attendance(self, request: AttendanceAsk, *, timeout: float) -> AttendancePending | ProfileStatus:
        with self._event_guard:
            epoch = self._retirement_epoch
        reply = self._connection.attendance(request, deadline=deadline_after(timeout))
        if isinstance(reply, AttendancePending):
            return reply
        admitted = self._reply(reply, ProfileStatus)
        status = admitted.status
        if (
            status.denial is not None
            or not status.connected
            or not status.profile_bound
            or status.profile_id != self.profile_id
            or status.session_id is None
        ):
            raise FrontendRefusedError(
                status.denial.value if status.denial is not None else AccessDenialCode.PROFILE_MISMATCH.value
            )
        if self._event_subscription is None:
            self._event_subscription = self._connection.subscribe_session_events(
                self._session_retired, disconnected=self._connection_failed
            )
        with self._event_guard:
            if epoch != self._retirement_epoch:
                raise FrontendRefusedError(AccessDenialCode.SESSION_INACTIVE.value)
            self._session_id = status.session_id
        return admitted

    def submit_secret(
        self,
        requirement: OperationSecretRequirement,
        secret: bytearray,
        *,
        timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS,
    ) -> OperationAcknowledged:
        """Consume a secret through its exact operation's protected handoff."""
        try:
            return self._reply(
                self._connection.operation_secret(
                    OperationSecret(
                        request_id=uuid4(),
                        profile_id=self.profile_id,
                        session_id=self._session(),
                        requirement=requirement,
                    ),
                    secret,
                    deadline=deadline_after(timeout),
                ),
                OperationAcknowledged,
            )
        finally:
            secret[:] = bytes(len(secret))

    def _session_status(self, action: Literal["session_status", "session_refresh"], *, timeout: float) -> ProfileStatus:
        session_id = self._session()
        reply = self._reply(
            self._connection.session(
                SessionRequest(action=action, request_id=uuid4(), profile_id=self.profile_id, session_id=session_id),
                deadline=deadline_after(timeout),
            ),
            ProfileStatus,
        )
        if reply.status.session_id not in (None, session_id) or reply.status.profile_id not in (
            None,
            self.profile_id,
        ):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return reply

    def status(self, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS) -> ProfileStatus:
        """Recheck the current connection-bound session without refreshing it."""
        return self._session_status("session_status", timeout=timeout)

    def disclosure_page(
        self, request: DisclosurePageRequest, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
    ) -> DisclosurePage:
        """Read one page of the disclosures this session's status counts."""
        reply = self._reply(
            self._connection.disclosure_page(
                ProfileDisclosurePageRequest(
                    request_id=uuid4(), profile_id=self.profile_id, session_id=self._session(), page=request
                ),
                deadline=deadline_after(timeout),
            ),
            ProfileDisclosurePage,
        )
        if reply.page.offset != request.offset or request.expected_digest not in (None, reply.page.disclosure_digest):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return reply.page

    def sign_in_status(self, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS) -> SignInStatusReply:
        """Observe shared presence without borrowing proof or authenticating this connection."""
        return self._reply(
            self._connection.sign_in_status(
                SignInStatusRequest(request_id=uuid4(), profile_id=self.profile_id),
                deadline=deadline_after(timeout),
            ),
            SignInStatusReply,
        )

    def human_sign_out(self, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS) -> HumanSignedOut:
        """Revoke profile-wide human access using this connection's proven human session."""
        if self._session_id is None:
            self.resume_receipt(timeout=timeout)
        result = self._reply(
            self._connection.session(
                SessionRequest(
                    action="human_sign_out", request_id=uuid4(), profile_id=self.profile_id, session_id=self._session()
                ),
                deadline=deadline_after(timeout),
            ),
            HumanSignedOut,
        )
        if result.profile_id != self.profile_id:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._session_id = None
        return result

    def refresh_api_key(self, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS) -> ProfileStatus:
        """Explicitly renew this connection's API-key lease under current authority."""
        reply = self._session_status("session_refresh", timeout=timeout)
        status = reply.status
        if status.denial is not None:
            raise FrontendRefusedError(status.denial.value)
        if (
            not status.connected
            or not status.credential_authenticated
            or not status.profile_bound
            or status.profile_id != self.profile_id
            or status.session_id != self._session()
        ):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        return reply

    def lock(self, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS) -> SessionsLocked:
        """Retire this lease through the runtime's own-session lock door."""
        session_id = self._session()
        reply = self._reply(
            self._connection.session(
                SessionRequest(
                    action="session_lock", request_id=uuid4(), profile_id=self.profile_id, session_id=session_id
                ),
                deadline=deadline_after(timeout),
            ),
            SessionsLocked,
        )
        if session_id not in reply.session_ids:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        self._session_id = None
        return reply

    def revoke_session(
        self, target_session_id: UUID, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS
    ) -> SessionsLocked:
        """Request an explicit session cascade; the runtime requires human authority."""
        session_id = self._session()
        reply = self._reply(
            self._connection.session(
                SessionRequest(
                    action="session_lock",
                    request_id=uuid4(),
                    profile_id=self.profile_id,
                    session_id=session_id,
                    target_session_id=target_session_id,
                ),
                deadline=deadline_after(timeout),
            ),
            SessionsLocked,
        )
        if session_id in reply.session_ids:
            self._session_id = None
        return reply

    def sessions(self, *, timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS) -> tuple[PublicAccessSession, ...]:
        """Read only this session's authorized exact-profile public inventory."""
        request = SessionInventory(request_id=uuid4(), profile_id=self.profile_id, session_id=self._session())
        reply = self._reply(
            self._connection.session_inventory(request, deadline=deadline_after(timeout)), SessionInventoryReply
        )
        return reply.sessions

    def deny_automation(
        self,
        kind: AutomationDenialKind,
        *,
        target_id: UUID | None = None,
        timeout: float = MAX_CONNECTION_EXCHANGE_TIMEOUT_SECONDS,
    ) -> AutomationDenialReceipt:
        """Request a durable authority reduction under this exact current session."""
        request = AutomationDeny(
            request_id=uuid4(),
            profile_id=self.profile_id,
            session_id=self._session(),
            kind=kind,
            target_id=target_id,
        )
        reply = self._reply(
            self._connection.deny_automation(request, deadline=deadline_after(timeout)), AutomationDenied
        )
        if kind is AutomationDenialKind.PROFILE_LOCK:
            self._session_id = None
        return reply.receipt

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
        from cadrumo.application.user_profile.login_session import ProfileLoginThrottledError
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
