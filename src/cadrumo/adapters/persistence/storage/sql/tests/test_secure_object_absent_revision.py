"""A secure-object row carrying no revision metadata is refused, not tolerated.

The lineage gate and the record contract used to disagree about this row. The
gate reported ``revision_id is None`` CONSISTENT -- documented as an older,
readable shape -- and then the codec built
:class:`~.._secure_object_records.SecureObjectRecord`, whose ``revision_id`` is
typed as an exactly-64-character digest, out of ``str(None)``. So the shape the
gate admitted could not survive the record it was admitted for: the single-row
surface surfaced a raw Pydantic ``ValidationError`` from inside the codec, and
the batch surface attributed that validation text as its unreadable reason.

Every write stamps revision metadata inside the same transaction that inserts
the ciphertext, so no such row was ever written by this application; under the
pre-release compatibility regime it is corruption now, and the one authority on
the question refuses it.

Real behaviour throughout: real SQLite, a real ``EphemeralMasterKeyProvider``,
real AEAD, real stored-metadata erasure. Nothing is mocked.
"""

from __future__ import annotations

import pytest

from ......tests.master_key import EphemeralMasterKeyProvider
from ._secure_objects_support import (
    UTC,
    Path,
    SecureObjectRecord,
    SecureObjectRepository,
    SecureObjectUnreadable,
    SecureObjectUnreadableError,
    SensitivityClass,
    _repo_at,
    datetime,
    sqlite3,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_NAMESPACE = "cadrumo.absent.revision"
_KEY = "absent-revision-subject"
_PAYLOAD = b"absent-revision-payload"
_LINEAGE_REASON = "revision lineage self-consistency check failed"

#: Every column ``write_revision_metadata`` stamps that the lineage gate reads.
_REVISION_COLUMNS = (
    "revision_id",
    "previous_revision_id",
    "payload_hash",
    "ciphertext_hash",
    "previous_payload_hash",
)


def _seed(db_path: Path) -> None:
    """Write one genuine row through the public repository."""
    with _repo_at(db_path) as repo:
        repo.save(
            namespace=_NAMESPACE,
            object_key=_KEY,
            classification=SensitivityClass.FINANCIAL,
            schema_version=1,
            written_at=datetime.now(UTC),
            payload=_PAYLOAD,
        )


def _erase_revision_metadata(db_path: Path) -> None:
    """Null every revision column, leaving valid classification and ciphertext.

    The ciphertext and its AEAD binding are untouched, so the row still
    DECRYPTS: the refusal under test is attributable to the absent lineage
    metadata alone and to nothing else about the row.
    """
    assignments = ", ".join(f"{column} = NULL" for column in _REVISION_COLUMNS)
    with sqlite3.connect(db_path) as con:
        con.execute(
            f"UPDATE secure_objects SET {assignments} WHERE namespace = ?",  # noqa: S608 - column names are module constants
            (_NAMESPACE,),
        )


def _load(repo: SecureObjectRepository) -> SecureObjectRecord | None:
    return repo.load(
        namespace=_NAMESPACE,
        object_key=_KEY,
        expected_class=SensitivityClass.FINANCIAL,
        max_supported_version=1,
    )


def _iterate(repo: SecureObjectRepository) -> list[object]:
    return list(
        repo.iter_records_with_failures(
            namespace=_NAMESPACE,
            expected_class=SensitivityClass.FINANCIAL,
            max_supported_version=1,
        ),
    )


def test_stamped_row_round_trips_through_both_read_surfaces(tmp_path: Path) -> None:
    """POSITIVE CONTROL: an ordinary row is readable on both surfaces.

    Without this, every refusal below is satisfied by a repository that refuses
    everything -- including a fixture too broken to have proved anything. This
    pins that the metadata erasure is the only difference between a readable
    row and the refused ones, and that the gate did not over-refuse.
    """
    db_path = tmp_path / "stamped.db"
    with EphemeralMasterKeyProvider():
        _seed(db_path)
        with _repo_at(db_path) as repo:
            record = _load(repo)
            assert record is not None
            assert record.payload == _PAYLOAD
            assert len(record.revision_id) == 64

            items = _iterate(repo)
            assert len(items) == 1
            assert isinstance(items[0], SecureObjectRecord)
            assert items[0].revision_id == record.revision_id


def test_row_without_revision_metadata_is_refused_on_single_load(tmp_path: Path) -> None:
    """The typed storage refusal, not a validation error escaping the codec.

    DISCRIMINATING on the fix: before it, the gate admitted the row and the
    failure arrived as ``ValidationError`` raised while constructing the record
    -- a Pydantic error, not a storage one, from past the point the read path
    had already decided the row was fine. ``SecureObjectUnreadableError`` is a
    ``DecryptionError`` subclass, so asserting it also excludes that.
    """
    db_path = tmp_path / "absent-single.db"
    with EphemeralMasterKeyProvider():
        _seed(db_path)
        _erase_revision_metadata(db_path)
        with _repo_at(db_path) as repo, pytest.raises(SecureObjectUnreadableError):
            _load(repo)


def test_row_without_revision_metadata_is_attributed_during_iteration(tmp_path: Path) -> None:
    """The batch surface attributes the row to the lineage gate.

    The verdict alone is order-invariant and would pass under the old
    behaviour too -- iteration reported the row unreadable either way. What
    changed is the ATTRIBUTION: the reason is now the gate's own structural
    diagnostic rather than the text of a Pydantic validation failure, so the
    assertion is on the reason.
    """
    db_path = tmp_path / "absent-batch.db"
    with EphemeralMasterKeyProvider():
        _seed(db_path)
        _erase_revision_metadata(db_path)
        with _repo_at(db_path) as repo:
            items = _iterate(repo)

    assert len(items) == 1
    unreadable = items[0]
    assert isinstance(unreadable, SecureObjectUnreadable)
    assert unreadable.reason == _LINEAGE_REASON


def test_lineage_gate_refuses_an_absent_revision_id_directly(tmp_path: Path) -> None:
    """The single authority answers ``False`` for the absent shape.

    Asserted against the gate itself, not only through the repository, because
    the gate is what both read surfaces consult: a future caller that reaches
    it directly must get the same answer. ``tmp_path`` is unused by design --
    this exercises the pure metadata predicate with no stored row at all.
    """
    from ..secure_object_crypto import derive_revision_id, verify_revision_self_consistency

    written_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    object_key = b"\x11" * 32
    payload_hash = "a" * 64
    ciphertext_hash = "b" * 64

    def check(revision_id: str | None) -> bool:
        return verify_revision_self_consistency(
            revision_id,
            namespace=_NAMESPACE,
            object_key=object_key,
            schema_version=1,
            written_at=written_at,
            previous_revision_id=None,
            payload_hash=payload_hash,
            ciphertext_hash=ciphertext_hash,
            previous_payload_hash=None,
        )

    assert check(None) is False

    stamped = derive_revision_id(
        namespace=_NAMESPACE,
        object_key=object_key,
        schema_version=1,
        written_at=written_at,
        payload_hash=payload_hash,
        ciphertext_hash=ciphertext_hash,
        previous_revision_id=None,
        previous_payload_hash=None,
    )
    # Positive control for the predicate: the same lineage WITH its derived id
    # is accepted, so the refusal above is about the absent id and not about a
    # lineage tuple that could never verify.
    assert check(stamped) is True
