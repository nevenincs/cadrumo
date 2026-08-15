"""The capsule inventory separates custody content from database representation.

A capsule directory is a bucket directory, so the profile's own encrypted
SQLite database sits inside the tree a local deletion inventories. That
database is opened in ``journal_mode=WAL``: an open connection parks committed
pages in a ``-wal`` sidecar with a ``-shm`` index beside it, and closing the
connection checkpoints those pages back into the main file and removes both
sidecars.

None of that is a change to what the capsule HOLDS, but all of it changes bytes
-- including the bytes of the main database file, which is the half that is
easy to miss. So the inventory digest covers the byte-stable custody records
and names the three database paths as representation, while the observation
itself still reports every file it saw.

These cases exercise the classification directly against real files on a real
filesystem, with no application layer above them. The proof that a REAL session
close produces exactly this shape -- and that a logged-in profile is therefore
deletable -- lives with the custody transaction, in
``application/user_profile/tests/test_delete_while_logged_in.py``; splitting
them keeps this file at the boundary that owns the rule.
"""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import pytest

from .._errors import ProfileCustodyRecordError
from .._inventory import (
    DATABASE_PRESENCE_ONLY_RELATIVE_PATHS,
    DATABASE_SIDECAR_RELATIVE_PATHS,
    inventory_profile_custody_capsule,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PROFILE_ID = UUID("6f1c2b84-9d3a-4e57-8f60-2c7b1a54e903")

_COMMIT_BYTES = b'{"schema_version": 1, "profile_id": "capsule commit stand-in"}'
_ENVELOPE_BYTES = b'{"schema_version": 1, "kdf": "password envelope stand-in"}'
_DATABASE_BYTES = b"main database pages" * 64
_WAL_BYTES = b"write-ahead pages awaiting checkpoint" * 128
_SHM_BYTES = b"shared-memory index" * 32


def _write(capsule: Path, relative: str, payload: bytes) -> None:
    target = capsule / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)


def _capsule_with_an_open_connection(tmp_path: Path) -> Path:
    """Lay down a capsule in the shape an OPEN database connection leaves it.

    Two byte-stable custody records, the main database file, and both
    write-ahead sidecars.
    """
    capsule = tmp_path / str(_PROFILE_ID)
    _write(capsule, "profile.commit.v1.json", _COMMIT_BYTES)
    _write(capsule, "custody/envelope.v1.json", _ENVELOPE_BYTES)
    for relative, payload in (
        ("db/cadrumo.db", _DATABASE_BYTES),
        ("db/cadrumo.db-wal", _WAL_BYTES),
        ("db/cadrumo.db-shm", _SHM_BYTES),
    ):
        _write(capsule, relative, payload)
    return capsule


def _checkpoint(capsule: Path) -> None:
    """Apply what closing the connection does: fold the sidecars into the file.

    The main file GROWS -- that is the whole difficulty. A rule that excluded
    only ``-wal`` and ``-shm`` would still see this file change and would still
    refuse the deletion.
    """
    (capsule / "db/cadrumo.db-wal").unlink()
    (capsule / "db/cadrumo.db-shm").unlink()
    (capsule / "db/cadrumo.db").write_bytes(_DATABASE_BYTES + _WAL_BYTES)


def _relative_paths(capsule: Path) -> set[str]:
    inventory = inventory_profile_custody_capsule(_PROFILE_ID, capsule)
    return {entry.relative_path for entry in inventory.entries}


def test_the_database_paths_are_named_from_the_storage_taxonomy() -> None:
    """The two collections are derived, not a second hand-typed literal.

    Anchoring them to the taxonomy member the engine itself resolves is what
    stops a rename of the database directory or filename from silently
    emptying them and reinstating the defect.
    """
    assert frozenset({"db/cadrumo.db-wal", "db/cadrumo.db-shm"}) == DATABASE_SIDECAR_RELATIVE_PATHS
    assert frozenset({"db/cadrumo.db"}) == DATABASE_PRESENCE_ONLY_RELATIVE_PATHS


def test_a_checkpoint_leaves_the_inventory_digest_unmoved(tmp_path: Path) -> None:
    """The representation change the deletion causes itself must not be a conflict.

    A local deletion inventories the capsule at preflight and re-verifies it
    against the same capsule at execution, and its own first destructive act
    closes this connection. If the checkpoint moved the digest, the deletion
    would invalidate its own preflight and a profile the operator is signed
    into could never be deleted.
    """
    capsule = _capsule_with_an_open_connection(tmp_path)
    while_open = inventory_profile_custody_capsule(_PROFILE_ID, capsule)

    _checkpoint(capsule)
    after_close = inventory_profile_custody_capsule(_PROFILE_ID, capsule)

    assert after_close.digest == while_open.digest


