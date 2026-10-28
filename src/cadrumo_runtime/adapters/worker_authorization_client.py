"""Cancellation-complete acquisition and approval requests to the retained runtime parent."""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import SecretBytes

from cadrumo.application.operations.models import OperationId
from cadrumo.application.user_profile.automation_enrollment import AutomationInventory
from cadrumo.core.async_cleanup import await_cancellation_complete, close_async_resources
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.contracts import RefusalCode, RefusalError
from cadrumo_client.contracts.deadline_budget import exchange_deadline
from cadrumo_client.contracts.profile_access import AccessRefusal
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport.frame_io import read_document, write_document, write_secret
from cadrumo_runtime.contracts.worker_authorization import (
    WorkerAuthorityCheck,
    WorkerAuthorityChecked,
    WorkerAuthorityRequest,
    WorkerAuthorizationAcknowledgement,
    WorkerAuthorizationReply,
    WorkerAutomationInventoryRequest,
    WorkerOperationsAdvanced,
)
from cadrumo_runtime.contracts.worker_enrollment import (
    WorkerApprovalPhaseResult,
    WorkerApprovalReady,
    WorkerApprovalRequest,
)

from .worker_authorization_connections import WorkerAuthorizationConnections
from .worker_authorization_lease import WorkerAuthorizationLease
from .worker_authorization_refusals import raise_worker_access_refusal
from .worker_transport import WorkerChannel

_REPORT_SECONDS = 5.0
_APPROVAL_PHASE_SECONDS = 60.0


