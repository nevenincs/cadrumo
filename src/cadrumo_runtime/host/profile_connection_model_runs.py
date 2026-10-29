"""Model runs relayed from a profile's worker to the profile's admitted agent service.

The worker's request waits here, under a run id, while the service is told it
exists. The service then fetches it, and answers it, with requests on its own
connection, under its exact lease. The runtime never reads a body or a reply:
both cross as secret frames and are wiped once handed on. Nothing in either
direction is a credential.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Event
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.contracts import ByteChannel
from cadrumo_client.contracts.model_runs import (
    ModelRunCompleted,
    ModelRunCompleteRequest,
    ModelRunFetched,
    ModelRunFetchRequest,
    ModelRunOutcome,
    ModelRunRefusalCode,
    ModelRunRequested,
)
from cadrumo_client.contracts.profile_access import AccessRefusal, ProfileStatus, SecretReady
from cadrumo_client.contracts.service_access import ServiceCapability, ServiceLease
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.transport.frame_io import write_document
from cadrumo_client.transport.model_run_frames import read_secret_chunks, write_secret_chunks
from cadrumo_runtime.contracts.worker_authorization import WorkerModelRun

if TYPE_CHECKING:
    from .profile_connections import RuntimeProfileConnections
    from .service_connection_records import ServiceConnection

_LOOKUP_ANSWER_SECONDS = 30.0
"""How long a lane lookup or selections read waits for the service; it reads settings and runs nothing."""

_ANSWER_MARGIN_SECONDS = 120.0
"""Time beyond a run's own deadline for the service to start the run and report the outcome it reached.

Starting a run on a lane whose model runs on this computer loads the model
first, which the service allows 90 s; the run's deadline counts from its start.
"""

_TRANSFER_SECONDS = 10
"""How long a request's frames may take, counted from when they are due, never from dispatch.

