"""Retained service connection and pending human admission records."""

from __future__ import annotations

import logging
from collections.abc import Generator
from contextlib import AbstractContextManager, contextmanager
from dataclasses import dataclass, field
from time import monotonic
from uuid import UUID

from cadrumo.application.operations.person_acts import is_persons_frontend
from cadrumo.core.diagnostic_log import diagnostic_event
from cadrumo.core.logging import get_logger
from cadrumo_client.contracts.access_refusals import AccessDenied
from cadrumo_client.contracts.contracts import ByteChannel
from cadrumo_client.contracts.service_access import (
    InstalledServiceDescriptor,
    ServiceAdmission,
    ServiceAdmissionPending,
    ServiceAdmissionStatusQuery,
    ServiceConnected,
    ServiceLease,
    VerifiedServicePeer,
)
from cadrumo_client.contracts.transport import ConnectionContext

from .profile_connection import ProfileConnection


@dataclass(slots=True)
class ServiceConnection:
    """Retain a verified service peer, channel, descriptor, and optional lease."""

    descriptor: InstalledServiceDescriptor
    peer: VerifiedServicePeer
    channel: ByteChannel
    lease: ServiceLease | None = None
    # Model-run disclosures being written under the lease; withdrawing it waits for them.
    disclosing: int = 0


@dataclass(slots=True)
class PendingServiceAdmission:
    """One retained verification job; its handle grants no authority."""

    admission_id: UUID
    context: ConnectionContext
    request: ServiceAdmission
    cancelled: bool = False
    started: bool = False
    complete: bool = False
    result: ServiceConnected | AccessDenied | None = None
    queued_at: float = field(default_factory=monotonic)
    """When the job was queued, so its log can say how long it waited for a verification slot."""
    started_at: float | None = None

    def active(self) -> bool:
        """Read cancellation afresh after work that can run beside the owner."""
        return not self.cancelled


def admission_coordinates_match(
    pending: PendingServiceAdmission, context: ConnectionContext, request: ServiceAdmissionStatusQuery
) -> bool:
    """Check the exact pending admission coordinates."""
    return (
        pending.active()
        and pending.context == context
        and pending.request.profile_id == request.profile_id
        and pending.request.session_id == request.session_id
        and pending.request.recipient_connection_id == request.recipient_connection_id
        and pending.request.service_id == request.service_id
    )


def admission_status_matches(
    pending: PendingServiceAdmission,
    holder: ProfileConnection | None,
    context: ConnectionContext,
    request: ServiceAdmissionStatusQuery,
) -> bool:
    """Check the pending request and its live holder."""
    return (
        admission_coordinates_match(pending, context, request)
        and holder is not None
        and holder.session_id == request.session_id
        and not holder.disconnecting
    )


def person_holder_matches(holder: ProfileConnection, context: ConnectionContext, request: ServiceAdmission) -> bool:
    """Require the exact person-held session for admission."""
    return (
        holder.context == context
        and holder.profile_id == request.profile_id
        and holder.session_id == request.session_id
        and is_persons_frontend(holder.frontend)
    )


def cancel_service_admissions(
    admissions: dict[UUID, PendingServiceAdmission], connection_id: UUID | None, session_id: UUID | None
) -> None:
    """Fence pending work for a departing connection or session."""
    for admission_id, pending in tuple(admissions.items()):
        if (
            connection_id is None
            or pending.context.connection_id == connection_id
            or pending.request.recipient_connection_id == connection_id
            or (session_id is not None and pending.request.session_id == session_id)
        ):
            pending.cancelled = True
            if pending.complete or not pending.started:
                admissions.pop(admission_id, None)


def pending_service_reply(boot: UUID, pending: PendingServiceAdmission, request_id: UUID) -> ServiceAdmissionPending:
    """Correlate a retained pending admission to its request."""
    return ServiceAdmissionPending(
        request_id=request_id,
        runtime_boot_id=boot,
        connection_id=pending.context.connection_id,
        profile_id=pending.request.profile_id,
        service_id=pending.request.service_id,
        admission_id=pending.admission_id,
    )


def cancel_pending_status(
    admissions: dict[UUID, PendingServiceAdmission],
    boot: UUID,
    pending: PendingServiceAdmission,
    request: ServiceAdmissionStatusQuery,
) -> ServiceConnected | ServiceAdmissionPending:
    """Cancel only a pending admission while preserving already published completion."""
    if isinstance(pending.result, ServiceConnected):
        admissions.pop(request.admission_id, None)
        return pending.result.model_copy(update={"request_id": request.request_id})
    pending.cancelled = True
    if pending.complete or not pending.started:
        admissions.pop(request.admission_id, None)
    return pending_service_reply(boot, pending, request.request_id).model_copy(update={"cancelled": True})


_LOGGER = get_logger(__name__)


@contextmanager
def timed_stage(stages: dict[str, float], name: str) -> Generator[None]:
    """Record in ``stages`` how long the enclosed work took, however it ends."""
    began = monotonic()
    try:
        yield
    finally:
        stages[name] = monotonic() - began


@contextmanager
def entered_timed(lock: AbstractContextManager[object], stages: dict[str, float], name: str) -> Generator[None]:
    """Hold ``lock`` for the enclosed work, recording in ``stages`` how long entering it waited."""
    began = monotonic()
    with lock:
        stages[name] = monotonic() - began
        yield


def log_admission_timing(
    pending: PendingServiceAdmission, stages: dict[str, float], result: ServiceConnected | AccessDenied
) -> None:
    """Log how long one service admission waited and spent in each stage, beside the desktop's own timing.

    Only durations and the outcome are logged, never an identity.
    """
    started = pending.started_at
    fields: dict[str, str | int | float | bool | None] = {
        "outcome": "admitted" if isinstance(result, ServiceConnected) else "denied",
        "queued_ms": None if started is None else round((started - pending.queued_at) * 1000),
        "total_ms": round((monotonic() - pending.queued_at) * 1000),
    }
    for stage in ("recheck", "guard_wait", "commit"):
        spent = stages.get(stage)
        fields[f"{stage}_ms"] = None if spent is None else round(spent * 1000)
    diagnostic_event(_LOGGER, "service_admission_timing", fields=fields, level=logging.INFO)
