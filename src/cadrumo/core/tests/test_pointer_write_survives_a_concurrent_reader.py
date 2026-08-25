"""Current-pointer publication survives a peer reading the record."""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from ..bucket_pointer import BucketPointer
from ..bucket_pointer import read_pointer, write_pointer

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_WRITE_CYCLES = 300


def _read_until(root: Path, stop: threading.Event, seen: dict[str, int]) -> None:
    """Hold brief real read handles the way a starting process does."""
    while not stop.is_set():
        try:
            observed = read_pointer(root)
        except OSError:
            continue
        seen["absent" if observed.bucket_id is None else "present"] += 1


def test_a_profile_switch_is_not_refused_by_a_peer_reading_the_pointer(tmp_path: Path) -> None:
    """DISCRIMINATING: atomic write tolerates a live current-record reader."""
    stop = threading.Event()
    seen = {"present": 0, "absent": 0}
    reader = threading.Thread(target=_read_until, args=(tmp_path, stop, seen))
    reader.start()
    try:
        revision = 0
        for _ in range(_WRITE_CYCLES):
            revision += 1
            write_pointer(tmp_path, BucketPointer.selected(bucket_id="0" * 32, transition_revision=revision))
            revision += 1
            write_pointer(tmp_path, BucketPointer.absent(transition_revision=revision))
    finally:
        stop.set()
        reader.join(30)

    assert seen["present"] > 0, "the reader never observed a selected pointer; the race did not overlap"
    assert seen["absent"] > 0, "the reader never observed a tombstone; the race did not overlap"


def test_a_writer_still_reports_an_unreplaceable_target(tmp_path: Path) -> None:
    """ANTI-TAUTOLOGY: retrying sharing contention does not hide all refusals."""
    (tmp_path / "active-profile").mkdir()

    with pytest.raises(OSError):
        write_pointer(tmp_path, BucketPointer.selected(bucket_id="0" * 32, transition_revision=1))
