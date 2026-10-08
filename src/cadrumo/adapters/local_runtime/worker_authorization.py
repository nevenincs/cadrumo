"""Native worker-only effect fences held on dedicated runtime threads."""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import datetime, timedelta
from importlib.metadata import version
from pathlib import Path
from threading import BoundedSemaphore, Event, Thread
from uuid import UUID, uuid4, uuid5

from pydantic import SecretBytes

from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError, RuntimeServerHello
from ...application.runtime.profile_access import RuntimeAccessRefusal
from ...application.runtime.profile_worker import ProfileWorkerIdentity
from ...application.runtime.worker_authorization import (
    AUTHORITY_SECTION_MAXIMUM_SECONDS,
    WORKER_AUTOMATION_INVENTORY_MAX_BYTES,
    WorkerAuthorityEnvelope,
    WorkerAuthorityRequest,
    WorkerAuthorizationAcknowledgement,
    WorkerAuthorizationInstruction,
    WorkerAuthorizationOwner,
    WorkerAuthorizationPermit,
    WorkerAuthorizationRelease,
    WorkerAuthorizationReleased,
    WorkerAuthorizationRequest,
    WorkerAutomationInventoryAllowed,
    WorkerAutomationInventoryPermit,
    WorkerAutomationInventoryRequest,
    WorkerResponseScopePermit,
    WorkerResponseScopeRequest,
)
from ...application.runtime.worker_enrollment import (
    WorkerApprovalPhaseResult,
    WorkerApprovalPublication,
    WorkerApprovalPublished,
    WorkerApprovalReady,
    WorkerApprovalRequest,
)
from ...application.user_profile.access_contracts import AccessAllowed, AccessDenialCode, OperationResponseScopeAllowed
from ...application.user_profile.access_errors import ProfileAccessRefusedError
from ...application.user_profile.automation_custody_port import AutomationCustodyError
from ...application.user_profile.automation_enrollment import AutomationInventory
from ...core.hashing import canonical_json_bytes
from ...core.time.clock import now
from .framing import accept_runtime_handshake
from .runtime_frame_io import MAXIMUM_FRAME_BYTES, read_document, read_secret, write_document
from .worker_transport import WorkerChannel, worker_endpoint


def worker_authorization_namespace(worker_id: UUID) -> UUID:
    """Derive a separate endpoint identity; the name itself grants no authority."""
    return uuid5(worker_id, "cadrumo-operation-authorization")


