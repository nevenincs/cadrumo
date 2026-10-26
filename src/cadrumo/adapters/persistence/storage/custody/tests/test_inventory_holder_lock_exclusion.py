"""The capsule inventory digest excludes the bucket holder lockfile.

A capsule directory IS a bucket directory, so the lockfile the storage layer
writes to claim the bucket sits inside the tree a local deletion inventories.
Its whole payload is the holding process's id.

That makes it unholdable across the boundary a crash-resume spans. A reset
acquires the lock as its own precondition, fingerprints the capsule while
holding it, and -- if the process dies -- resumes in a DIFFERENT process, which
writes a different pid. A digest covering those bytes can never reproduce
itself across the one boundary it exists to span, so every resume paused as a
changed target and the roll-forward mandate was unreachable.

The exclusion narrows what the digest CLAIMS; it does not substitute a value
the code did not observe. Everything custody-bearing stays covered, which is
what the cases below pin: the walk still reports the lockfile, and a file
planted anywhere else -- including one named ``.lock`` deeper in the tree --
still moves the digest.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from uuid import UUID

import pytest

from .._inventory import (
    HOLDER_LOCK_RELATIVE_PATHS,
    inventory_profile_custody_capsule,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PROFILE_ID = UUID("2b7d4c19-6a85-4f30-9c12-8e5b0d3a7f64")

_COMMIT_BYTES = b'{"schema_version": 1, "profile_id": "capsule commit stand-in"}'
_ENVELOPE_BYTES = b'{"schema_version": 1, "kdf": "password envelope stand-in"}'


def _write(capsule: Path, relative: str, payload: bytes) -> None:
    target = capsule / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)


def _capsule(tmp_path: Path) -> Path:
    capsule = tmp_path / str(_PROFILE_ID)
    _write(capsule, "profile.commit.v1.json", _COMMIT_BYTES)
    _write(capsule, "custody/envelope.v1.json", _ENVELOPE_BYTES)
    _write(capsule, "db/cadrumo.db", b"main database pages" * 8)
    return capsule


def _digest(capsule: Path) -> str:
    return inventory_profile_custody_capsule(_PROFILE_ID, capsule).digest


def test_the_lock_path_is_named_from_the_storage_taxonomy() -> None:
    """The collection is derived, not a second hand-typed literal.

    Anchoring it to the taxonomy member the storage layer itself resolves is
    what stops a rename of the lockfile from silently emptying the set and
    reinstating the defect behind a still-green suite.
    """
    assert frozenset({".lock"}) == HOLDER_LOCK_RELATIVE_PATHS


def test_the_holder_pid_does_not_move_the_digest(tmp_path: Path) -> None:
    """Held by this process, held by a real child, and unheld all agree.

    The child is a REAL second interpreter, because the defect is invisible
    within one process: the same interpreter re-acquiring writes the same pid,
    and only a genuinely different process reproduces what a resume does.
    """
    capsule = _capsule(tmp_path)
    unheld = _digest(capsule)

    (capsule / ".lock").write_bytes(f"{os.getpid()}\n".encode("ascii"))
    held_here = _digest(capsule)

    child = subprocess.run(
        [sys.executable, "-c", "import os, sys; sys.stdout.write(str(os.getpid()))"],
        capture_output=True,
        check=True,
        text=True,
    )
    (capsule / ".lock").write_bytes(f"{child.stdout.strip()}\n".encode("ascii"))
    held_elsewhere = _digest(capsule)

    assert held_here == unheld
    assert held_elsewhere == unheld


def test_the_walk_still_reports_the_lockfile(tmp_path: Path) -> None:
    """Narrowing the digest must not blind the observation.

    ``entries`` is the honest record of what the walk saw. A lockfile absent
    from it would mean the exclusion had removed evidence rather than removed a
    claim.
    """
    capsule = _capsule(tmp_path)
    (capsule / ".lock").write_bytes(b"4321\n")

    inventory = inventory_profile_custody_capsule(_PROFILE_ID, capsule)

    assert ".lock" in {entry.relative_path for entry in inventory.entries}
    assert ".lock" not in {entry.relative_path for entry in inventory.digest_entries}


def test_the_exclusion_is_one_exact_path_and_not_a_name_rule(tmp_path: Path) -> None:
    """A file called ``.lock`` deeper in the tree is still foreign matter.

    This is the anti-blindness proof. If the rule matched on filename rather
    than on the one capsule-relative path the taxonomy names, an intruder could
    hide bytes anywhere by choosing that name.
    """
    capsule = _capsule(tmp_path)
    before = _digest(capsule)

    _write(capsule, "custody/.lock", b"planted where the rule must not reach")

    assert _digest(capsule) != before


def test_a_custody_record_change_still_moves_the_digest(tmp_path: Path) -> None:
    """The detector still bites on the members it does claim.

    Without this the exclusion could not be told apart from a weakening: a
    digest that stopped moving for custody records would pass every case above.
    """
    capsule = _capsule(tmp_path)
    (capsule / ".lock").write_bytes(b"999\n")
    before = _digest(capsule)

    (capsule / "custody/envelope.v1.json").write_bytes(_ENVELOPE_BYTES + b" tampered")

    assert _digest(capsule) != before
