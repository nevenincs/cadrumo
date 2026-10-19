"""Model-run bodies and replies carried as a run of bounded secret frames.

A model-run body may hold a taxpayer's document, so it never travels as a
document frame. It is split into secret frames no larger than one frame
allows, and the receiver reassembles exactly the declared length.
"""

from __future__ import annotations

from ..contracts.contracts import ByteChannel, RefusalCode, RefusalError
from .frame_io import MAXIMUM_SECRET_BYTES, read_secret, write_secret


def write_secret_chunks(channel: ByteChannel, data: bytearray, *, deadline: float) -> None:
    """Send ``data`` as consecutive secret frames, then wipe it; an empty buffer sends nothing."""
    try:
        for start in range(0, len(data), MAXIMUM_SECRET_BYTES):
            write_secret(channel, bytearray(data[start : start + MAXIMUM_SECRET_BYTES]), deadline=deadline)
    finally:
        data[:] = bytes(len(data))


def read_secret_chunks(channel: ByteChannel, byte_count: int, *, deadline: float) -> bytearray:
    """Reassemble exactly ``byte_count`` bytes from secret frames, wiping the result on failure."""
    received = bytearray()
    try:
        while len(received) < byte_count:
            with read_secret(channel, deadline=deadline) as frame:
                if len(received) + len(frame) > byte_count:
                    raise RefusalError(RefusalCode.INVALID_FRAME)
                received.extend(frame)
    except BaseException:
        received[:] = bytes(len(received))
        raise
    return received


__all__ = ["read_secret_chunks", "write_secret_chunks"]
