"""A byte channel that forwards every call to a real channel, for tests that observe or fault one door."""

from __future__ import annotations

from ...contracts.contracts import ByteChannel, ChannelWake, Peer


class DelegatingChannel:
    """Forward the whole channel contract to ``channel`` so a subclass overrides only the call it faults."""

    def __init__(self, channel: ByteChannel) -> None:
        self.channel = channel

    @property
    def peer(self) -> Peer:
        return self.channel.peer

    def read_exact(self, count: int, *, deadline: float) -> bytes:
        return self.channel.read_exact(count, deadline=deadline)

    def read_ready(self) -> bool:
        return self.channel.read_ready()

    def wait_readable(self, *wakes: ChannelWake) -> bool:
        return self.channel.wait_readable(*wakes)

    def write_all(self, payload: bytes | bytearray, *, deadline: float) -> None:
        self.channel.write_all(payload, deadline=deadline)

    def close(self) -> None:
        self.channel.close()
