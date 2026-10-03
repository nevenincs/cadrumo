"""Bounded frontend access to one native-verified profile runtime connection."""

from __future__ import annotations

import asyncio
from typing import Literal, Self
from uuid import UUID, uuid4

from ...application.operations.registry import (
    OperationFrontendProjection,
)
from ...application.operations.secret_submission import OperationSecretRequirement
from ...application.runtime.access_management import (
    RuntimeAutomationDenied,
    RuntimeAutomationDeny,
    RuntimeProfileRecoveryPrepare,
    RuntimeProfileRecoveryPrepared,
    RuntimeProfileResume,
    RuntimeProfileResumed,
    RuntimeSessionInventory,
    RuntimeSessionInventoryReply,
)
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.deadline_budget import deadline_after
from ...application.runtime.enrollment_access import (
    RuntimeEnrollmentPrepare,
    RuntimeEnrollmentPrepared,
    RuntimeEnrollmentReconcile,
    RuntimeEnrollmentRecorded,
)
from ...application.runtime.operation_access import (
    RuntimeOperationAcknowledged,
    RuntimeOperationSecret,
)
from ...application.runtime.profile_access import (
    PROFILE_ADMISSION_TIMEOUT_SECONDS,
    RuntimeProfileLogin,
    RuntimeProfileStatus,
    RuntimeSessionRequest,
    RuntimeSessionsLocked,
)
from ...application.user_profile.access_contracts import AccessDenialCode
from ...application.user_profile.access_projections import PublicAccessSession
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationSecretStore
from ...application.user_profile.automation_enrollment import AutomationReceiptProjection, EnrollmentStage
from ...application.user_profile.automation_lifecycle import AutomationDenialKind, AutomationDenialReceipt
from ...application.user_profile.automation_lifecycle_service import AutomationResumeReceipt
from ...core.async_cleanup import await_cancellation_complete
from .enrollment_client import NativeEnrollmentClient
from .framing import VerifiedRuntimeConnection
from .frontend_client_contracts import RuntimeFrontendRefusedError
from .frontend_profile_view_client import RuntimeProfileViewFrontend
from .runtime_transport_cleanup import RuntimeTransportCleanup
from .startup import RuntimeLaunchDoor