class WorkerAuthorizationClient:
    """Run each exchange on its own pooled verified connection, one exchange at a time on each."""

    def __init__(self, *, identity: ProfileWorkerIdentity, root: Path, parent_pid: int) -> None:
        """Bind one immutable worker to its verified runtime parent."""
        self.identity, self.root, self.parent_pid = identity, root, parent_pid
        self.connections = WorkerAuthorizationConnections(identity=identity, root=root, parent_pid=parent_pid)

    def close(self) -> None:
        """Close the pooled connections; an exchange still running closes its own when it ends."""
        self.connections.close()

    @asynccontextmanager
    async def guard(self, request: WorkerAuthorityRequest) -> AsyncGenerator[WorkerAuthorizationLease]:
        """Finish acquisition and release even when the operation task is cancelled."""
        lease = WorkerAuthorizationLease(connections=self.connections, request=request)
        try:
            await await_cancellation_complete(asyncio.to_thread(lease.acquire), task_name="worker-authority-acquire")
            yield lease
        finally:
            if isinstance(sys.exception(), asyncio.CancelledError):
                # The release still runs to its end; only the connection is not reused.
                lease.abandon()
            await close_async_resources(lease, task_name="worker-authority-release")

    async def check(self, request: WorkerAuthorityRequest) -> None:
        """Ask whether one stage is admitted now, for a caller that runs no body under the answer.

        The runtime holds no fence and issues no permit. A refusal raises its
        exact category, as a refused guard does.
        """
        await await_cancellation_complete(asyncio.to_thread(self._check, request), task_name="worker-authority-check")

    async def inventory(self, request: WorkerAutomationInventoryRequest) -> AutomationInventory:
        """Read held human inventory and finish its native release before returning."""
        lease = WorkerAuthorizationLease(connections=self.connections, request=request)
        try:
            await await_cancellation_complete(asyncio.to_thread(lease.acquire), task_name="worker-inventory-acquire")
            return lease.inventory()
        finally:
            if isinstance(sys.exception(), asyncio.CancelledError):
                lease.abandon()
            await close_async_resources(lease, task_name="worker-inventory-release")

    async def approval_phase(self, request: WorkerApprovalRequest, password: SecretBytes | None = None) -> bool | None:
        """Complete an unguarded proof or recipient phase on a verified connection of its own."""
        return await await_cancellation_complete(
            asyncio.to_thread(self._approval_phase, request, password), task_name="worker-approval-phase"
        )

    def operations_advanced(self, operation_ids: tuple[OperationId, ...], *, records_changed: bool = False) -> None:
        """Report committed operations to the runtime parent; it acknowledges and grants nothing."""
        report = WorkerOperationsAdvanced(
            request_id=uuid4(), operation_ids=operation_ids, records_changed=records_changed
        )
        deadline = time.monotonic() + _REPORT_SECONDS
        channel = self.connections.checkout(deadline)
        clean = False
        try:
            write_document(channel, report, deadline=deadline)
            acknowledged = read_document(channel, WorkerAuthorizationAcknowledgement, deadline=deadline)
            if acknowledged.request_id != report.request_id:
                raise RefusalError(RefusalCode.INVALID_FRAME)
            clean = True
        finally:
            self.connections.checkin(channel, reusable=clean)

    def _check(self, request: WorkerAuthorityRequest) -> None:
        # The runtime may queue this admission behind a running COMMIT's fence.
        deadline = exchange_deadline()
        channel = self.connections.checkout(deadline)
        clean = False
        try:
            write_document(channel, WorkerAuthorityCheck(authority=request), deadline=deadline)
            reply = read_document(channel, WorkerAuthorizationReply, deadline=deadline).root
            if (
                not isinstance(reply, AccessRefusal | WorkerAuthorityChecked)
                or reply.request_id != request.request_id
                or reply.runtime_boot_id != self.identity.runtime_boot_id
            ):
                raise RefusalError(RefusalCode.INVALID_FRAME)
            if isinstance(reply, AccessRefusal):
                _acknowledge_refusal(channel, reply, request.request_id, request.connection_id, deadline)
                clean = True
                raise_worker_access_refusal(reply)
            clean = True
            # Admission is checked as the stage starts; a lease already ended admits nothing.
            if reply.expires_at <= now():
                raise RefusalError(RefusalCode.TIMEOUT)
        finally:
            self.connections.checkin(channel, reusable=clean)

    def _approval_phase(self, request: WorkerApprovalRequest, password: SecretBytes | None) -> bool | None:
        if (request.phase == "prepare") != (password is not None):
            raise RefusalError(RefusalCode.INVALID_FRAME)
        deadline = time.monotonic() + _APPROVAL_PHASE_SECONDS
        channel = self.connections.checkout(deadline)
        clean = False
        try:
            write_document(channel, request, deadline=deadline)
            first = read_document(channel, WorkerAuthorizationReply, deadline=deadline).root
            if (
                not isinstance(first, AccessRefusal | WorkerApprovalReady | WorkerApprovalPhaseResult)
                or first.request_id != request.request_id
                or first.runtime_boot_id != self.identity.runtime_boot_id
            ):
                raise RefusalError(RefusalCode.INVALID_FRAME)
            reply = first
            if isinstance(first, WorkerApprovalReady):
                # Fresh proof is sent only after the exact worker has acknowledged preparation.
                if request.phase != "prepare" or password is None:
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                write_secret(channel, bytearray(password.get_secret_value()), deadline=deadline)
                reply = read_document(channel, WorkerAuthorizationReply, deadline=deadline).root
                if (
                    not isinstance(reply, AccessRefusal | WorkerApprovalPhaseResult)
                    or reply.request_id != request.request_id
                    or reply.runtime_boot_id != self.identity.runtime_boot_id
                ):
                    raise RefusalError(RefusalCode.INVALID_FRAME)
            if isinstance(reply, AccessRefusal):
                _acknowledge_refusal(channel, reply, request.request_id, request.connection_id, deadline)
                # A refusal after the proof was sent closes the connection, as the runtime does.
                clean = reply is first
                raise_worker_access_refusal(reply)
            if not isinstance(reply, WorkerApprovalPhaseResult) or (
                (request.phase == "inspect_recipient") != (reply.needs_candidate is not None)
            ):
                raise RefusalError(RefusalCode.INVALID_FRAME)
            write_document(
                channel, WorkerAuthorizationAcknowledgement(request_id=request.request_id), deadline=deadline
            )
            clean = True
            return reply.needs_candidate
        finally:
            self.connections.checkin(channel, reusable=clean)


def _acknowledge_refusal(
    channel: WorkerChannel, reply: AccessRefusal, request_id: UUID, connection_id: UUID, deadline: float
) -> None:
    """Acknowledge only a refusal addressed to this exact request and connection."""
    if reply.request_id != request_id or reply.connection_id != connection_id:
        raise RefusalError(RefusalCode.INVALID_FRAME)
    write_document(channel, WorkerAuthorizationAcknowledgement(request_id=reply.request_id), deadline=deadline)
