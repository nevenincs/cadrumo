"""Cancellation-complete worker access to a runtime-held profile authorization fence."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import ExitStack, asynccontextmanager
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

from pydantic import SecretBytes

from ...application.runtime.approval_binding import RuntimeApprovalBinding
from ...application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.profile_access import RuntimeAccessRefusal
from ...application.runtime.profile_worker import ProfileWorkerIdentity
from ...application.runtime.worker_authorization import (
    AUTHORITY_SECTION_MAXIMUM_SECONDS,
    WorkerAuthorityRequest,
    WorkerAuthorizationAcknowledgement,
    WorkerAuthorizationPermit,
    WorkerAuthorizationRelease,
    WorkerAuthorizationReleased,
    WorkerAuthorizationReply,
    WorkerAuthorizationRequest,
    WorkerAutomationInventoryPermit,
    WorkerAutomationInventoryRequest,
    WorkerResponseScopePermit,
    WorkerResponseScopeRequest,
)
from ...application.runtime.worker_enrollment import (
    WorkerApprovalPhaseResult,
    WorkerApprovalPublication,
    WorkerApprovalPublicationPhase,
    WorkerApprovalPublished,
    WorkerApprovalReady,
    WorkerApprovalRequest,
)
from ...application.user_profile.access_contracts import AccessAction, AccessDenialCode
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...application.user_profile.automation_enrollment import AutomationInventory, EnrollmentTransition
from ...application.user_profile.automation_operations import (
    AUTOMATION_APPROVE_OPERATION_DEFINITION_ID,
    AUTOMATION_DECLINE_OPERATION_DEFINITION_ID,
)
from ...core.async_cleanup import await_cancellation_complete, close_async_resources
from ...core.time.clock import now
from .framing import VerifiedRuntimeConnection, read_document, write_document, write_secret
from .posix import PosixRuntimeChannel
from .worker_authorization import worker_authorization_namespace
from .worker_transport import WorkerChannel, worker_endpoint


class WorkerAuthorizationLease:
    """One native connection with explicit acquisition/release, never an ordinary result."""

    def __init__(
        self,
        *,
        identity: ProfileWorkerIdentity,
        root: Path,
        parent_pid: int,
        request: WorkerAuthorityRequest | WorkerAutomationInventoryRequest,
    ) -> None:
        """Capture only trusted worker routing and registered operation coordinates."""
        self.identity, self.root, self.parent_pid, self.request = identity, root, parent_pid, request
        self._channel: WorkerChannel | None = None
        self._permit: WorkerAuthorizationPermit | WorkerResponseScopePermit | WorkerAutomationInventoryPermit | None = (
            None
        )
        self._deadline = 0.0
        self._publication_sent = False

    def acquire(self) -> None:
        """Authenticate the retained native parent before requesting a held fence."""
        endpoint = worker_endpoint(
            storage_root=self.root, worker_namespace=worker_authorization_namespace(self.identity.worker_id)
        )
        channel: WorkerChannel | None = None
        try:
            channel = endpoint.connect(timeout=5)
            if (
                channel.peer.process_id != self.parent_pid
                or channel.peer.os_owner_id != self.identity.binding.os_owner_id
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            if isinstance(channel, PosixRuntimeChannel):
                with channel.capture_peer_pidfd():
                    pass
            deadline = time.monotonic() + AUTHORITY_SECTION_MAXIMUM_SECONDS + 5
            verified = VerifiedRuntimeConnection(
                channel,
                expected=RuntimeClientHello(
                    product_version=version("cadrumo"), storage_identity=endpoint.storage_identity
                ),
                deadline=deadline,
            )
            if verified.hello.boot_id != self.identity.runtime_boot_id:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            write_document(channel, self.request, deadline=deadline)
            reply = read_document(channel, WorkerAuthorizationReply, deadline=deadline).root
            if reply.request_id != self.request.request_id:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            if isinstance(reply, RuntimeAccessRefusal):
                if (
                    reply.runtime_boot_id != self.identity.runtime_boot_id
                    or reply.connection_id != self.request.connection_id
                ):
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                write_document(
                    channel, WorkerAuthorizationAcknowledgement(request_id=self.request.request_id), deadline=deadline
                )
                if isinstance(reply.code, AccessDenialCode):
                    raise ProfileAccessRefusedError(reply.code)
                if isinstance(reply.code, AutomationCustodyCode):
                    raise AutomationCustodyError(reply.code)
                raise RuntimeRefusalError(reply.code)
            if (
                not isinstance(
                    reply, WorkerAuthorizationPermit | WorkerResponseScopePermit | WorkerAutomationInventoryPermit
                )
                or reply.runtime_boot_id != self.identity.runtime_boot_id
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            if (
                isinstance(self.request, WorkerResponseScopeRequest) != isinstance(reply, WorkerResponseScopePermit)
                or isinstance(self.request, WorkerAutomationInventoryRequest)
                != isinstance(reply, WorkerAutomationInventoryPermit)
                or isinstance(self.request, WorkerAuthorizationRequest) != isinstance(reply, WorkerAuthorizationPermit)
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            remaining = (reply.expires_at - now()).total_seconds()
            if not 0 < remaining <= AUTHORITY_SECTION_MAXIMUM_SECONDS:
                raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)
            self._deadline = time.monotonic() + remaining
            self._permit, self._channel = reply, channel
            channel = None
        finally:
            if channel is not None:
                channel.close()
            endpoint.close()

    def inventory(self) -> AutomationInventory:
        """Return only an exact inventory permit, never an ordinary guard reply."""
        if not isinstance(self.request, WorkerAutomationInventoryRequest) or not isinstance(
            self._permit, WorkerAutomationInventoryPermit
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return self._permit.inventory

    def publish_approval(
        self, binding: RuntimeApprovalBinding, phase: WorkerApprovalPublicationPhase
    ) -> EnrollmentTransition | None:
        """Send one publication over this exact held COMMIT channel, without reacquiring it."""
        channel, permit, request = self._channel, self._permit, self.request
        expected = (
            AUTOMATION_DECLINE_OPERATION_DEFINITION_ID
            if phase == "decline"
            else AUTOMATION_APPROVE_OPERATION_DEFINITION_ID
        )
        if (
            channel is None
            or not isinstance(permit, WorkerAuthorizationPermit)
            or not isinstance(request, WorkerAuthorizationRequest)
            or request.request.action is not AccessAction.COMMIT
            or request.request.definition_id != expected
            or self._publication_sent
            or binding.operation_id != request.operation_id
            or binding.session_id != request.session_id
            or binding.connection_id != request.connection_id
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        command = WorkerApprovalPublication(
            request_id=request.request_id,
            permit_id=permit.permit_id,
            command_id=uuid4(),
            binding=binding,
            phase=phase,
        )
        self._publication_sent = True
        write_document(channel, command, deadline=self._deadline)
        reply = read_document(channel, WorkerAuthorizationReply, deadline=self._deadline).root
        if (
            not isinstance(reply, RuntimeAccessRefusal | WorkerApprovalPublished)
            or reply.request_id != request.request_id
            or reply.runtime_boot_id != self.identity.runtime_boot_id
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if isinstance(reply, RuntimeAccessRefusal):
            if reply.connection_id != request.connection_id:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            if isinstance(reply.code, AccessDenialCode):
                raise ProfileAccessRefusedError(reply.code)
            if isinstance(reply.code, AutomationCustodyCode):
                raise AutomationCustodyError(reply.code)
            raise RuntimeRefusalError(reply.code)
        if (
            not isinstance(reply, WorkerApprovalPublished)
            or reply.permit_id != permit.permit_id
            or reply.command_id != command.command_id
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        if reply.receipt is None:
            if phase != "commit_review":
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            return None
        if (
            reply.receipt.profile_id != binding.profile_binding.profile_id
            or reply.receipt.request_id != binding.enrollment_request_id
            or reply.receipt.review_digest != binding.review_digest
        ):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        return EnrollmentTransition(receipt=reply.receipt, published=reply.published)

    def release(self) -> None:
        """Acknowledge body completion on the exact channel, preserving uncertain failure."""
        channel, permit = self._channel, self._permit
        self._channel, self._permit = None, None
        if channel is None:
            return
        try:
            if permit is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            write_document(
                channel,
                WorkerAuthorizationRelease(request_id=self.request.request_id, permit_id=permit.permit_id),
                deadline=self._deadline,
            )
            reply = read_document(channel, WorkerAuthorizationReply, deadline=self._deadline).root
            if (
                not isinstance(reply, WorkerAuthorizationReleased)
                or reply.request_id != self.request.request_id
                or reply.permit_id != permit.permit_id
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            write_document(
                channel, WorkerAuthorizationAcknowledgement(request_id=self.request.request_id), deadline=self._deadline
            )
        finally:
            channel.close()

    async def close(self) -> None:
        """Complete blocking native release through the existing cleanup owner."""
        await asyncio.to_thread(self.release)


class WorkerAuthorizationClient:
    """Use a distinct connection for each concurrent protected body."""

    def __init__(self, *, identity: ProfileWorkerIdentity, root: Path, parent_pid: int) -> None:
        """Bind one immutable worker to its verified runtime parent."""
        self.identity, self.root, self.parent_pid = identity, root, parent_pid

    @asynccontextmanager
    async def guard(self, request: WorkerAuthorityRequest) -> AsyncGenerator[WorkerAuthorizationLease]:
        """Finish acquisition and release even when the operation task is cancelled."""
        lease = WorkerAuthorizationLease(
            identity=self.identity, root=self.root, parent_pid=self.parent_pid, request=request
        )
        try:
            await await_cancellation_complete(asyncio.to_thread(lease.acquire), task_name="worker-authority-acquire")
            yield lease
        finally:
            await close_async_resources(lease, task_name="worker-authority-release")

    async def inventory(self, request: WorkerAutomationInventoryRequest) -> AutomationInventory:
        """Read held human inventory and finish its native release before returning."""
        lease = WorkerAuthorizationLease(
            identity=self.identity, root=self.root, parent_pid=self.parent_pid, request=request
        )
        try:
            await await_cancellation_complete(asyncio.to_thread(lease.acquire), task_name="worker-inventory-acquire")
            return lease.inventory()
        finally:
            await close_async_resources(lease, task_name="worker-inventory-release")

    async def approval_phase(self, request: WorkerApprovalRequest, password: SecretBytes | None = None) -> bool | None:
        """Complete an unguarded proof or recipient phase on a separately verified channel."""
        return await await_cancellation_complete(
            asyncio.to_thread(self._approval_phase, request, password), task_name="worker-approval-phase"
        )

    def _approval_phase(self, request: WorkerApprovalRequest, password: SecretBytes | None) -> bool | None:
        if (request.phase == "prepare") != (password is not None):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        endpoint = worker_endpoint(
            storage_root=self.root, worker_namespace=worker_authorization_namespace(self.identity.worker_id)
        )
        with ExitStack() as resources:
            resources.callback(endpoint.close)
            channel = endpoint.connect(timeout=5)
            resources.callback(channel.close)
            if (
                channel.peer.process_id != self.parent_pid
                or channel.peer.os_owner_id != self.identity.binding.os_owner_id
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            if isinstance(channel, PosixRuntimeChannel):
                with channel.capture_peer_pidfd():
                    pass
            deadline = time.monotonic() + 60
            verified = VerifiedRuntimeConnection(
                channel,
                expected=RuntimeClientHello(
                    product_version=version("cadrumo"), storage_identity=endpoint.storage_identity
                ),
                deadline=deadline,
            )
            if verified.hello.boot_id != self.identity.runtime_boot_id:
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            write_document(channel, request, deadline=deadline)
            reply = read_document(channel, WorkerAuthorizationReply, deadline=deadline).root
            if (
                not isinstance(reply, RuntimeAccessRefusal | WorkerApprovalReady | WorkerApprovalPhaseResult)
                or reply.request_id != request.request_id
                or reply.runtime_boot_id != self.identity.runtime_boot_id
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            if isinstance(reply, WorkerApprovalReady):
                if request.phase != "prepare" or password is None:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                write_secret(channel, bytearray(password.get_secret_value()), deadline=deadline)
                reply = read_document(channel, WorkerAuthorizationReply, deadline=deadline).root
            if (
                not isinstance(reply, RuntimeAccessRefusal | WorkerApprovalPhaseResult)
                or reply.request_id != request.request_id
                or reply.runtime_boot_id != self.identity.runtime_boot_id
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            if isinstance(reply, RuntimeAccessRefusal):
                if reply.connection_id != request.connection_id:
                    raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                write_document(
                    channel, WorkerAuthorizationAcknowledgement(request_id=request.request_id), deadline=deadline
                )
                if isinstance(reply.code, AccessDenialCode):
                    raise ProfileAccessRefusedError(reply.code)
                if isinstance(reply.code, AutomationCustodyCode):
                    raise AutomationCustodyError(reply.code)
                raise RuntimeRefusalError(reply.code)
            if not isinstance(reply, WorkerApprovalPhaseResult) or (
                (request.phase == "inspect_recipient") != (reply.needs_candidate is not None)
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            write_document(
                channel, WorkerAuthorizationAcknowledgement(request_id=request.request_id), deadline=deadline
            )
            return reply.needs_candidate
