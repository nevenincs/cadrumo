"""Cancellation-complete acquisition and approval requests to the retained runtime parent."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import ExitStack, asynccontextmanager
from importlib.metadata import version
from pathlib import Path

from pydantic import SecretBytes

from ...application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.profile_access import RuntimeAccessRefusal
from ...application.runtime.profile_worker import ProfileWorkerIdentity
from ...application.runtime.worker_authorization import (
    WorkerAuthorityRequest,
    WorkerAuthorizationAcknowledgement,
    WorkerAuthorizationPermit,
    WorkerAuthorizationReleased,
    WorkerAuthorizationReply,
    WorkerAutomationInventoryPermit,
    WorkerAutomationInventoryRequest,
    WorkerResponseScopePermit,
)
from ...application.runtime.worker_enrollment import (
    WorkerApprovalPhaseResult,
    WorkerApprovalPublished,
    WorkerApprovalReady,
    WorkerApprovalRequest,
)
from ...application.user_profile.automation_enrollment import AutomationInventory
from ...core.async_cleanup import await_cancellation_complete, close_async_resources
from .framing import VerifiedRuntimeConnection
from .posix_channel import PosixRuntimeChannel
from .runtime_frame_io import read_document, write_document, write_secret
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
            reply = _complete_password_phase(channel, reply, request, password, self.identity, deadline)
            return _accepted_approval_phase_reply(channel, reply, request, self.identity, deadline)


def _complete_password_phase(
    channel: WorkerChannel,
    reply: RuntimeAccessRefusal
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
    RuntimeAccessRefusal
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
        not isinstance(reply, RuntimeAccessRefusal | WorkerApprovalReady | WorkerApprovalPhaseResult)
        or reply.request_id != request.request_id
        or reply.runtime_boot_id != identity.runtime_boot_id
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    if isinstance(reply, WorkerApprovalReady):
        if request.phase != "prepare" or password is None:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        write_secret(channel, bytearray(password.get_secret_value()), deadline=deadline)
        reply = read_document(channel, WorkerAuthorizationReply, deadline=deadline).root
    return reply


def _accepted_approval_phase_reply(
    channel: WorkerChannel,
    reply: RuntimeAccessRefusal
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
        not isinstance(reply, RuntimeAccessRefusal | WorkerApprovalPhaseResult)
        or reply.request_id != request.request_id
        or reply.runtime_boot_id != identity.runtime_boot_id
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    if isinstance(reply, RuntimeAccessRefusal):
        if reply.connection_id != request.connection_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        write_document(channel, WorkerAuthorizationAcknowledgement(request_id=request.request_id), deadline=deadline)
        raise_worker_access_refusal(reply)
    if not isinstance(reply, WorkerApprovalPhaseResult) or (
        (request.phase == "inspect_recipient") != (reply.needs_candidate is not None)
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    write_document(channel, WorkerAuthorizationAcknowledgement(request_id=request.request_id), deadline=deadline)
    return reply.needs_candidate
