"""The KDF transport refuses a pipe that stops accepting bytes.

A descriptor that can no longer progress reports zero accepted bytes instead of
raising. A frame writer that merely advances by that count spins forever, which
wedges the wrap or unwrap waiting on the worker with no refusal to translate.
"""

from __future__ import annotations

import os

import pytest

from ......tests.attribute_scope import scoped_attribute
from .._kdf_codec import KDF_FRAME_CONTROL, read_kdf_frame, write_kdf_frame

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_CALL_CEILING = 64


class _StalledPipe:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, fd: int, data: bytes | memoryview) -> int:
        self.calls += 1
        if self.calls > _CALL_CEILING:
            raise AssertionError("frame writer kept retrying a pipe that makes no progress")
        return 0


def test_a_stalled_pipe_refuses_the_frame_instead_of_spinning() -> None:
    stalled = _StalledPipe()

    with scoped_attribute(os, "write", stalled), pytest.raises(OSError, match="no progress"):
        write_kdf_frame(1, b"payload", kind=KDF_FRAME_CONTROL)

    assert stalled.calls == 1


def test_a_frame_still_round_trips_through_a_real_pipe() -> None:
    read_fd, write_fd = os.pipe()
    try:
        write_kdf_frame(write_fd, b"payload", kind=KDF_FRAME_CONTROL)
        assert read_kdf_frame(read_fd) == (KDF_FRAME_CONTROL, b"payload")
    finally:
        os.close(read_fd)
        os.close(write_fd)
