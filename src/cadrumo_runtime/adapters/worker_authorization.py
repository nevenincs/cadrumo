"""Native worker-only effect fences held on dedicated runtime threads."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, suppress
from datetime import datetime
from pathlib import Path
from threading import BoundedSemaphore, Event, Thread
from uuid import UUID, uuid4, uuid5

from pydantic import SecretBytes

from cadrumo.application.user_profile.access_errors import ProfileAccessRefusedError
from cadrumo.application.user_profile.automation_enrollment import AutomationInventory
from cadrumo.core.diagnostic_log import diagnostic_error_fields, diagnostic_event
from cadrumo.core.hashing import canonical_json_bytes, sha256_hex
from cadrumo.core.logging import get_logger
from cadrumo.core.time.clock import now
from cadrumo_client.contracts.access_refusals import AccessAllowed, AccessDenialCode, OperationResponseScopeAllowed
from cadrumo_client.contracts.access_vocabulary import AccessAction
from cadrumo_client.contracts.automation_codes import AutomationCustodyError
from cadrumo_client.contracts.contracts import ByteChannel, RefusalCode, RefusalError, ServerHello
from cadrumo_client.contracts.profile_access import AccessRefusal
from cadrumo_client.contracts.worker_identity import ProfileWorkerIdentity
from cadrumo_client.transport.frame_io import read_document, read_secret, write_document, write_document_transfer
from cadrumo_client.transport.model_run_frames import read_secret_chunks, write_secret_chunks
from cadrumo_client.transport.native_wake import NativeWake
from cadrumo_client.transport.product_version import installed_product_version
from cadrumo_runtime.adapters.connection_handshake import accept_connection_handshake
from cadrumo_runtime.contracts.worker_authorization import (
    WORKER_AUTOMATION_INVENTORY_MAX_BYTES,
    WORKER_AUTOMATION_INVENTORY_PERMIT_MAX_BYTES,
    WorkerAuthorityCheck,
    WorkerAuthorityChecked,
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
    WorkerAutomationInventoryTransfer,
    WorkerModelRun,
    WorkerModelRunResult,
    WorkerOperationsAdvanced,
    WorkerResponseScopePermit,
    WorkerResponseScopeRequest,
)
from cadrumo_runtime.contracts.worker_enrollment import (
    WorkerApprovalPhaseResult,
    WorkerApprovalPublication,
    WorkerApprovalPublished,
    WorkerApprovalReady,
    WorkerApprovalRequest,
)

from .native_peer import require_live_native_peer
from .worker_transport import WorkerChannel, worker_endpoint


def worker_authorization_namespace(worker_id: UUID) -> UUID:
    """Derive a separate endpoint identity; the name itself grants no authority."""
    return uuid5(worker_id, "cadrumo-operation-authorization")


def _require_inventory_ipc_budget(inventory: AutomationInventory) -> None:
    """Refuse a whole inventory that cannot fit a protected native response."""
    size = len(canonical_json_bytes(inventory.model_dump(mode="json")))
    if size > WORKER_AUTOMATION_INVENTORY_MAX_BYTES:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


_LOGGER = get_logger(__name__)

_FRAME_SECONDS = 5.0
"""How long one frame of the authority handshake may take to arrive once its first byte is ready."""

_SETTLE_JOIN_SECONDS = 35.0
"""How long shutdown joins the callback thread; its worker is contained first, so the thread ends promptly."""

WORKER_AUTHORIZATION_CONNECTIONS = 8
"""Connections the runtime serves for one worker at once, idle and busy together; the worker opens no more."""


class WorkerAuthorizationServer:
    """Keep the profile RLock on one thread until release or owned-process containment.

    Shutdown signals do not join while a caller holds the profile guard. The
    host separately calls settle after releasing that guard. At most eight
    native channels may wait for or hold authority for one worker.

    A channel is verified once, when it is accepted, and then serves one
    exchange at a time until it closes. Before each exchange the worker's
    kernel incarnation and its membership in the owned job are checked again,
    and the exchange itself is admitted afresh: a channel carries no
    authority from one exchange to the next.
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
        # A stage's wait for the worker's next frame blocks on this stop too.
        self._stop, self._failed = NativeWake(), Event()
        self._slots = BoundedSemaphore(WORKER_AUTHORIZATION_CONNECTIONS)
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
            with ThreadPoolExecutor(
                max_workers=WORKER_AUTHORIZATION_CONNECTIONS, thread_name_prefix="profile-effect"
            ) as pool:
                while not self._stop.is_set():
                    try:
                        channel = self._endpoint.accept(timeout=None, wakes=(self._stop,))
                    except RefusalError as error:
                        if error.reason in {
                            RefusalCode.TIMEOUT,
                            RefusalCode.PEER_UNTRUSTED,
                            RefusalCode.CONNECTION_CLOSED,
                        }:
                            continue
                        raise
                    # A connection the worker just closed may not have handed back its slot yet.
                    # Every slot holder wakes on stop, so this wait also ends promptly then.
                    if not self._slots.acquire(timeout=_FRAME_SECONDS):
                        channel.close()
                        continue
                    if self._stop.is_set():
                        channel.close()
                        self._slots.release()
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
        try:
            self._verify_worker_channel(channel)
            while self._exchange(channel):
                pass
        except (ProfileAccessRefusedError, AutomationCustodyError, RefusalError):
            # A peer refused or lost during verification, the handshake or an idle wait has
            # nothing outstanding; a lost permit was already contained where it was held.
            pass
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

    def _exchange(self, channel: WorkerChannel) -> bool:
        """Serve the channel's next exchange and return whether the channel may serve another.

        Between exchanges nothing is outstanding, so a channel lost, refused or
        stopped while it waits here contains nothing.
        """
        try:
            if not channel.wait_readable(self._stop) or self._stop.is_set():
                return False
            self._require_worker_incarnation(channel)
            envelope = read_document(channel, WorkerAuthorityEnvelope, deadline=time.monotonic() + 5).root
        except RefusalError:
            return False
        if isinstance(envelope, WorkerOperationsAdvanced):
            return self._operations_advanced(channel, envelope)
        request = envelope.authority if isinstance(envelope, WorkerAuthorityCheck) else envelope
        # Set before the first reply is attempted. A refusal after that may follow a partial
        # frame, a secret or a protected body, so the channel then closes instead of serving on.
        replied = [False]
        try:
            owner = self._request_owner(request)
            if isinstance(envelope, WorkerAuthorityCheck):
                self._check(channel, owner, envelope.authority, replied)
            elif isinstance(request, WorkerApprovalRequest):
                try:
                    self._approval_phase(channel, request, replied)
                except BaseException:
                    # A lost phase reply must not strand proof until expiry.
                    # Retirement is peer-bound cleanup and needs no live lease.
                    owner.approval_phase(request.model_copy(update={"phase": "close"}), None)
                    raise
            else:
                self._permit_exchange(channel, owner, request, replied)
        except (ProfileAccessRefusedError, AutomationCustodyError, RefusalError) as error:
            return self._refuse_exchange(channel, request, error, replied)
        return True

    def _refuse_exchange(
        self,
        channel: WorkerChannel,
        request: WorkerAuthorityRequest | WorkerAutomationInventoryRequest | WorkerApprovalRequest,
        error: ProfileAccessRefusedError | AutomationCustodyError | RefusalError,
        replied: list[bool],
    ) -> bool:
        """Acknowledge a refusal only when no earlier frame has been sent."""
        try:
            write_document(
                channel,
                AccessRefusal(
                    request_id=request.request_id,
                    runtime_boot_id=self.identity.runtime_boot_id,
                    connection_id=request.connection_id,
                    code=error.reason,
                ),
                deadline=time.monotonic() + 1,
            )
            acknowledged = read_document(channel, WorkerAuthorizationAcknowledgement, deadline=time.monotonic() + 5)
        except RefusalError:
            return False
        # Only a refusal given before any other reply ends the exchange where the worker expects it.
        return not replied[0] and acknowledged.request_id == request.request_id

    def _permit_exchange(
        self,
        channel: WorkerChannel,
        owner: WorkerAuthorizationOwner,
        request: WorkerAuthorityRequest | WorkerAutomationInventoryRequest,
        replied: list[bool],
    ) -> None:
        """Issue one permit, run its body on this thread and end with an acknowledged release."""
        permit_id = uuid4()
        guard = (
            owner.automation_inventory(request)
            if isinstance(request, WorkerAutomationInventoryRequest)
            else owner.authorize(request)
        )
        # Authority is checked once, as the stage starts. Only a COMMIT keeps the
        # profile's admission fence through its body: its effects are irreversible,
        # and an approval publishes on the fence's own thread. Every other stage runs
        # unfenced, so it never holds up the profile's other requests.
        hold_fence = isinstance(request, WorkerAuthorizationRequest) and request.request.action is AccessAction.COMMIT
        with ExitStack() as fence:
            allowed = fence.enter_context(guard)
            permit = self._held_permit(request, allowed, permit_id)
            replied[0] = True
            _write_permit(channel, permit, deadline=time.monotonic() + 5)
            if not hold_fence:
                fence.close()
            try:
                # A stage is never ended for the time it takes; it ends when the
                # worker releases it, its channel dies, or the runtime stops.
                self._held_body(channel, request, permit_id=permit_id)
            except BaseException as error:
                # A lost release cannot prove the effect body stopped. Contain
                # the owned job before dropping the fence.
                diagnostic_event(
                    _LOGGER,
                    "profile_worker_permit_contained",
                    fields={"request_kind": request.kind, **diagnostic_error_fields(error)},
                    level=logging.WARNING,
                    primary_error=error,
                )
                try:
                    self._contain()
                except BaseException:
                    self._failed.set()
                    self._stop.set()
                    raise
                raise
        # The fence is already released, before the channel waits for its next exchange.
        write_document(
            channel,
            WorkerAuthorizationReleased(request_id=request.request_id, permit_id=permit_id),
            deadline=time.monotonic() + 5,
        )
        acknowledged = read_document(channel, WorkerAuthorizationAcknowledgement, deadline=time.monotonic() + 5)
        if acknowledged.request_id != request.request_id:
            raise RefusalError(RefusalCode.INVALID_FRAME)

    def _check(
        self,
        channel: WorkerChannel,
        owner: WorkerAuthorizationOwner,
        request: WorkerAuthorityRequest,
        replied: list[bool],
    ) -> None:
        """Answer whether one stage is admitted now, leaving the guard before the answer is sent.

        No permit is issued and no fence outlives the evaluation, so nothing is
        outstanding if the channel is lost while the answer is in flight.
        """
        with owner.authorize(request) as allowed:
            _require_allowed_request_family(request, allowed)
            expires = self._admitted_until(allowed)
        replied[0] = True
        write_document(
            channel,
            WorkerAuthorityChecked(
                request_id=request.request_id, runtime_boot_id=self.identity.runtime_boot_id, expires_at=expires
            ),
            deadline=time.monotonic() + 5,
        )

    def _operations_advanced(self, channel: WorkerChannel, report: WorkerOperationsAdvanced) -> bool:
        """Cue observers of the reported operations; a report holds no authority, so nothing here contains.

        Return whether the acknowledgement was sent, which ends the exchange cleanly.
        """
        if self._owner is not None:
            try:
                self._owner.operations_advanced(report.operation_ids, records_changed=report.records_changed)
            except Exception as error:
                # A missed cue costs a client its wait, bounded by its deadline.
                diagnostic_event(
                    _LOGGER,
                    "profile_worker_progress_cue_failed",
                    fields=diagnostic_error_fields(error),
                    level=logging.WARNING,
                    primary_error=error,
                )
        try:
            write_document(
                channel,
                WorkerAuthorizationAcknowledgement(request_id=report.request_id),
                deadline=time.monotonic() + 5,
            )
        except RefusalError:
            return False
        return True

    def _approval_phase(self, channel: WorkerChannel, request: WorkerApprovalRequest, replied: list[bool]) -> None:
        if self._owner is None or self._stop.is_set():
            raise RefusalError(RefusalCode.DRAINING)
        self._owner.approval_preflight(request)
        deadline = time.monotonic() + 60
        if request.phase == "prepare":
            replied[0] = True
            write_document(
                channel,
                WorkerApprovalReady(request_id=request.request_id, runtime_boot_id=self.identity.runtime_boot_id),
                deadline=deadline,
            )
            with read_secret(channel, deadline=deadline) as secret:
                result = self._owner.approval_phase(request, SecretBytes(bytes(secret)))
        else:
            result = self._owner.approval_phase(request, None)
        replied[0] = True
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
            raise RefusalError(RefusalCode.INVALID_FRAME)

    def _held_body(
        self,
        channel: WorkerChannel,
        request: WorkerAuthorityRequest | WorkerAutomationInventoryRequest,
        *,
        permit_id: UUID,
    ) -> None:
        """Execute at most one command on the native thread retaining the guard, then await the release."""
        command_seen = False
        while True:
            self._await_instruction(channel)
            instruction = read_document(
                channel, WorkerAuthorizationInstruction, deadline=time.monotonic() + _FRAME_SECONDS
            ).root
            if instruction.request_id != request.request_id or instruction.permit_id != permit_id:
                raise RefusalError(RefusalCode.INVALID_FRAME)
            if isinstance(instruction, WorkerAuthorizationRelease):
                return
            if command_seen or not isinstance(request, WorkerAuthorizationRequest) or self._owner is None:
                raise RefusalError(RefusalCode.INVALID_FRAME)
            command_seen = True
            if isinstance(instruction, WorkerModelRun):
                self._model_run(channel, self._owner, request, instruction, permit_id)
                continue
            reply = self._publication_result(self._owner, request, instruction, permit_id)
            write_document(channel, reply, deadline=time.monotonic() + _FRAME_SECONDS)

    def _model_run(
        self,
        channel: WorkerChannel,
        owner: WorkerAuthorizationOwner,
        request: WorkerAuthorizationRequest,
        instruction: WorkerModelRun,
        permit_id: UUID,
    ) -> None:
        """Answer one model-run instruction under a held START permit, from the profile's agent service.

        Only a START permit admits it, so the runtime has already rechecked the
        operation's authority for this stage. The body and the reply text are
        relayed as secret frames and wiped once sent; the runtime reads neither.
        """
        if request.request.action is not AccessAction.START:
            raise RefusalError(RefusalCode.INVALID_FRAME)
        body = read_secret_chunks(channel, instruction.body_byte_count, deadline=time.monotonic() + _FRAME_SECONDS)
        text = bytearray()
        try:
            outcome, text = owner.model_run(request, instruction, body)
            write_document(
                channel,
                WorkerModelRunResult(
                    request_id=request.request_id,
                    permit_id=permit_id,
                    command_id=instruction.command_id,
                    runtime_boot_id=self.identity.runtime_boot_id,
                    outcome=outcome,
                ),
                deadline=time.monotonic() + _FRAME_SECONDS,
            )
            write_secret_chunks(channel, text, deadline=time.monotonic() + _FRAME_SECONDS)
        finally:
            body[:] = bytes(len(body))
            text[:] = bytes(len(text))

    def _await_instruction(self, channel: WorkerChannel) -> None:
        """Wait for the worker's next frame for as long as its stage runs, ending only on stop or a dead channel."""
        if not channel.wait_readable(self._stop):
            raise RefusalError(RefusalCode.DRAINING)

    def require_healthy(self) -> None:
        """A failed or stopping callback owner cannot authorize another operation."""
        if self._failed.is_set() or self._stop.is_set():
            raise RefusalError(RefusalCode.UNAVAILABLE)

    def close(self) -> None:
        """Stop new permits; do not join a thread while holding its needed profile guard."""
        self._stop.set()

    def settle(self, *, timeout: float = _SETTLE_JOIN_SECONDS) -> None:
        """Join only after the host has released profile guards and contained its worker."""
        self._thread.join(timeout=timeout)
        if self._thread.is_alive() or self._failed.is_set():
            raise RefusalError(RefusalCode.UNAVAILABLE)

    def _request_owner(
        self, request: WorkerAuthorityRequest | WorkerAutomationInventoryRequest | WorkerApprovalRequest
    ) -> WorkerAuthorizationOwner:
        """Require configured authority for the exact worker profile before dispatch."""
        if self._owner is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if request.request.profile_id != self.identity.binding.profile_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        return self._owner

    def _require_worker_incarnation(self, channel: WorkerChannel) -> None:
        """Recheck, before each exchange, that the verified worker is the same live process in the owned job."""
        require_live_native_peer(channel)
        if channel.peer.process_id != self._pid or not self._owns_process(self._pid):
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)

    def _verify_worker_channel(self, channel: WorkerChannel) -> None:
        """Authenticate the retained worker process before accepting any request."""
        if (
            channel.peer.process_id != self._pid
            or channel.peer.os_owner_id != self.identity.binding.os_owner_id
            or not self._owns_process(self._pid)
        ):
            raise RefusalError(RefusalCode.PEER_UNTRUSTED)
        accept_connection_handshake(
            channel,
            identity=ServerHello(
                product_version=installed_product_version(),
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
    ) -> WorkerAuthorizationPermit | WorkerResponseScopePermit | WorkerAutomationInventoryPermit:
        """Build a live exact-family permit while the owning profile guard is held."""
        _require_allowed_request_family(request, allowed)
        expires = self._admitted_until(allowed)
        if isinstance(request, WorkerAutomationInventoryRequest):
            if not isinstance(allowed, WorkerAutomationInventoryAllowed):
                raise RefusalError(RefusalCode.INVALID_FRAME)
            _require_inventory_ipc_budget(allowed.inventory)
            permit = WorkerAutomationInventoryPermit(
                request_id=request.request_id,
                runtime_boot_id=self.identity.runtime_boot_id,
                permit_id=permit_id,
                expires_at=expires,
                inventory=allowed.inventory,
            )
            if len(canonical_json_bytes(permit.model_dump(mode="json"))) > WORKER_AUTOMATION_INVENTORY_PERMIT_MAX_BYTES:
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
        return permit

    def _admitted_until(
        self, allowed: AccessAllowed | OperationResponseScopeAllowed | WorkerAutomationInventoryAllowed
    ) -> datetime:
        """Return when the admitting lease ends, refusing once shutdown began or the lease has ended."""
        # A queued callback may acquire the profile guard only after
        # shutdown began. It must not publish a new permit or answer then.
        if self._stop.is_set():
            raise RefusalError(RefusalCode.DRAINING)
        # The permit names when the admitting lease ends; a stage already running is not ended by it.
        expires = allowed.expires_at
        if expires <= self._wall_clock():
            raise ProfileAccessRefusedError(AccessDenialCode.SESSION_EXPIRED)
        return expires

    def _publication_result(
        self,
        owner: WorkerAuthorizationOwner,
        request: WorkerAuthorizationRequest,
        instruction: WorkerApprovalPublication,
        permit_id: UUID,
    ) -> AccessRefusal | WorkerApprovalPublished:
        """Publish on the lock-owning thread and preserve exact custody refusals."""
        # The owner validates exact operation/profile/session coordinates
        # and performs canonical publication on this same lock-owning thread.
        try:
            transition = owner.approval_publication(request, instruction)
        except (AutomationCustodyError, ProfileAccessRefusedError) as error:
            reply = AccessRefusal(
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


def _write_permit(
    channel: ByteChannel,
    permit: WorkerAuthorizationPermit | WorkerResponseScopePermit | WorkerAutomationInventoryPermit,
    *,
    deadline: float,
) -> None:
    """Write a permit; an inventory permit follows its transfer header as bounded chunks."""
    if not isinstance(permit, WorkerAutomationInventoryPermit):
        write_document(channel, permit, deadline=deadline)
        return
    payload = canonical_json_bytes(permit.model_dump(mode="json"))
    write_document(
        channel,
        WorkerAutomationInventoryTransfer(
            request_id=permit.request_id,
            runtime_boot_id=permit.runtime_boot_id,
            permit_id=permit.permit_id,
            byte_count=len(payload),
            payload_digest=sha256_hex(payload),
        ),
        deadline=deadline,
    )
    write_document_transfer(channel, payload, deadline=deadline)


def _require_allowed_request_family(
    request: WorkerAuthorityRequest | WorkerAutomationInventoryRequest,
    allowed: AccessAllowed | OperationResponseScopeAllowed | WorkerAutomationInventoryAllowed,
) -> None:
    """Refuse inventory or scope capabilities returned for a different request family."""
    # No inventory payload can be advertised through an ordinary
    # permit, and no scope-only response can become an effect permit.
    if isinstance(request, WorkerAutomationInventoryRequest):
        if not isinstance(allowed, WorkerAutomationInventoryAllowed):
            raise RefusalError(RefusalCode.INVALID_FRAME)
    elif isinstance(allowed, WorkerAutomationInventoryAllowed) or (
        isinstance(request, WorkerResponseScopeRequest) != isinstance(allowed, OperationResponseScopeAllowed)
    ):
        raise RefusalError(RefusalCode.INVALID_FRAME)