def test_the_observation_still_reports_the_sidecars_the_digest_ignores(tmp_path: Path) -> None:
    """Narrowing the digest must not blind the walk, or the case above proves nothing.

    An inventory that simply stopped SEEING the database files would satisfy
    the digest assertion while destroying the record of what the capsule
    actually contained. The entries are the honest observation and still move.
    """
    capsule = _capsule_with_an_open_connection(tmp_path)
    while_open = inventory_profile_custody_capsule(_PROFILE_ID, capsule)
    assert {entry.relative_path for entry in while_open.entries} >= DATABASE_SIDECAR_RELATIVE_PATHS

    _checkpoint(capsule)
    after_close = inventory_profile_custody_capsule(_PROFILE_ID, capsule)

    assert {entry.relative_path for entry in after_close.entries} == {
        "profile.commit.v1.json",
        "custody/envelope.v1.json",
        "db/cadrumo.db",
    }
    assert after_close.total_bytes != while_open.total_bytes


def test_a_changed_custody_record_still_moves_the_digest(tmp_path: Path) -> None:
    """The safety property the marker exists for survives the narrowing.

    Custody records are write-once canonical JSON. One byte different in the
    password envelope is a different capsule, and the deletion must refuse
    rather than destroy something the operator did not confirm.
    """
    capsule = _capsule_with_an_open_connection(tmp_path)
    before = inventory_profile_custody_capsule(_PROFILE_ID, capsule)

    _write(capsule, "custody/envelope.v1.json", _ENVELOPE_BYTES.replace(b'"kdf"', b'"KDF"'))

    assert inventory_profile_custody_capsule(_PROFILE_ID, capsule).digest != before.digest


def test_a_vanished_custody_record_still_moves_the_digest(tmp_path: Path) -> None:
    """Removal is the other half of "changed", and the sidecars made it subtle.

    Two of the excluded paths vanish legitimately. Nothing else may vanish
    quietly.
    """
    capsule = _capsule_with_an_open_connection(tmp_path)
    before = inventory_profile_custody_capsule(_PROFILE_ID, capsule)

    (capsule / "custody/envelope.v1.json").unlink()

    assert inventory_profile_custody_capsule(_PROFILE_ID, capsule).digest != before.digest


def test_a_foreign_file_under_the_database_directory_still_moves_the_digest(tmp_path: Path) -> None:
    """The exclusion is three exact paths, never a directory or a suffix rule.

    Excluding everything under ``db/`` -- or everything matching ``*-wal`` --
    would let a planted file ride into a confirmed deletion unnoticed.
    """
    capsule = _capsule_with_an_open_connection(tmp_path)
    before = inventory_profile_custody_capsule(_PROFILE_ID, capsule)

    _write(capsule, "db/planted.bin", b"not one of the three named members")

    assert inventory_profile_custody_capsule(_PROFILE_ID, capsule).digest != before.digest


def test_a_vanished_database_still_moves_the_digest(tmp_path: Path) -> None:
    """The database's bytes are out of the digest; its PATH is not.

    This is the half of the concession that is still a real guard, and it is
    the reason the database is carried as a presence member rather than
    dropped the way the sidecars are. A deletion whose target database
    disappeared between preflight and execution is being asked to destroy
    something other than what was confirmed, and it refuses.
    """
    capsule = _capsule_with_an_open_connection(tmp_path)
    _checkpoint(capsule)
    settled = inventory_profile_custody_capsule(_PROFILE_ID, capsule)

    (capsule / "db/cadrumo.db").unlink()

    assert inventory_profile_custody_capsule(_PROFILE_ID, capsule).digest != settled.digest


def test_database_content_deliberately_does_not_move_the_digest(tmp_path: Path) -> None:
    """Pin the limitation so it is executable, not merely documented.

    Rows written into the capsule database between preflight and execution do
    NOT move the digest, and nothing else catches them -- the deletion is the
    only reader of this inventory in that window. Asserting the gap keeps it
    honest in both directions: it cannot be quietly forgotten, and anyone who
    later believes they have re-covered database content will find this case
    red and be forced to read why it was given up.

    The write here is byte-level rather than through the engine on purpose:
    what is being pinned is the digest's blindness to the file's bytes, and no
    key material is needed to demonstrate that.
    """
    capsule = _capsule_with_an_open_connection(tmp_path)
    _checkpoint(capsule)
    settled = inventory_profile_custody_capsule(_PROFILE_ID, capsule)

    (capsule / "db/cadrumo.db").write_bytes(_DATABASE_BYTES + b"pages a later write appended")

    changed = inventory_profile_custody_capsule(_PROFILE_ID, capsule)
    assert changed.digest == settled.digest
    assert changed.entries != settled.entries, (
        "the walk must still SEE the change, or the limitation is a blind spot rather than a stated one"
    )


def test_a_capsule_of_database_files_alone_is_refused(tmp_path: Path) -> None:
    """A digest over nothing is the degenerate constant, and it must not exist.

    Every real capsule carries a commit record; a tree that carries only the
    excluded members is not one, and returning a well-formed digest for it
    would let two unrelated trees compare equal.
    """
    capsule = tmp_path / str(_PROFILE_ID)
    _write(capsule, "db/cadrumo.db", _DATABASE_BYTES)
    _write(capsule, "db/cadrumo.db-wal", _WAL_BYTES)

    with pytest.raises(ProfileCustodyRecordError, match="no durable custody record"):
        inventory_profile_custody_capsule(_PROFILE_ID, capsule)
