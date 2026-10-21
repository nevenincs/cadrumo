"""A model-run body crosses as consecutive secret frames and is reassembled exactly."""

from __future__ import annotations

import time

import pytest

from ...contracts.contracts import RefusalError
from ..frame_io import MAXIMUM_SECRET_BYTES, write_secret
from ..model_run_frames import read_secret_chunks, write_secret_chunks
from .memory_channel import MemoryChannel

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]


def _pair() -> tuple[MemoryChannel, MemoryChannel]:
    left, right = MemoryChannel(), MemoryChannel()
    left.pair(right)
    return left, right


@pytest.mark.parametrize("size", [0, 1, MAXIMUM_SECRET_BYTES, MAXIMUM_SECRET_BYTES * 2 + 17])
def test_a_body_of_any_size_up_to_its_bound_round_trips_and_the_sent_copy_is_wiped(size: int) -> None:
    sender, receiver = _pair()
    original = bytes((index * 7) % 251 for index in range(size))
    outgoing = bytearray(original)

    write_secret_chunks(sender, outgoing, deadline=time.monotonic() + 5)
    received = read_secret_chunks(receiver, size, deadline=time.monotonic() + 5)

    assert bytes(received) == original
    assert outgoing == bytearray(size)
    assert all(len(frame) <= MAXIMUM_SECRET_BYTES + 5 for frame in sender.writes)


def test_more_bytes_than_declared_is_refused() -> None:
    sender, receiver = _pair()
    write_secret(sender, bytearray(b"twelve bytes"), deadline=time.monotonic() + 5)

    with pytest.raises(RefusalError):
        read_secret_chunks(receiver, 4, deadline=time.monotonic() + 5)
