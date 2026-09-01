"""The revision-lineage gate covers the derivation tuple, and only that tuple.

``write_revision_metadata`` stamps ten columns; ``derive_revision_id`` mixes
eight inputs, four of which are among the stamped ten. So five stamped columns
sit outside the digest and a row whose stored value for any of them is edited
recomputes the same ``revision_id`` and is admitted by the gate.

That asymmetry is pinned here, in both directions, because it is easy to read
past. The covered half is asserted so a derivation input cannot silently stop
being covered; the uncovered half is asserted so the gap cannot silently widen
by a new stamped column, and so a future change that closes it fails here and
forces the prose to move with it.

The uncovered set is recorded, not endorsed. ``revision_ancestor_ids`` is the
consequential member: it is the ancestry chain, of which only the head link
``previous_revision_id`` is mixed, so the parent edge is pinned and the chain
behind it is not. Closing that restamps every stored ``revision_id``, which is
a persisted-format decision rather than a local fix.

Reaching a stamped column requires direct database write access, and the AEAD
still authenticates the payload bytes throughout: what is at stake is the
integrity of revision provenance and audit attribution, not payload
confidentiality.

Real behaviour throughout: real SQLite, a real ``EphemeralMasterKeyProvider``,
real AEAD, real raw-SQL tampering of stored columns. Nothing is mocked.
"""

from __future__ import annotations

import inspect
from typing import TypedDict

import pytest

