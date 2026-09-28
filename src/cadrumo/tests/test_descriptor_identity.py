"""The descriptor-closure check follows the open file, not the reusable number."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from .descriptor_identity import descriptor_identity, descriptor_was_closed

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_an_open_descriptor_is_not_reported_closed() -> None:
    reader, writer = os.pipe()
    try:
        identity = descriptor_identity(reader)
        assert not descriptor_was_closed(reader, identity)
    finally:
        os.close(reader)
        os.close(writer)


def test_a_closed_descriptor_is_reported_closed() -> None:
    reader, writer = os.pipe()
    os.close(writer)
    identity = descriptor_identity(reader)
    os.close(reader)

    assert descriptor_was_closed(reader, identity)


def test_a_closed_number_reused_by_another_file_is_still_reported_closed(tmp_path: Path) -> None:
    """The case a bare ``os.fstat`` check misreports as still open."""
    reader, writer = os.pipe()
    os.close(writer)
    identity = descriptor_identity(reader)
    os.close(reader)
    occupant = tmp_path / "occupant"
    occupant.write_bytes(b"")
    reused = os.open(occupant, os.O_RDONLY)
    try:
        if reused != reader:
            os.dup2(reused, reader)
        assert descriptor_identity(reader) == descriptor_identity(reused)

        assert descriptor_was_closed(reader, identity)
    finally:
        if reused != reader:
            os.close(reader)
        os.close(reused)
