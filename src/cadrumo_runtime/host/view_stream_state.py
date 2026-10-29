"""Retained view attach authority and relay leg state."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from uuid import UUID

from cadrumo.application.operations.models import OperationId
from cadrumo_client.contracts.contracts import ByteChannel, Peer
from cadrumo_client.contracts.transport import ConnectionContext
from cadrumo_client.contracts.view_stream import ViewState, ViewWorkerBind
from cadrumo_client.transport.native_wake import NativeWake

from ..adapters.worker_transport import WorkerChannel


@dataclass(frozen=True, slots=True)
class ViewAttachGrant:
    """Who may present a token: the exact attaching session, its person connection and native peer."""

    operation_id: OperationId
    profile_id: UUID
    session_id: UUID
    person_connection_id: UUID
    peer: Peer
    runtime_boot_id: UUID


@dataclass(slots=True)
class PendingViewAttach:
    """A single-use attach token and its authority."""

    token: bytes
    grant: ViewAttachGrant
    expires_at: float


@dataclass(slots=True)
class ViewWindowLeg:
    """The live window transport and its credit state."""

    channel: ByteChannel
    context: ConnectionContext
    grant: ViewAttachGrant
    stopping: NativeWake = field(default_factory=NativeWake)
    write_lock: Lock = field(default_factory=Lock)
    credit: int = 0
    ready: bool = False
    unbound: bool = False
    close_sent: bool = False


@dataclass(slots=True)
class ViewWorkerLeg:
    """The live worker transport and its credit state."""

    profile_id: UUID
    bind: ViewWorkerBind
    channel: WorkerChannel
    stopping: NativeWake = field(default_factory=NativeWake)
    write_lock: Lock = field(default_factory=Lock)
    credit: int = 0
    last_sequence: int | None = None
    last_state: ViewState | None = None
    window: ViewWindowLeg | None = None
    ended: bool = False
