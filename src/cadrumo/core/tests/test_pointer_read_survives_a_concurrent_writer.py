"""Reading the active-profile pointer survives a concurrent switch.

``read_pointer`` sits on the ``Settings()`` bootstrap path, so every process
resolves the pointer as it starts. A peer switching profile rewrites that file
through write-then-rename and clears it through ``unlink``, which leaves the
reader looking at a file being replaced underneath it.

Two failures were measured on Windows under concurrent access, and both crashed
a starting process with a raw ``OSError`` rather than answering the question
asked:

- the file vanished between ``is_file()`` and the open, raising
  ``FileNotFoundError`` from a function documented to answer ``None`` when the
  pointer is absent;
- the open was refused while a writer held the file, raising
  ``PermissionError`` -- with ``winerror`` unset, so contention is not
  distinguishable from a denying ACL by inspection.

Driven as a real race against the real IO functions rather than by injecting
errors, because the failure is a property of the filesystem's behaviour under
contention and an injected exception would only re-assert the handler.
"""

from __future__ import annotations

import threading
import tomllib
from collections.abc import Callable
from pathlib import Path

import pytest

from .._bucket_pointer import BucketPointer
from .._bucket_pointer_io import capture_pointer, clear_pointer, read_pointer, restore_pointer

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CHURN_CYCLES = 400


def _churn(root: Path, payload: bytes, done: threading.Event) -> None:
    """Rewrite and clear the pointer the way a peer profile switch does."""
    try:
        for _ in range(_CHURN_CYCLES):
            try:
                restore_pointer(root, payload)
                clear_pointer(root)
            except OSError:
                # The writer losing to a reader's open handle is the other half
                # of this window and is not what this test governs.
                continue
    finally:
        done.set()


def _race(root: Path, reader: Callable[[Path], object | None]) -> tuple[int, int]:
    """Run ``reader`` in a loop against a churning writer; count what it saw."""
    payload = BucketPointer(bucket_id="0" * 32, schema_version=1).to_toml().encode("utf-8")
    done = threading.Event()
    writer = threading.Thread(target=_churn, args=(root, payload, done))
    writer.start()
    present = absent = 0
    try:
        while not done.is_set():
            if reader(root) is None:
                absent += 1
            else:
                present += 1
    finally:
        writer.join(30)
    return present, absent


def test_read_pointer_never_raises_while_a_peer_switches_profile(tmp_path: Path) -> None:
    """DISCRIMINATING: the crash a starting process hit mid-switch.

    Any escaping ``OSError`` fails the test by propagating out of the loop.
    """
    present, absent = _race(tmp_path, read_pointer)

    assert present > 0, "the reader never observed a written pointer; the race did not overlap"
    assert absent > 0, "the reader never observed a cleared pointer; the race did not overlap"


def test_capture_pointer_never_raises_while_a_peer_switches_profile(tmp_path: Path) -> None:
    """The sibling read, which the custody snapshot takes.

    It answered absence correctly already but shared the refusal window, so it
    is pinned here rather than left to be discovered separately.
    """
    present, absent = _race(tmp_path, capture_pointer)

    assert present > 0, "the reader never observed a written pointer; the race did not overlap"
    assert absent > 0, "the reader never observed a cleared pointer; the race did not overlap"


def test_an_absent_pointer_is_still_absence_rather_than_an_error(tmp_path: Path) -> None:
    """ANTI-TAUTOLOGY: tolerating the race must not tolerate everything.

    A reader that swallowed OSError wholesale would pass the races above while
    reporting a corrupt or unreadable pointer as "no pointer". Absence stays
    ``None`` and a malformed pointer still raises.
    """
    assert read_pointer(tmp_path) is None
    assert capture_pointer(tmp_path) is None

    (tmp_path / "active-profile").write_text("this is not valid toml", encoding="utf-8")
    with pytest.raises(tomllib.TOMLDecodeError):
        read_pointer(tmp_path)
