"""Bounded final-write barrier over real native runtime channels."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Event

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

    def before_write(self, payload: bytes | bytearray, *, deadline: float) -> None:
        if self.enabled.is_set() and b'"kind":"operation_observed"' in payload:
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
        return self.channel.read_exact(count, deadline=deadline)

    def read_ready(self) -> bool:
        return self.channel.read_ready()

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        self.barrier.before_write(payload, deadline=deadline)
        self.channel.write_all(payload, deadline=deadline)

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
