"""Current-pointer reads survive concurrent atomic record publication."""

from __future__ import annotations

import threading
import tomllib
from pathlib import Path

import pytest

from ..bucket_pointer import BucketPointer
from ..bucket_pointer import read_pointer, write_pointer

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CHURN_CYCLES = 400


def _churn(root: Path, done: threading.Event) -> None:
    """Publish selected and durable-absent states through the current writer."""
    try:
        revision = 0
        for _ in range(_CHURN_CYCLES):
            try:
                revision += 1
                write_pointer(root, BucketPointer.selected(bucket_id="0" * 32, transition_revision=revision))
                revision += 1
                write_pointer(root, BucketPointer.absent(transition_revision=revision))
            except OSError:
                # Writer-side sharing refusal has a separate test; it is not
                # the property under test here.
                continue
    finally:
        done.set()


def _race(root: Path) -> tuple[int, int]:
    """Read in a loop against a real publishing writer."""
    done = threading.Event()
    writer = threading.Thread(target=_churn, args=(root, done))
    writer.start()
    present = absent = 0
    try:
        while not done.is_set():
            if read_pointer(root).bucket_id is None:
                absent += 1
            else:
                present += 1
    finally:
        writer.join(30)
    return present, absent


def test_read_pointer_never_raises_while_a_peer_switches_profile(tmp_path: Path) -> None:
    """DISCRIMINATING: a startup reader survives an atomic state transition."""
    present, absent = _race(tmp_path)

    assert present > 0, "the reader never observed a selected pointer; the race did not overlap"
    assert absent > 0, "the reader never observed a tombstone; the race did not overlap"


def test_an_absent_pointer_is_a_current_absent_coordinate(tmp_path: Path) -> None:
    """Absence is a record, while malformed current bytes still fail closed."""
    assert read_pointer(tmp_path) == BucketPointer.absent(transition_revision=0)

    (tmp_path / "active-profile").write_text("this is not valid toml", encoding="utf-8")
    with pytest.raises(tomllib.TOMLDecodeError):
        read_pointer(tmp_path)
