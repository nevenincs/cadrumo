"""A participation index is bound to the transaction key it is filed under.

``TransactionParticipationIndexRepository`` derives its secure-object key from a
transaction id, so the key and the payload's own ``transaction_id`` are two
encodings of one fact. ``load`` validated envelope metadata only and returned
the decrypted index unchecked, so an index belonging to transaction B read
through A's key attributed B's finalized-revision participations to A.

That misattribution is load-bearing: the participation index is what the ledger
deletion guard and the operator cross-reference read to answer "which finalized
revisions used this transaction?".

Real behaviour throughout: a real isolated bucket runtime, the real encrypted
SQL backend, the real repository. The foreign row is planted through the
repository's own secure-object writer, so it is genuinely valid at every layer
beneath the identity check. Nothing is mocked.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from .....core.period import Period
from .....domain.modelos.codes import ModeloCode
from .....domain.modelos.participation_index import (
    TransactionRevisionParticipation,
    TransactionRevisionParticipationIndex,
)
from ...storage.envelope.contract import Envelope
from ...storage.errors import SecureObjectRowIdentityError
from ...storage.secure_object_namespaces import TRANSACTION_PARTICIPATION_INDEX_NAMESPACE
from ...storage.sql.secure_objects import SecureObjectRepository
from ...tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ..participation_index import TransactionParticipationIndexRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "93939393-9393-4393-8393-939393939393"
_NOW = datetime(2026, 5, 20, 9, 0, tzinfo=UTC)
_PERIOD = Period.from_year_and_code(2024, "2T")


def _hex(seed: str) -> str:
    """Return a stable 64-char hex blob for typed-id fixture values."""
    return (seed * 64)[:64]


_TX_A = _hex("a")
_TX_B = _hex("b")

_runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID)


def _index(transaction_id: str, *, revision_seed: str) -> TransactionRevisionParticipationIndex:
    return TransactionRevisionParticipationIndex(
        transaction_id=transaction_id,
        participations=(
            TransactionRevisionParticipation(
                calculation_revision_id=_hex(revision_seed),
                work_unit_id=_hex("c"),
                modelo=ModeloCode("303"),
                filing_year=2024,
                period=_PERIOD,
                revision_state="presentado",
                filing_record_id=_hex("d"),
                justificante_reference="2024-303-2T-JUST-0001",
            ),
        ),
    )


def _plant_under_foreign_key(index: TransactionRevisionParticipationIndex, *, row_key: str) -> None:
    """Write ``index``'s valid envelope under a DIFFERENT transaction's row key."""
    envelope = Envelope[TransactionRevisionParticipationIndex](
        schema_version=TRANSACTION_PARTICIPATION_INDEX_NAMESPACE.schema_version,
        written_at=_NOW,
        classification=TRANSACTION_PARTICIPATION_INDEX_NAMESPACE.sensitivity,
        payload=index,
    )
    SecureObjectRepository().save(
        namespace=TRANSACTION_PARTICIPATION_INDEX_NAMESPACE.namespace,
        object_key=row_key,
        classification=TRANSACTION_PARTICIPATION_INDEX_NAMESPACE.sensitivity,
        schema_version=TRANSACTION_PARTICIPATION_INDEX_NAMESPACE.schema_version,
        written_at=envelope.written_at,
        payload=envelope.model_dump_json().encode("utf-8"),
    )


def test_index_round_trips_under_its_own_transaction_key() -> None:
    """POSITIVE CONTROL: an honestly-filed index still loads unchanged.

    Without this, the refusal below is equally satisfied by a repository that
    refuses every row -- which would break the deletion guard that reads this
    index, in the fail-open direction if a caller swallowed the error.
    """
    repo = TransactionParticipationIndexRepository()
    index = _index(_TX_A, revision_seed="e")
    repo.save(index)

    assert TransactionParticipationIndexRepository().load(_TX_A) == index


def test_absent_index_still_reads_as_an_empty_index() -> None:
    """An unwritten transaction reads empty, not refused: absence is not corruption."""
    loaded = TransactionParticipationIndexRepository().load(_TX_A)

    assert loaded.transaction_id == _TX_A
    assert loaded.participations == ()


def test_load_refuses_an_index_belonging_to_another_transaction() -> None:
    """``load(A)`` must not return the index whose own transaction_id is B.

    DISCRIMINATING: before the fix this returned B's index with
    ``transaction_id == B`` while both keys existed, so B's finalized-revision
    participations were reported as A's.
    """
    repo = TransactionParticipationIndexRepository()
    repo.save(_index(_TX_A, revision_seed="e"))
    _plant_under_foreign_key(_index(_TX_B, revision_seed="f"), row_key=_TX_A)

    with pytest.raises(SecureObjectRowIdentityError) as excinfo:
        repo.load(_TX_A)

    assert excinfo.value.expected_identifier == _TX_B
    assert excinfo.value.namespace == TRANSACTION_PARTICIPATION_INDEX_NAMESPACE.namespace
