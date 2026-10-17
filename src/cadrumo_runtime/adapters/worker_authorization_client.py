"""Cancellation-complete acquisition and approval requests to the retained runtime parent."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import ExitStack, asynccontextmanager
from importlib.metadata import version
from pathlib import Path
from uuid import uuid4

from pydantic import SecretBytes

from cadrumo.application.operations.models import OperationId
from cadrumo.application.user_profile.automation_enrollment import AutomationInventory
from cadrumo.core.async_cleanup import await_cancellation_complete, close_async_resources
from cadrumo_client.contracts.contracts import ClientHello, RefusalCode, RefusalError
from cadrumo_client.contracts.profile_access import AccessRefusal
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport.frame_io import read_document, write_document, write_secret
from cadrumo_client.transport.framing import VerifiedConnection
from cadrumo_client.transport.posix_channel import PosixChannel
from cadrumo_runtime.contracts.worker_authorization import (
    WorkerAuthorityRequest,
    WorkerAuthorizationAcknowledgement,
    WorkerAuthorizationPermit,
    WorkerAuthorizationReleased,
    WorkerAuthorizationReply,
    WorkerAutomationInventoryPermit,
    WorkerAutomationInventoryRequest,
    WorkerOperationsAdvanced,
    WorkerResponseScopePermit,
)
from cadrumo_runtime.contracts.worker_enrollment import (
    WorkerApprovalPhaseResult,
    WorkerApprovalPublished,
    WorkerApprovalReady,
    WorkerApprovalRequest,
)

from .native_peer import require_live_native_peer
from .worker_authorization import worker_authorization_namespace
from .worker_authorization_lease import WorkerAuthorizationLease
from .worker_authorization_refusals import raise_worker_access_refusal
from .worker_transport import WorkerChannel, worker_endpoint


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

    def operations_advanced(self, operation_ids: tuple[OperationId, ...]) -> None:
        """Report committed operations to the runtime parent; it acknowledges and grants nothing."""
        report = WorkerOperationsAdvanced(request_id=uuid4(), operation_ids=operation_ids)
        with ExitStack() as resources:
            channel = self._verified_parent_channel(resources, time.monotonic() + 5)
            deadline = time.monotonic() + 5
            write_document(channel, report, deadline=deadline)
            acknowledged = read_document(channel, WorkerAuthorizationAcknowledgement, deadline=deadline)
            if acknowledged.request_id != report.request_id:
                raise RefusalError(RefusalCode.INVALID_FRAME)

    def _verified_parent_channel(self, resources: ExitStack, deadline: float) -> WorkerChannel:
        """Connect to this worker's runtime parent and prove both ends before any request."""
        endpoint = worker_endpoint(
            storage_root=self.root, worker_namespace=worker_authorization_namespace(self.identity.worker_id)
        )
        resources.callback(endpoint.close)
        channel = endpoint.connect(timeout=5)
        resources.callback(channel.close)
        if channel.peer.process_id != self.parent_pid or channel.peer.os_owner_id != self.identity.binding.os_owner_id:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        if isinstance(channel, PosixChannel):
            require_live_native_peer(channel)
        verified = VerifiedConnection(
            channel,
            expected=ClientHello(product_version=version("cadrumo"), storage_identity=endpoint.storage_identity),
            deadline=deadline,
        )
        if verified.hello.boot_id != self.identity.runtime_boot_id:
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        return channel

    def _approval_phase(self, request: WorkerApprovalRequest, password: SecretBytes | None) -> bool | None:
        if (request.phase == "prepare") != (password is not None):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        with ExitStack() as resources:
            deadline = time.monotonic() + 60
            channel = self._verified_parent_channel(resources, deadline)
            write_document(channel, request, deadline=deadline)
            reply = read_document(channel, WorkerAuthorizationReply, deadline=deadline).root
            reply = _complete_password_phase(channel, reply, request, password, self.identity, deadline)
            return _accepted_approval_phase_reply(channel, reply, request, self.identity, deadline)


def _complete_password_phase(
    channel: WorkerChannel,
    reply: AccessRefusal
    | WorkerAuthorizationPermit
    | WorkerResponseScopePermit
    | WorkerAutomationInventoryPermit
    | WorkerAuthorizationReleased
    | WorkerApprovalReady
    | WorkerApprovalPhaseResult
    | WorkerApprovalPublished,
    request: WorkerApprovalRequest,
    password: SecretBytes | None,
    identity: ProfileWorkerIdentity,
    deadline: float,
) -> (
    AccessRefusal
    | WorkerAuthorizationPermit
    | WorkerResponseScopePermit
    | WorkerAutomationInventoryPermit
    | WorkerAuthorizationReleased
    | WorkerApprovalReady
    | WorkerApprovalPhaseResult
    | WorkerApprovalPublished
):
    """Send fresh proof only after the exact worker has acknowledged preparation."""
    if (
        not isinstance(reply, AccessRefusal | WorkerApprovalReady | WorkerApprovalPhaseResult)
        or reply.request_id != request.request_id
        or reply.runtime_boot_id != identity.runtime_boot_id
    ):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    if isinstance(reply, WorkerApprovalReady):
        if request.phase != "prepare" or password is None:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        write_secret(channel, bytearray(password.get_secret_value()), deadline=deadline)
        reply = read_document(channel, WorkerAuthorizationReply, deadline=deadline).root
    return reply


def _accepted_approval_phase_reply(
    channel: WorkerChannel,
    reply: AccessRefusal
    | WorkerAuthorizationPermit
    | WorkerResponseScopePermit
    | WorkerAutomationInventoryPermit
    | WorkerAuthorizationReleased
    | WorkerApprovalReady
    | WorkerApprovalPhaseResult
    | WorkerApprovalPublished,
    request: WorkerApprovalRequest,
    identity: ProfileWorkerIdentity,
    deadline: float,
) -> bool | None:
    """Acknowledge only the addressed final phase result or exact received refusal."""
    if (
        not isinstance(reply, AccessRefusal | WorkerApprovalPhaseResult)
        or reply.request_id != request.request_id
        or reply.runtime_boot_id != identity.runtime_boot_id
    ):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    if isinstance(reply, AccessRefusal):
        if reply.connection_id != request.connection_id:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        write_document(channel, WorkerAuthorizationAcknowledgement(request_id=request.request_id), deadline=deadline)
        raise_worker_access_refusal(reply)
    if not isinstance(reply, WorkerApprovalPhaseResult) or (
        (request.phase == "inspect_recipient") != (reply.needs_candidate is not None)
    ):
        raise RefusalError(RefusalCode.INVALID_FRAME)
    write_document(channel, WorkerAuthorizationAcknowledgement(request_id=request.request_id), deadline=deadline)
    return reply.needs_candidate
