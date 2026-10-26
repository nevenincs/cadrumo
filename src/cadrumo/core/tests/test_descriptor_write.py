"""A descriptor write completes a partial write and refuses a stalled one."""

from __future__ import annotations

import os

import pytest

from ...tests.attribute_scope import scoped_attribute
from ..descriptor_write import write_all

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CALL_CEILING = 64
"""A refusal must arrive long before this; reaching it means the loop spun."""


class _ScriptedDescriptor:
    """Stand-in for ``os.write`` that accepts at most ``accept`` bytes per call."""

    def __init__(self, accept: int) -> None:
        self.accept = accept
        self.calls = 0
        self.received = bytearray()

    def __call__(self, fd: int, data: bytes | memoryview) -> int:
        self.calls += 1
        if self.calls > _CALL_CEILING:
            raise AssertionError("write loop kept retrying a descriptor that makes no progress")
        taken = bytes(data[: self.accept])
        self.received.extend(taken)
        return len(taken)


def test_a_partial_write_resumes_from_the_accepted_offset() -> None:
    descriptor = _ScriptedDescriptor(accept=3)
    payload = b"0123456789"

    with scoped_attribute(os, "write", descriptor):
        write_all(1, payload)

    assert bytes(descriptor.received) == payload
    assert descriptor.calls == 4


def test_a_descriptor_that_accepts_nothing_is_refused() -> None:
    descriptor = _ScriptedDescriptor(accept=0)

    with scoped_attribute(os, "write", descriptor), pytest.raises(OSError, match="no progress"):
        write_all(1, b"payload")

    assert descriptor.calls == 1


def test_an_empty_payload_never_touches_the_descriptor() -> None:
    descriptor = _ScriptedDescriptor(accept=0)

    with scoped_attribute(os, "write", descriptor):
        write_all(1, b"")

    assert descriptor.calls == 0
