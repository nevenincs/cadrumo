"""Native worker-only effect fences held on dedicated runtime threads."""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import timedelta
from importlib.metadata import version
from pathlib import Path
from threading import BoundedSemaphore, Event, Thread
from uuid import UUID, uuid4, uuid5

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError, RuntimeServerHello
from ...application.runtime.profile_access import RuntimeAccessRefusal
from ...application.runtime.profile_worker import ProfileWorkerIdentity
from ...application.runtime.worker_authorization import (
    AUTHORITY_SECTION_MAXIMUM_SECONDS,
    WorkerAuthorizationAcknowledgement,
    WorkerAuthorizationOwner,
    WorkerAuthorizationPermit,
    WorkerAuthorizationRelease,
    WorkerAuthorizationReleased,
    WorkerAuthorizationRequest,
)
from ...application.user_profile.access_contracts import AccessDenialCode
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_custody_port import AutomationCustodyError
from ...core.time.clock import now
from .framing import accept_runtime_handshake, read_document, write_document
from .windows import WindowsRuntimeChannel, WindowsRuntimeEndpoint


def worker_authorization_namespace(worker_id: UUID) -> UUID:
    """Derive a separate endpoint identity; the name itself grants no authority."""
    return uuid5(worker_id, "cadrumo-operation-authorization")


class WorkerAuthorizationServer:
    """Keep the profile RLock on one thread until release or owned-process containment.

    Shutdown signals do not join while a caller holds the profile guard. The
    host separately calls settle after releasing that guard. At most eight
    native channels may wait for or hold authority for one worker.
    """

    def __init__(
        self,
        *,
        identity: ProfileWorkerIdentity,
        root: Path,
        process_id: int,
        owns_process: Callable[[int], bool],
        contain: Callable[[], None],
        owner: WorkerAuthorizationOwner | None,
    ) -> None:
        """Claim a private worker namespace before any operation can request authority."""
        self.identity, self._pid = identity, process_id
        self._owns_process, self._contain, self._owner = owns_process, contain, owner
        self._stop, self._failed = Event(), Event()
        self._slots = BoundedSemaphore(8)
        self._endpoint = WindowsRuntimeEndpoint(
            storage_root=root, worker_namespace=worker_authorization_namespace(identity.worker_id)
        )
        self._thread = Thread(target=self._serve, name="profile-operation-authority", daemon=True)
        try:
            self._endpoint.listen()
            self._thread.start()
        except BaseException:
            self._endpoint.close()
            raise

    def _serve(self) -> None:
        try:
            with ThreadPoolExecutor(max_workers=8, thread_name_prefix="profile-effect") as pool:
                while not self._stop.is_set():
                    try:
                        channel = self._endpoint.accept(timeout=0.2)
                    except RuntimeRefusalError as error:
                        if error.reason in {
                            RuntimeRefusalCode.DEADLINE_EXCEEDED,
                            RuntimeRefusalCode.PEER_UNTRUSTED,
                            RuntimeRefusalCode.CONNECTION_CLOSED,
                        }:
                            continue
                        raise
                    if self._stop.is_set() or not self._slots.acquire(blocking=False):
                        channel.close()
                        continue
                    try:
                        pool.submit(self._connection, channel)
                    except BaseException:
                        channel.close()
                        self._slots.release()
                        raise
        except Exception:
            self._failed.set()
            self._stop.set()
        finally:
            self._endpoint.close()

    def _connection(self, channel: WindowsRuntimeChannel) -> None:
        request: WorkerAuthorizationRequest | None = None
        try:
            if (
                channel.peer.process_id != self._pid
                or channel.peer.os_owner_id != self.identity.binding.os_owner_id
                or not self._owns_process(self._pid)
            ):
                raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
            accept_runtime_handshake(
                channel,
                identity=RuntimeServerHello(
                    product_version=version("cadrumo"),
                    storage_identity=self._endpoint.storage_identity,
                    boot_id=self.identity.runtime_boot_id,
                ),
                deadline=time.monotonic() + 5,
            )
            request = read_document(channel, WorkerAuthorizationRequest, deadline=time.monotonic() + 5)
            if self._owner is None:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            if request.request.profile_id != self.identity.binding.profile_id:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            permit_id = uuid4()
            with self._owner.authorize(request) as allowed:
                # A queued callback may acquire the profile guard only after
                # shutdown began. It must not publish a new permit then.
                if self._stop.is_set():
                    raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
                instant = now()
                expires = min(allowed.expires_at, instant + timedelta(seconds=AUTHORITY_SECTION_MAXIMUM_SECONDS))
                remaining = (expires - instant).total_seconds()
                if remaining <= 0:
                    raise ProfileAccessRefusedError(AccessDenialCode.SESSION_EXPIRED)
                deadline = time.monotonic() + remaining
                try:
                    write_document(
                        channel,
                        WorkerAuthorizationPermit(
                            request_id=request.request_id,
                            runtime_boot_id=self.identity.runtime_boot_id,
                            permit_id=permit_id,
                            expires_at=expires,
                        ),
                        deadline=deadline,
                    )
                    released = read_document(channel, WorkerAuthorizationRelease, deadline=deadline)
                    if released.request_id != request.request_id or released.permit_id != permit_id:
                        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
                except BaseException:
                    # A missing/ambiguous release cannot prove the effect body
                    # stopped. Contain the owned job before dropping the fence.
                    try:
                        self._contain()
                    except BaseException:
                        self._failed.set()
                        self._stop.set()
                        raise
                    raise
            write_document(
                channel,
                WorkerAuthorizationReleased(request_id=request.request_id, permit_id=permit_id),
                deadline=time.monotonic() + 5,
            )
            acknowledged = read_document(channel, WorkerAuthorizationAcknowledgement, deadline=time.monotonic() + 5)
            if acknowledged.request_id != request.request_id:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
        except (ProfileAccessRefusedError, AutomationCustodyError, RuntimeRefusalError) as error:
            if request is not None:
                with suppress(RuntimeRefusalError):
                    write_document(
                        channel,
                        RuntimeAccessRefusal(
                            request_id=request.request_id,
                            runtime_boot_id=self.identity.runtime_boot_id,
                            connection_id=request.connection_id,
                            code=error.reason,
                        ),
                        deadline=time.monotonic() + 1,
                    )
                    read_document(channel, WorkerAuthorizationAcknowledgement, deadline=time.monotonic() + 5)
        except Exception:
            self._failed.set()
            self._stop.set()
            # Failure remains latched even if the best-effort containment call
            # itself fails. Host cleanup must independently prove termination.
            with suppress(Exception):
                self._contain()
        finally:
            channel.close()
            self._slots.release()

    def require_healthy(self) -> None:
        """A failed or stopping callback owner cannot authorize another operation."""
        if self._failed.is_set() or self._stop.is_set():
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)

    def close(self) -> None:
        """Stop new permits; do not join a thread while holding its needed profile guard."""
        self._stop.set()

    def settle(self, *, timeout: float = AUTHORITY_SECTION_MAXIMUM_SECONDS + 5) -> None:
        """Join only after the host has released profile guards and contained its worker."""
        self._thread.join(timeout=timeout)
        if self._thread.is_alive() or self._failed.is_set():
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
