"""Cancellation-complete worker access to a runtime-held profile authorization fence."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from importlib.metadata import version
from pathlib import Path

from ...application.runtime.contracts import RuntimeClientHello, RuntimeRefusalCode, RuntimeRefusalError
from ...application.runtime.profile_access import RuntimeAccessRefusal
from ...application.runtime.profile_worker import ProfileWorkerIdentity
from ...application.runtime.worker_authorization import (
    AUTHORITY_SECTION_MAXIMUM_SECONDS,
    WorkerAuthorizationAcknowledgement,
    WorkerAuthorizationPermit,
    WorkerAuthorizationRelease,
    WorkerAuthorizationReleased,
    WorkerAuthorizationReply,
    WorkerAuthorizationRequest,
)
from ...application.user_profile.access_contracts import AccessDenialCode
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from ...core.async_cleanup import await_cancellation_complete, close_async_resources
from ...core.time.clock import now
from .framing import VerifiedRuntimeConnection, read_document, write_document
from .windows import WindowsRuntimeChannel, WindowsRuntimeEndpoint
from .worker_authorization import worker_authorization_namespace


class WorkerAuthorizationLease:
    """One native connection with explicit acquisition/release, never an ordinary result."""

    def __init__(
        self, *, identity: ProfileWorkerIdentity, root: Path, parent_pid: int, request: WorkerAuthorizationRequest
    ) -> None:
        """Capture only trusted worker routing and registered operation coordinates."""
        self.identity, self.root, self.parent_pid, self.request = identity, root, parent_pid, request
        self._channel: WindowsRuntimeChannel | None = None
        self._permit: WorkerAuthorizationPermit | None = None
        self._deadline = 0.0

    def acquire(self) -> None:
        """Authenticate the retained native parent before requesting a held fence."""
        endpoint = WindowsRuntimeEndpoint(
            storage_root=self.root, worker_namespace=worker_authorization_namespace(self.identity.worker_id)
        )
        channel: WindowsRuntimeChannel | None = None
        try:
            channel = endpoint.connect(timeout=5)
            if (
                channel.peer.process_id != self.parent_pid
                or channel.peer.os_owner_id != self.identity.binding.os_owner_id
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
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
                not isinstance(reply, WorkerAuthorizationPermit)
                or reply.runtime_boot_id != self.identity.runtime_boot_id
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
    async def guard(self, request: WorkerAuthorizationRequest) -> AsyncGenerator[None]:
        """Finish acquisition and release even when the operation task is cancelled."""
        lease = WorkerAuthorizationLease(
            identity=self.identity, root=self.root, parent_pid=self.parent_pid, request=request
        )
        try:
            await await_cancellation_complete(asyncio.to_thread(lease.acquire), task_name="worker-authority-acquire")
            yield
        finally:
            await close_async_resources(lease, task_name="worker-authority-release")