Waiting for the guards and the peer recheck is the runtime's queueing, not the service's time.
"""

_REPLY_WRITE_SECONDS = 5


@dataclass
class PendingModelRun:
    """One worker request waiting for the service that was told about it."""

    profile_id: UUID
    connection_id: UUID
    lease_id: UUID
    command: WorkerModelRun
    body: bytearray = field(repr=False)
    answered: Event = field(default_factory=Event)
    fetched: bool = False
    outcome: ModelRunOutcome | None = None
    text: bytearray = field(default_factory=bytearray, repr=False)

    def answer(self, outcome: ModelRunOutcome, text: bytearray | None = None) -> None:
        """Record the answer once and wake the waiting worker relay."""
        if self.answered.is_set():
            if text is not None:
                text[:] = bytes(len(text))
            return
        self.outcome, self.text = outcome, text if text is not None else bytearray()
        self.answered.set()

    def wipe(self) -> None:
        """Forget the body; it is never kept once the service has it or nobody waits."""
        self.body[:] = bytes(len(self.body))


class ProfileConnectionModelRunsMixin:
    """Relay one worker's model runs to the agent service admitted for its profile."""

    def _relay_model_run(
        self: RuntimeProfileConnections, profile_id: UUID, command: WorkerModelRun, body: bytearray
    ) -> tuple[ModelRunOutcome, bytearray]:
        """Tell the profile's admitted service about the run, then wait for its answer or the deadline."""
        run_id = uuid4()
        with self._guard:
            service = _model_run_service(self, profile_id)
            if service is None or service.lease is None:
                body[:] = bytes(len(body))
                return ModelRunOutcome(refusal=ModelRunRefusalCode.SERVICE_UNAVAILABLE), bytearray()
            pending = PendingModelRun(
                profile_id=profile_id,
                connection_id=service.lease.connection_id,
                lease_id=service.lease.lease_id,
                command=command,
                body=body,
            )
            self._model_runs[run_id] = pending
        self._events.publish(
            ModelRunRequested(
                runtime_boot_id=self.boot,
                connection_id=pending.connection_id,
                profile_id=profile_id,
                run_id=run_id,
            )
        )
        wait = _LOOKUP_ANSWER_SECONDS if command.header is None else command.header.deadline_seconds
        try:
            if not pending.answered.wait(wait + (0 if command.header is None else _ANSWER_MARGIN_SECONDS)):
                pending.answer(ModelRunOutcome(refusal=ModelRunRefusalCode.TIMEOUT))
        finally:
            with self._guard:
                self._model_runs.pop(run_id, None)
            pending.wipe()
        outcome = pending.outcome or ModelRunOutcome(refusal=ModelRunRefusalCode.RUN_FAILED)
        return outcome, pending.text

    def _fail_model_runs(self: RuntimeProfileConnections, connection_id: UUID) -> None:
        """A service connection ended: every run waiting on it is answered as unavailable at once."""
        with self._guard:
            waiting = [run for run in self._model_runs.values() if run.connection_id == connection_id]
        for run in waiting:
            run.answer(ModelRunOutcome(refusal=ModelRunRefusalCode.SERVICE_UNAVAILABLE))

    def _withdraw_lease(self: RuntimeProfileConnections, service: ServiceConnection) -> None:
        """Withdraw the service's lease once no disclosure admitted under it is still being written.

        Called under ``self._guard``. Once the lease is cleared no fetch can claim
        it; a fetch already writing finishes its bounded output first. Every run
        bound to the withdrawn lease is then failed, so no retirement is published
        while a disclosure under that lease is in flight, and none follows it.
        """
        lease = service.lease
        service.lease = None
        while service.disclosing:
            self._disclosures.wait()
        if lease is None:
            return
        for run in self._model_runs.values():
            if run.lease_id == lease.lease_id:
                run.answer(ModelRunOutcome(refusal=ModelRunRefusalCode.SERVICE_UNAVAILABLE))

    def model_run_fetch(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        channel: ByteChannel,
        request: ModelRunFetchRequest,
    ) -> None:
        """Hand the waiting request to the service it was announced to, once.

        The lease the run was announced under fences the disclosure: it must still
        be the service's exact lease after the profile and peer are rechecked, and
        its withdrawal waits until the bounded header and body writes end.
        """
        with self._guard:
            pending = self._model_runs.get(request.run_id)
            service = self._services.get(context.connection_id)
            lease = None if service is None else service.lease
            if (
                pending is None
                or service is None
                or lease is None
                or not _admitted_lease(self, context, request)
                or not fetch_pending_matches(pending, context, lease)
            ):
                return _refuse(self, context, channel, request.request_id)
            pending.fetched = True
        if not _service_still_admitted(self, context, channel, request):
            pending.answer(ModelRunOutcome(refusal=ModelRunRefusalCode.SERVICE_UNAVAILABLE))
            return _refuse(self, context, channel, request.request_id)
        with self._guard:
            if service.lease is not lease:
                pending.answer(ModelRunOutcome(refusal=ModelRunRefusalCode.SERVICE_UNAVAILABLE))
                return _refuse(self, context, channel, request.request_id)
            service.disclosing += 1
        try:
            command = pending.command
            deadline = time.monotonic() + _TRANSFER_SECONDS
            write_document(
                channel,
                ModelRunFetched(
                    request_id=request.request_id,
                    runtime_boot_id=self.boot,
                    connection_id=context.connection_id,
                    run_id=request.run_id,
                    role=command.role,
                    header=command.header,
                    body_byte_count=len(pending.body),
                ),
                deadline=deadline,
            )
            write_secret_chunks(channel, pending.body, deadline=deadline)
        finally:
            with self._guard:
                service.disclosing -= 1
                self._disclosures.notify_all()

    def model_run_complete(
        self: RuntimeProfileConnections,
        context: ConnectionContext,
        channel: ByteChannel,
        request: ModelRunCompleteRequest,
    ) -> None:
        """Take the service's answer to a request it fetched and wake the worker that waits for it.

        The service controls how long the answer's text takes to arrive, so the
        admission seen before it is read grants nothing afterwards: the profile,
        the peer and the exact lease are checked again once it is in, and the
        answer is recorded under the guard that a lease withdrawal holds.
        """
        with self._guard:
            pending = self._model_runs.get(request.run_id)
            service = self._services.get(context.connection_id)
            lease = None if service is None else service.lease
            admitted = _admitted_lease(self, context, request)
        outcome = request.outcome
        if not admitted or not _service_still_admitted(self, context, channel, request):
            return _refuse(self, context, channel, request.request_id)
        text = bytearray()
        if outcome.text_byte_count:
            deadline = time.monotonic() + _TRANSFER_SECONDS
            write_document(
                channel,
                SecretReady(
                    request_id=request.request_id, runtime_boot_id=self.boot, connection_id=context.connection_id
                ),
                deadline=deadline,
            )
            text = read_secret_chunks(channel, outcome.text_byte_count, deadline=deadline)
        accepted = False
        if (
            pending is not None
            and completion_pending_matches(pending, context, request)
            and _service_still_admitted(self, context, channel, request)
        ):
            with self._guard:
                if completion_is_current(
                    service,
                    lease,
                    self._services.get(context.connection_id),
                    self._model_runs.get(request.run_id),
                    pending,
                    lambda: _admitted_lease(self, context, request),
                ):
                    pending.answer(outcome, text)
                    accepted = True
        if not accepted:
            text[:] = bytes(len(text))
        write_document(
            channel,
            ModelRunCompleted(
                request_id=request.request_id,
                runtime_boot_id=self.boot,
                connection_id=context.connection_id,
                run_id=request.run_id,
                accepted=accepted,
            ),
            deadline=time.monotonic() + _REPLY_WRITE_SECONDS,
        )