def _require_inventory_ipc_budget(inventory: AutomationInventory) -> None:
    """Refuse a whole inventory that cannot fit a protected native response."""
    size = len(canonical_json_bytes(inventory.model_dump(mode="json")))
    if size > WORKER_AUTOMATION_INVENTORY_MAX_BYTES:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


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
        wall_clock: Callable[[], datetime] = now,
    ) -> None:
        """Claim a private worker namespace before any operation can request authority."""
        self.identity, self._pid = identity, process_id
        self._owns_process, self._contain, self._owner = owns_process, contain, owner
        self._wall_clock = wall_clock
        self._stop, self._failed = Event(), Event()
        self._slots = BoundedSemaphore(8)
        self._endpoint = worker_endpoint(
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

    def _connection(self, channel: WorkerChannel) -> None:
        request: WorkerAuthorityRequest | WorkerAutomationInventoryRequest | WorkerApprovalRequest | None = None
        try:
            self._verify_worker_channel(channel)
            request = read_document(channel, WorkerAuthorityEnvelope, deadline=time.monotonic() + 5).root
            owner = self._request_owner(request)
            if isinstance(request, WorkerApprovalRequest):
                try:
                    self._approval_phase(channel, request)
                except BaseException:
                    # A lost phase reply must not strand proof until expiry.
                    # Retirement is peer-bound cleanup and needs no live lease.
                    owner.approval_phase(request.model_copy(update={"phase": "close"}), None)
                    raise
                return
            permit_id = uuid4()
            guard = (
                owner.automation_inventory(request)
                if isinstance(request, WorkerAutomationInventoryRequest)
                else owner.authorize(request)
            )
            with guard as allowed:
                permit, deadline = self._held_permit(request, allowed, permit_id)
                try:
                    write_document(
                        channel,
                        permit,
                        deadline=deadline,
                    )
                    self._held_body(channel, request, permit_id=permit_id, deadline=deadline)
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

    def _approval_phase(self, channel: WorkerChannel, request: WorkerApprovalRequest) -> None:
        if self._owner is None or self._stop.is_set():
            raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
        self._owner.approval_preflight(request)
        deadline = time.monotonic() + 60
        if request.phase == "prepare":
            write_document(
                channel,
                WorkerApprovalReady(request_id=request.request_id, runtime_boot_id=self.identity.runtime_boot_id),
                deadline=deadline,
            )
            with read_secret(channel, deadline=deadline) as secret:
                result = self._owner.approval_phase(request, SecretBytes(bytes(secret)))
        else:
            result = self._owner.approval_phase(request, None)
        write_document(
            channel,
            WorkerApprovalPhaseResult(
                request_id=request.request_id,
                runtime_boot_id=self.identity.runtime_boot_id,
                needs_candidate=result,
            ),
            deadline=deadline,
        )
        acknowledged = read_document(channel, WorkerAuthorizationAcknowledgement, deadline=deadline)
        if acknowledged.request_id != request.request_id:
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)

    def _held_body(
        self,
        channel: WorkerChannel,
        request: WorkerAuthorityRequest | WorkerAutomationInventoryRequest,
        *,
        permit_id: UUID,
        deadline: float,
    ) -> None:
        """Execute at most one publication on the native thread retaining the guard."""
        command_seen = False
        while True:
            instruction = read_document(channel, WorkerAuthorizationInstruction, deadline=deadline).root
            if instruction.request_id != request.request_id or instruction.permit_id != permit_id:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            if isinstance(instruction, WorkerAuthorizationRelease):
                return
            if command_seen or not isinstance(request, WorkerAuthorizationRequest) or self._owner is None:
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            command_seen = True
            reply = self._publication_result(self._owner, request, instruction, permit_id)
            write_document(channel, reply, deadline=deadline)

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

    def _request_owner(
        self, request: WorkerAuthorityRequest | WorkerAutomationInventoryRequest | WorkerApprovalRequest
    ) -> WorkerAuthorizationOwner:
        """Require configured authority for the exact worker profile before dispatch."""
        if self._owner is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if request.request.profile_id != self.identity.binding.profile_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        return self._owner

    def _verify_worker_channel(self, channel: WorkerChannel) -> None:
        """Authenticate the retained worker process before accepting any request."""
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

    def _held_permit(
        self,
        request: WorkerAuthorityRequest | WorkerAutomationInventoryRequest,
        allowed: AccessAllowed | OperationResponseScopeAllowed | WorkerAutomationInventoryAllowed,
        permit_id: UUID,
    ) -> tuple[WorkerAuthorizationPermit | WorkerResponseScopePermit | WorkerAutomationInventoryPermit, float]:
        """Build a live exact-family permit while the owning profile guard is held."""
        _require_allowed_request_family(request, allowed)
        # A queued callback may acquire the profile guard only after
        # shutdown began. It must not publish a new permit then.
        if self._stop.is_set():
            raise RuntimeRefusalError(RuntimeRefusalCode.DRAINING)
        instant = self._wall_clock()
        expires = min(allowed.expires_at, instant + timedelta(seconds=AUTHORITY_SECTION_MAXIMUM_SECONDS))
        remaining = (expires - instant).total_seconds()
        if remaining <= 0:
            raise ProfileAccessRefusedError(AccessDenialCode.SESSION_EXPIRED)
        deadline = time.monotonic() + remaining
        if isinstance(request, WorkerAutomationInventoryRequest):
            if not isinstance(allowed, WorkerAutomationInventoryAllowed):
                raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
            _require_inventory_ipc_budget(allowed.inventory)
            permit = WorkerAutomationInventoryPermit(
                request_id=request.request_id,
                runtime_boot_id=self.identity.runtime_boot_id,
                permit_id=permit_id,
                expires_at=expires,
                inventory=allowed.inventory,
            )
            if len(canonical_json_bytes(permit.model_dump(mode="json"))) > MAXIMUM_FRAME_BYTES:
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        elif isinstance(request, WorkerResponseScopeRequest):
            permit = WorkerResponseScopePermit(
                request_id=request.request_id,
                runtime_boot_id=self.identity.runtime_boot_id,
                permit_id=permit_id,
                expires_at=expires,
            )
        else:
            permit = WorkerAuthorizationPermit(
                request_id=request.request_id,
                runtime_boot_id=self.identity.runtime_boot_id,
                permit_id=permit_id,
                expires_at=expires,
            )
        return permit, deadline

    def _publication_result(
        self,
        owner: WorkerAuthorizationOwner,
        request: WorkerAuthorizationRequest,
        instruction: WorkerApprovalPublication,
        permit_id: UUID,
    ) -> RuntimeAccessRefusal | WorkerApprovalPublished:
        """Publish on the lock-owning thread and preserve exact custody refusals."""
        # The owner validates exact operation/profile/session coordinates
        # and performs canonical publication on this same lock-owning thread.
        try:
            transition = owner.approval_publication(request, instruction)
        except (AutomationCustodyError, ProfileAccessRefusedError) as error:
            reply = RuntimeAccessRefusal(
                request_id=request.request_id,
                runtime_boot_id=self.identity.runtime_boot_id,
                connection_id=request.connection_id,
                code=error.reason,
            )
        else:
            reply = WorkerApprovalPublished(
                request_id=request.request_id,
                permit_id=permit_id,
                command_id=instruction.command_id,
                runtime_boot_id=self.identity.runtime_boot_id,
                receipt=transition.receipt if transition is not None else None,
                published=transition.published if transition is not None else False,
            )
        return reply


def _require_allowed_request_family(
    request: WorkerAuthorityRequest | WorkerAutomationInventoryRequest,
    allowed: AccessAllowed | OperationResponseScopeAllowed | WorkerAutomationInventoryAllowed,
) -> None:
    """Refuse inventory or scope capabilities returned for a different request family."""
    # No inventory payload can be advertised through an ordinary
    # permit, and no scope-only response can become an effect permit.
    if isinstance(request, WorkerAutomationInventoryRequest):
        if not isinstance(allowed, WorkerAutomationInventoryAllowed):
            raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    elif isinstance(allowed, WorkerAutomationInventoryAllowed) or (
        isinstance(request, WorkerResponseScopeRequest) != isinstance(allowed, OperationResponseScopeAllowed)
    ):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
