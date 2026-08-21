"""Switching profile survives a peer process reading the pointer.

The custody root lock serialises pointer WRITERS. It does not cover readers:
every process resolves the active-profile pointer as it starts, and those reads
take no lock. On Windows a peer's open handle refuses the writer's replace and
unlink outright, so a profile switch or a logout could fail with a raw
``PermissionError`` while correctly holding the lock that was supposed to make
it safe.

Measured before the fix, over an eight-second race against a reader loop: 426
``ERROR_SHARING_VIOLATION`` and 115 ``ERROR_ACCESS_DENIED`` refusals. Logout is
the sharpest caller -- it closes the session artefacts BEFORE clearing the
pointer, so a refusal there leaves the secrets correctly zeroised but the
pointer still naming the profile, and reports a raw OS error to the operator.

Driven as a real race for the same reason as the read-side gate: the failure is
a property of the filesystem under contention, and an injected error would only
re-assert the handler.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest

from .._bucket_pointer import BucketPointer
from .._bucket_pointer_io import capture_pointer, clear_pointer, read_pointer, restore_pointer

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_WRITE_CYCLES = 300


def _read_until(root: Path, stop: threading.Event, seen: dict[str, int]) -> None:
    """Hold brief read handles on the pointer, the way a starting process does."""
    while not stop.is_set():
        for reader in (read_pointer, capture_pointer):
            try:
                observed = reader(root)
            except OSError:
                continue
            seen["absent" if observed is None else "present"] += 1


def test_a_profile_switch_is_not_refused_by_a_peer_reading_the_pointer(tmp_path: Path) -> None:
    """DISCRIMINATING: the refusal a switch or logout hit under a live reader.

    Any escaping ``OSError`` fails the test by propagating out of the loop.
    """
    payload = BucketPointer(bucket_id="0" * 32, schema_version=1).to_toml().encode("utf-8")
    stop = threading.Event()
    seen = {"present": 0, "absent": 0}
    reader = threading.Thread(target=_read_until, args=(tmp_path, stop, seen))
    reader.start()
    try:
        for _ in range(_WRITE_CYCLES):
            restore_pointer(tmp_path, payload)
            clear_pointer(tmp_path)
    finally:
        stop.set()
        reader.join(30)

    assert seen["present"] > 0, "the reader never observed a written pointer; the race did not overlap"
    assert seen["absent"] > 0, "the reader never observed a cleared pointer; the race did not overlap"


def test_a_clear_still_reports_a_refusal_it_cannot_wait_out(tmp_path: Path) -> None:
    """ANTI-TAUTOLOGY: waiting out contention must not swallow every refusal.

    A retry that absorbed the error class outright would pass the race above
    while reporting an unremovable pointer as a successful clear -- a logout
    that silently leaves the profile selected. A directory at the pointer path
    cannot be unlinked at all, so the refusal has to survive the budget.
    """
    (tmp_path / "active-profile").mkdir()

    with pytest.raises(OSError):
        clear_pointer(tmp_path)