from ......tests.master_key import EphemeralMasterKeyProvider
from ..secure_object_crypto import derive_revision_id
from ._secure_objects_support import (
    UTC,
    Path,
    SecureObjectUnreadableError,
    SensitivityClass,
    _repo_at,
    datetime,
    sqlite3,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NAMESPACE = "cadrumo.lineage.coverage"
_KEY = "lineage-coverage-subject"

#: The exact inputs mixed into the content address, in declaration order.
_DERIVATION_INPUTS = (
    "namespace",
    "object_key",
    "schema_version",
    "written_at",
    "payload_hash",
    "ciphertext_hash",
    "previous_revision_id",
    "previous_payload_hash",
)

#: Stamped columns that ARE derivation inputs: a tamper is detected.
_COVERED_TAMPERS = {
    "previous_revision_id": "c" * 64,
    "previous_payload_hash": "e" * 64,
    "payload_hash": "f" * 64,
    "ciphertext_hash": "0" * 64,
}

#: Stamped columns that are NOT derivation inputs: a tamper is admitted.
_UNCOVERED_TAMPERS = {
    "revision_ancestor_ids": '["' + "d" * 64 + '"]',
    "revision_written_at": "1999-01-01 00:00:00.000000",
    "write_provenance": "forged-provenance",
    "source_event_id": "forged-event-id",
    "conflict_policy": "forged-policy",
}


def _seed(db_path: Path) -> None:
    """Write the subject TWICE through the public repository.

    The second write is what gives the row a real ``previous_revision_id`` and
    a non-empty ``revision_ancestor_ids``; tampering an ancestry chain that is
    still ``[]`` would not exercise the case the chain exists for.
    """
    with _repo_at(db_path) as repo:
        for index in (1, 2):
            repo.save(
                namespace=_NAMESPACE,
                object_key=_KEY,
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=datetime.now(UTC),
                payload=f"lineage-coverage-payload-{index}".encode(),
            )


def _tamper(db_path: Path, column: str, value: str) -> None:
    """Overwrite ONE stored column, asserting the write actually changed it.

    Without the change assertion a tamper that silently no-ops would leave the
    row genuine, and every "admitted" verdict below would be satisfied by an
    untouched row rather than by a forged one.
    """
    with sqlite3.connect(db_path) as con:
        select = f"SELECT {column} FROM secure_objects WHERE namespace = ?"  # noqa: S608 - column names are module constants
        before = con.execute(select, (_NAMESPACE,)).fetchone()[0]
        con.execute(
            f"UPDATE secure_objects SET {column} = ? WHERE namespace = ?",  # noqa: S608 - column names are module constants
            (value, _NAMESPACE),
        )
        after = con.execute(select, (_NAMESPACE,)).fetchone()[0]
    assert before != after, f"{column}: tamper was a no-op, stored value stayed {before!r}"


def _load(db_path: Path) -> object | None:
    with _repo_at(db_path) as repo:
        return repo.load(
            namespace=_NAMESPACE,
            object_key=_KEY,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=1,
        )


class _RevisionInputs(TypedDict):
    namespace: str
    object_key: bytes
    schema_version: int
    written_at: datetime
    payload_hash: str
    ciphertext_hash: str
    previous_revision_id: str
    previous_payload_hash: str


def _revision_id(*, varied: str | None = None) -> str:
    values: _RevisionInputs = {
        "namespace": _NAMESPACE,
        "object_key": b"\x11" * 32,
        "schema_version": 1,
        "written_at": datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        "payload_hash": "a" * 64,
        "ciphertext_hash": "b" * 64,
        "previous_revision_id": "c" * 64,
        "previous_payload_hash": "d" * 64,
    }
    if varied == "namespace":
        values["namespace"] = _NAMESPACE + ".other"
    elif varied == "object_key":
        values["object_key"] = b"\x22" * 32
    elif varied == "schema_version":
        values["schema_version"] = 2
    elif varied == "written_at":
        values["written_at"] = datetime(2026, 1, 2, 3, 4, 6, tzinfo=UTC)
    elif varied == "payload_hash":
        values["payload_hash"] = "1" * 64
    elif varied == "ciphertext_hash":
        values["ciphertext_hash"] = "2" * 64
    elif varied == "previous_revision_id":
        values["previous_revision_id"] = "3" * 64
    elif varied == "previous_payload_hash":
        values["previous_payload_hash"] = "4" * 64
    return derive_revision_id(**values)


def test_derivation_accepts_exactly_the_documented_inputs() -> None:
    """The signature is the documented input set, no wider and no narrower."""
    assert tuple(inspect.signature(derive_revision_id).parameters) == _DERIVATION_INPUTS


@pytest.mark.parametrize("varied", _DERIVATION_INPUTS)
def test_every_documented_input_actually_changes_the_digest(varied: str) -> None:
    """Each documented input is MIXED, not merely accepted.

    The signature check above cannot see this: a parameter can be taken and
    then left out of the hashed tuple, which reads as covered and is not.
    Varying one input at a time and demanding a different digest measures the
    mixing itself, so an input dropped from the tuple fails here.
    """
    baseline = _revision_id()
    assert _revision_id(varied=varied) != baseline


def test_untampered_row_reads_after_two_writes(tmp_path: Path) -> None:
    """POSITIVE CONTROL: the seeded row is readable and genuinely has ancestry.

    Without this, every "admitted" verdict below is satisfiable by a gate that
    admits everything, and every "refused" verdict by a fixture too broken to
    read at all.
    """
    db_path = tmp_path / "control.db"
    with EphemeralMasterKeyProvider():
        _seed(db_path)
        assert _load(db_path) is not None

        with sqlite3.connect(db_path) as con:
            previous_revision_id, ancestors = con.execute(
                "SELECT previous_revision_id, revision_ancestor_ids FROM secure_objects WHERE namespace = ?",
                (_NAMESPACE,),
            ).fetchone()

    assert previous_revision_id is not None
    assert ancestors is not None
    assert previous_revision_id in ancestors


@pytest.mark.parametrize(("column", "forged"), sorted(_COVERED_TAMPERS.items()))
def test_tampering_a_derivation_input_is_refused(tmp_path: Path, column: str, forged: str) -> None:
    """Each covered column recomputes a different id, so the row is refused."""
    db_path = tmp_path / f"covered-{column}.db"
    with EphemeralMasterKeyProvider():
        _seed(db_path)
        _tamper(db_path, column, forged)
        with pytest.raises(SecureObjectUnreadableError):
            _load(db_path)


@pytest.mark.parametrize(("column", "forged"), sorted(_UNCOVERED_TAMPERS.items()))
def test_tampering_a_stamped_non_input_is_admitted(tmp_path: Path, column: str, forged: str) -> None:
    """Each uncovered column is outside the digest, so the forged row reads.

    This asserts a LIMITATION, and asserting it is the point: the gate's reach
    is now executable rather than only described, so widening the stamped set
    without widening the digest fails here instead of passing unnoticed.
    """
    db_path = tmp_path / f"uncovered-{column}.db"
    with EphemeralMasterKeyProvider():
        _seed(db_path)
        _tamper(db_path, column, forged)
        assert _load(db_path) is not None


def test_forged_ancestry_chain_survives_the_gate(tmp_path: Path) -> None:
    """The forged ancestry is READ BACK, not merely tolerated by the gate.

    Separated from the parametrised limitation above because a passing load
    only says the row was admitted. What makes ancestry the consequential
    member of the uncovered set is that the substituted chain is what a later
    reader of revision provenance receives, while the direct parent link stays
    pinned -- so the row presents a coherent, wrong lineage.
    """
    forged_ancestor = "d" * 64
    db_path = tmp_path / "forged-ancestry.db"
    with EphemeralMasterKeyProvider():
        _seed(db_path)
        with sqlite3.connect(db_path) as con:
            genuine = con.execute(
                "SELECT revision_ancestor_ids FROM secure_objects WHERE namespace = ?",
                (_NAMESPACE,),
            ).fetchone()[0]
        assert forged_ancestor not in genuine

        _tamper(db_path, "revision_ancestor_ids", f'["{forged_ancestor}"]')
        assert _load(db_path) is not None

        with sqlite3.connect(db_path) as con:
            stored, previous_revision_id = con.execute(
                "SELECT revision_ancestor_ids, previous_revision_id FROM secure_objects WHERE namespace = ?",
                (_NAMESPACE,),
            ).fetchone()

    assert forged_ancestor in stored
    assert previous_revision_id not in stored
