"""Metadata change time used to detect a file altered after admission."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from ..file_change_time import file_change_time_ns

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_change_time_advances_when_only_the_write_time_is_rewound(tmp_path: Path) -> None:
    """Restoring the write time must not hide that the file's metadata changed."""
    path = tmp_path / "admitted.bin"
    path.write_bytes(b"admitted")
    before = path.stat()
    admitted = file_change_time_ns(path, before)
    # NTFS stamps ChangeTime from a clock that advances in ~15.6 ms ticks.
    time.sleep(0.05)

    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
    os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    after = path.stat()

    assert after.st_mtime_ns == before.st_mtime_ns
    assert file_change_time_ns(path, after) > admitted


def test_repeated_queries_on_an_unchanged_file_agree(tmp_path: Path) -> None:
    path = tmp_path / "admitted.bin"
    path.write_bytes(b"admitted")
    status = path.stat()

    assert len({file_change_time_ns(path, status) for _ in range(200)}) == 1