def fetch_pending_matches(pending: PendingModelRun, context: ConnectionContext, lease: ServiceLease) -> bool:
    """Allow only the announced service to fetch a request once."""
    return pending.connection_id == context.connection_id and pending.lease_id == lease.lease_id and not pending.fetched


def completion_pending_matches(
    pending: PendingModelRun | None, context: ConnectionContext, request: ModelRunCompleteRequest
) -> bool:
    """Match the fetched proof owner and answer to the announced phase."""
    return (
        pending is not None
        and pending.connection_id == context.connection_id
        and pending.lease_id == request.lease_id
        and pending.fetched
        and _answers_its_phase(pending.command, request.outcome)
    )


def completion_is_current(
    service: ServiceConnection | None,
    lease: ServiceLease | None,
    current_service: ServiceConnection | None,
    current_pending: PendingModelRun | None,
    pending: PendingModelRun | None,
    admitted: Callable[[], bool],
) -> bool:
    """Recheck the same lease and unanswered owner while holding the guard."""
    return (
        service is not None
        and lease is not None
        and service.lease is lease
        and current_service is service
        and pending is not None
        and current_pending is pending
        and admitted()
        and not pending.answered.is_set()
    )


def _model_run_service(connections: RuntimeProfileConnections, profile_id: UUID) -> ServiceConnection | None:
    """Return the admitted service connection of ``profile_id`` whose installed descriptor admits model runs.

    The descriptor is the runtime's installed one, retained with the natively
    verified peer of that exact connection; nothing the service sends can
    declare the capability, and no other connection's descriptor lends it.
    """
    for service in connections._services.values():
        lease = service.lease
        if (
            lease is not None
            and lease.profile_id == profile_id
            and lease.runtime_boot_id == connections.boot
            and service.descriptor.declares(ServiceCapability.MODEL_RUN)
        ):
            return service
    return None


def _admitted_lease(
    connections: RuntimeProfileConnections,
    context: ConnectionContext,
    request: ModelRunFetchRequest | ModelRunCompleteRequest,
) -> bool:
    """Whether ``request`` names the exact live lease of the service on this connection."""
    service = connections._services.get(context.connection_id)
    connection = connections._connections.get(context.connection_id)
    if (
        service is None
        or connection is None
        or service.lease is None
        or not service.descriptor.declares(ServiceCapability.MODEL_RUN)
    ):
        return False
    lease = service.lease
    return (
        connection.context == context
        and lease.runtime_boot_id == connections.boot
        and lease.profile_id == request.profile_id
        and lease.session_id == request.session_id
        and lease.lease_id == request.lease_id
        and connection.session_id == request.session_id
    )


def _service_still_admitted(
    connections: RuntimeProfileConnections,
    context: ConnectionContext,
    channel: ByteChannel,
    request: ModelRunFetchRequest | ModelRunCompleteRequest,
) -> bool:
    """Recheck the profile's status and the service's native peer, as every record exchange does."""
    with connections._guard:
        service = connections._services.get(context.connection_id)
        connection = connections._connections.get(context.connection_id)
        host = connections._profiles.get(request.profile_id)
    if service is None or connection is None or host is None:
        return False
    with host.guard:
        status = connections._status(connection, host, request.request_id, request.session_id)
        if not isinstance(status, ProfileStatus) or status.status.denial is not None:
            return False
    return connections._service_verifier.recheck_service(context, channel, service.peer)


def _answers_its_phase(command: WorkerModelRun, outcome: ModelRunOutcome) -> bool:
    """A lookup is answered by a lane, a selections read by every role's state, a run by a served run.

    Each may instead be answered by a refusal.
    """
    if outcome.refusal is not None:
        return True
    if command.header is not None:
        return outcome.served is not None
    return outcome.lane is not None if command.role is not None else outcome.selections is not None


def _refuse(
    connections: RuntimeProfileConnections, context: ConnectionContext, channel: ByteChannel, request_id: UUID
) -> None:
    write_document(
        channel,
        AccessRefusal(
            request_id=request_id,
            runtime_boot_id=connections.boot,
            connection_id=context.connection_id,
            code=AccessDenialCode.OPERATION_DENIED,
        ),
        deadline=time.monotonic() + _REPLY_WRITE_SECONDS,
    )


__all__ = ["PendingModelRun", "ProfileConnectionModelRunsMixin"]
