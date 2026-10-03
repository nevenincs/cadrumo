"""Bounded final-write barrier over real native runtime channels."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from threading import Event, Lock
from uuid import UUID

from cadrumo.adapters.local_runtime.framing import MAXIMUM_FRAME_BYTES
from cadrumo.adapters.local_runtime.windows import WindowsRuntimeEndpoint
from cadrumo.application.runtime.contracts import (
    RuntimeByteChannel,
    RuntimePeer,
    RuntimeRefusalCode,
    RuntimeRefusalError,
)


@dataclass
class ProjectionWriteBarrier:
    """Pause the synthetic private projection before the native write, without replacing it."""

    enabled: Event = field(default_factory=Event)
    entered: Event = field(default_factory=Event)
    release: Event = field(default_factory=Event)
    reply_kind: str = "operation_observed"
    request_id: UUID | None = None
    denial_received: Event = field(default_factory=Event)
    denial_written: Event = field(default_factory=Event)
    _events: list[str] = field(default_factory=list)
    _events_guard: Lock = field(default_factory=Lock)

    @staticmethod
    def _matches(
        payload: bytes | bytearray,
        field_name: str,
        value: str,
        *,
        request_id: UUID | None = None,
        framed: bool = False,
    ) -> bool:
        if framed:
            # Native writes contain one complete J + network uint32 + JSON frame.
            # Native reads supply the separately read JSON body instead.
            if len(payload) < 5 or payload[:1] != b"J":
                return False
            size = int.from_bytes(payload[1:5], byteorder="big")
            if not 0 < size <= MAXIMUM_FRAME_BYTES or size != len(payload) - 5:
                return False
            payload = payload[5:]
        try:
            document = json.loads(payload)
        except (ValueError, UnicodeError):
            return False
        if not isinstance(document, dict):
            return False
        selected = document.get(field_name)
        if not isinstance(selected, str) or selected != value:
            return False
        if request_id is None:
            return True
        returned_request = document.get("request_id")
        return isinstance(returned_request, str) and returned_request == str(request_id)

    def _record(self, event: str) -> None:
        with self._events_guard:
            self._events.append(event)

    def events(self) -> tuple[str, ...]:
        """Expose chronology only, never the native private document."""
        with self._events_guard:
            return tuple(self._events)

    def after_read(self, payload: bytes) -> None:
        if self.enabled.is_set() and self._matches(payload, "action", "automation_deny"):
            self._record("denial_received")
            self.denial_received.set()

    def after_write(self, payload: bytes | bytearray) -> None:
        if not self.enabled.is_set():
            return
        if self._matches(payload, "kind", self.reply_kind, request_id=self.request_id, framed=True):
            self._record("private_written")
        elif self._matches(payload, "kind", "automation_denied", framed=True):
            self._record("denial_written")
            self.denial_written.set()

    def before_write(self, payload: bytes | bytearray, *, deadline: float) -> None:
        if self.enabled.is_set() and self._matches(
            payload, "kind", self.reply_kind, request_id=self.request_id, framed=True
        ):
            self._record("private_entered")
            self.entered.set()
            if not self.release.wait(max(0, deadline - time.monotonic())):
                raise RuntimeRefusalError(RuntimeRefusalCode.DEADLINE_EXCEEDED)


@dataclass
class PausedProjectionChannel:
    """Retain the kernel-verified peer, real framing and original native deadlines."""

    channel: RuntimeByteChannel
    barrier: ProjectionWriteBarrier

    @property
    def peer(self) -> RuntimePeer:
        return self.channel.peer

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        payload = self.channel.read_exact(count, deadline=deadline)
        self.barrier.after_read(payload)
        return payload

    def read_ready(self) -> bool:
        return self.channel.read_ready()

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        self.barrier.before_write(payload, deadline=deadline)
        self.channel.write_all(payload, deadline=deadline)
        self.barrier.after_write(payload)

    def close(self) -> None:
        self.channel.close()


@dataclass
class PausedProjectionListener:
    """Delegate exclusive endpoint ownership and native peer authentication unchanged."""

    endpoint: WindowsRuntimeEndpoint
    barrier: ProjectionWriteBarrier

    @property
    def storage_identity(self) -> str:
        return self.endpoint.storage_identity

    def listen(self) -> None:
        self.endpoint.listen()

    def accept(self, *, timeout: float) -> RuntimeByteChannel:
        return PausedProjectionChannel(self.endpoint.accept(timeout=timeout), self.barrier)

    def close(self) -> None:
        self.endpoint.close()