class RuntimeFrontendClient(RuntimeProfileViewFrontend):
    """Own one exact profile/frontend connection and its connection-bound lease.

    The caller retains this object only for its frontend session. Every method
    derives the profile and session coordinates from a successful native login;
    copied IDs and ambient profile selection cannot retarget it. Blocking wire
    methods should be called off a UI event loop.
    """

    def __init__(
        self, connection: VerifiedRuntimeConnection, *, profile_id: UUID, frontend: OperationFrontendProjection
    ) -> None:
        """Bind one verified connection to an explicit immutable frontend target."""
        self._connection = connection
        self._profile_id = profile_id
        self._frontend = frontend
        self._session_id: UUID | None = None
        self._connection_purpose: Literal["fresh", "admission", "recovery", "enrollment"] = "fresh"

    @classmethod
    async def open(
        cls,
        launch: RuntimeLaunchDoor,
        *,
        profile_id: UUID,
        frontend: OperationFrontendProjection,
        timeout: float = 10,
    ) -> Self:
        """Use the canonical owner-verified launch door before any credential."""
        return cls(await launch.open(timeout=timeout), profile_id=profile_id, frontend=frontend)

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

    def cleanup_owner(self, *, primary_error: BaseException | None) -> RuntimeTransportCleanup:
        """Fence this client and retain one owner for its exact connection."""
        self._session_id = None
        retained = None if primary_error is None else primary_error.__dict__.get("_runtime_transport_cleanup")
        if isinstance(retained, RuntimeTransportCleanup) and (
            retained.resource is self or retained.resource is self._connection
        ):
            # The failed exchange already owns this native release. Rebinding
            # that same owner also clears frontend state without duplicating
            # the connection's retry path in a merged cleanup attachment.
            retained.resource = self
            return retained
        return RuntimeTransportCleanup(self)

    def _login(
        self, method: str, secret: bytearray, *, timeout: float, persist_receipt: bool = False
    ) -> RuntimeProfileStatus:
        try:
            if self._connection_purpose in {"recovery", "enrollment"}:
                raise RuntimeFrontendRefusedError(AutomationCustodyCode.CONFLICT.value)
            if self._session_id is not None:
                raise RuntimeFrontendRefusedError(AutomationCustodyCode.CONFLICT.value)
            self._connection_purpose = "admission"
            request = RuntimeProfileLogin.model_validate(
                {
                    "request_id": uuid4(),
                    "profile_id": self.profile_id,
                    "frontend": self.frontend,
                    "method": method,
                    "persist_receipt": persist_receipt,
                }
            )
            reply = self._reply(
                self._connection.login(request, secret, deadline=deadline_after(timeout)), RuntimeProfileStatus
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
                raise RuntimeFrontendRefusedError(
                    status.denial.value if status.denial is not None else AccessDenialCode.PROFILE_MISMATCH.value
                )
            self._session_id = status.session_id
            return reply
        finally:
            secret[:] = bytes(len(secret))

    def login_password(
        self, secret: bytearray, *, timeout: float = PROFILE_ADMISSION_TIMEOUT_SECONDS, persist_receipt: bool = False
    ) -> RuntimeProfileStatus:
        """Consume an explicit password only on the one-use verified secret frame."""
        return self._login("password", secret, timeout=timeout, persist_receipt=persist_receipt)

    def login_api_key(
        self, secret: bytearray, *, timeout: float = PROFILE_ADMISSION_TIMEOUT_SECONDS
    ) -> RuntimeProfileStatus:
        """Consume an explicit key without attempting human receipt fallback."""
        return self._login("api_key", secret, timeout=timeout)

    def resume_receipt(self, *, timeout: float = PROFILE_ADMISSION_TIMEOUT_SECONDS) -> RuntimeProfileStatus:
        """Borrow the exact profile's protected receipt proof for one verified frame."""
        from ...application.user_profile.login_session import borrow_profile_receipt_key

        with borrow_profile_receipt_key(bucket_id=self.profile_id) as proof:
            return self._login("receipt", proof, timeout=timeout)

    def submit_secret(
        self, requirement: OperationSecretRequirement, secret: bytearray, *, timeout: float = 20
    ) -> RuntimeOperationAcknowledged:
        """Consume a CLI/TUI secret through its exact operation's protected handoff."""
        try:
            if self.frontend not in {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}:
                raise RuntimeFrontendRefusedError(AccessDenialCode.FRONTEND_DENIED.value)
            return self._reply(
                self._connection.operation_secret(
                    RuntimeOperationSecret(
                        request_id=uuid4(),
                        profile_id=self.profile_id,
                        session_id=self._session(),
                        requirement=requirement,
                    ),
                    secret,
                    deadline=deadline_after(timeout),
                ),
                RuntimeOperationAcknowledged,
            )
        finally:
            secret[:] = bytes(len(secret))

    def _session_status(
        self, action: Literal["session_status", "session_refresh"], *, timeout: float
    ) -> RuntimeProfileStatus:
        session_id = self._session()
        reply = self._reply(
            self._connection.session(
                RuntimeSessionRequest(
                    action=action, request_id=uuid4(), profile_id=self.profile_id, session_id=session_id
                ),
                deadline=deadline_after(timeout),
            ),
            RuntimeProfileStatus,
        )
        if reply.status.session_id not in (None, session_id) or reply.status.profile_id not in (
            None,
            self.profile_id,
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return reply

    def status(self, *, timeout: float = 5) -> RuntimeProfileStatus:
        """Recheck the current connection-bound session without refreshing it."""
        return self._session_status("session_status", timeout=timeout)

    def refresh_api_key(self, *, timeout: float = 5) -> RuntimeProfileStatus:
        """Explicitly renew this connection's API-key lease under current authority."""
        reply = self._session_status("session_refresh", timeout=timeout)
        status = reply.status
        if status.denial is not None:
            raise RuntimeFrontendRefusedError(status.denial.value)
        if (
            not status.connected
            or not status.credential_authenticated
            or not status.profile_bound
            or status.profile_id != self.profile_id
            or status.session_id != self._session()
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return reply

    def lock(self, *, timeout: float = 5) -> RuntimeSessionsLocked:
        """Retire this lease through the runtime's own-session lock door."""
        session_id = self._session()
        reply = self._reply(
            self._connection.session(
                RuntimeSessionRequest(
                    action="session_lock", request_id=uuid4(), profile_id=self.profile_id, session_id=session_id
                ),
                deadline=deadline_after(timeout),
            ),
            RuntimeSessionsLocked,
        )
        if session_id not in reply.session_ids:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        self._session_id = None
        return reply

    def revoke_session(self, target_session_id: UUID, *, timeout: float = 5) -> RuntimeSessionsLocked:
        """Request an explicit session cascade; the runtime requires human authority."""
        session_id = self._session()
        reply = self._reply(
            self._connection.session(
                RuntimeSessionRequest(
                    action="session_lock",
                    request_id=uuid4(),
                    profile_id=self.profile_id,
                    session_id=session_id,
                    target_session_id=target_session_id,
                ),
                deadline=deadline_after(timeout),
            ),
            RuntimeSessionsLocked,
        )
        if session_id in reply.session_ids:
            self._session_id = None
        return reply

    def sessions(self, *, timeout: float = 5) -> tuple[PublicAccessSession, ...]:
        """Read only this session's authorized exact-profile public inventory."""
        request = RuntimeSessionInventory(request_id=uuid4(), profile_id=self.profile_id, session_id=self._session())
        reply = self._reply(
            self._connection.session_inventory(request, deadline=deadline_after(timeout)), RuntimeSessionInventoryReply
        )
        return reply.sessions

    def deny_automation(
        self, kind: AutomationDenialKind, *, target_id: UUID | None = None, timeout: float = 10
    ) -> AutomationDenialReceipt:
        """Request a durable authority reduction under this exact current session."""
        request = RuntimeAutomationDeny(
            request_id=uuid4(),
            profile_id=self.profile_id,
            session_id=self._session(),
            kind=kind,
            target_id=target_id,
        )
        reply = self._reply(
            self._connection.deny_automation(request, deadline=deadline_after(timeout)), RuntimeAutomationDenied
        )
        if kind is AutomationDenialKind.PROFILE_LOCK:
            self._session_id = None
        return reply.receipt

    def recover_profile(
        self, password: bytearray, *, grants: frozenset[UUID] = frozenset(), timeout: float = 20
    ) -> AutomationResumeReceipt:
        """Resume selected grants on a dedicated unadmitted connection with one proof."""
        try:
            if self._connection_purpose != "fresh" or self._session_id is not None:
                raise RuntimeFrontendRefusedError(AutomationCustodyCode.CONFLICT.value)
            self._connection_purpose = "recovery"
            deadline = deadline_after(timeout)
            prepared = self._reply(
                self._connection.recovery_prepare(
                    RuntimeProfileRecoveryPrepare(
                        request_id=uuid4(), profile_id=self.profile_id, frontend=self.frontend
                    ),
                    deadline=deadline,
                ),
                RuntimeProfileRecoveryPrepared,
            )
            request = RuntimeProfileResume(
                request_id=uuid4(),
                profile_id=self.profile_id,
                frontend=self.frontend,
                lock_generation=prepared.lock_generation,
                grants=grants,
            )
            reply = self._reply(
                self._connection.resume_profile(request, password, deadline=deadline), RuntimeProfileResumed
            )
            return reply.receipt
        finally:
            password[:] = bytes(len(password))

    def prepare_enrollment(
        self, secrets_store: AutomationSecretStore, *, timeout: float = 10
    ) -> NativeEnrollmentClient:
        """Prepare one pre-unlock client handoff on a fresh verified connection."""
        if self._connection_purpose != "fresh" or self._session_id is not None:
            raise RuntimeFrontendRefusedError(AutomationCustodyCode.CONFLICT.value)
        self._connection_purpose = "enrollment"
        prepared = self._reply(
            self._connection.enrollment_prepare(
                RuntimeEnrollmentPrepare(request_id=uuid4(), profile_id=self.profile_id, frontend=self.frontend),
                deadline=deadline_after(timeout),
            ),
            RuntimeEnrollmentPrepared,
        )
        return NativeEnrollmentClient(connection=self._connection, prepared=prepared, secrets_store=secrets_store)

    def prepare_grant_change(
        self, secrets_store: AutomationSecretStore, *, timeout: float = 10
    ) -> NativeEnrollmentClient:
        """Request review for this root key's grant without extending its lease.

        Rotation uses the same protected delivery protocol as first enrollment.
        Renewal and scope approval invalidate old leases; a fresh key login is
        required after the human's canonical approval receipt confirms the change.
        """
        if self._connection_purpose != "admission":
            raise RuntimeFrontendRefusedError(AutomationCustodyCode.CONFLICT.value)
        prepared = self._reply(
            self._connection.enrollment_prepare(
                RuntimeEnrollmentPrepare(
                    request_id=uuid4(),
                    profile_id=self.profile_id,
                    frontend=self.frontend,
                    session_id=self._session(),
                ),
                deadline=deadline_after(timeout),
            ),
            RuntimeEnrollmentPrepared,
        )
        return NativeEnrollmentClient(connection=self._connection, prepared=prepared, secrets_store=secrets_store)

    def reconcile_enrollment(self, request_id: UUID, *, timeout: float = 10) -> AutomationReceiptProjection:
        """Recover terminal own-grant metadata without restoring an old offer.

        The runtime requires current root API-key authority. A receipt grants
        no authority and this call cannot submit, approve or redeliver a key.
        """
        request = RuntimeEnrollmentReconcile(
            request_id=uuid4(),
            profile_id=self.profile_id,
            session_id=self._session(),
            enrollment_request_id=request_id,
        )
        reply = self._reply(
            self._connection.enrollment_inspect(request, deadline=deadline_after(timeout)), RuntimeEnrollmentRecorded
        )
        if reply.receipt.stage not in {EnrollmentStage.COMPLETE, EnrollmentStage.DECLINED}:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return reply.receipt
