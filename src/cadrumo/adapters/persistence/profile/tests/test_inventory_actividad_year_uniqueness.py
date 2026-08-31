"""One activity and year, one inventory ledger -- on every write path.

``InventoryLedgerRepository.create`` and the application service refused a
second ledger for the same ``(actividad_id, year)`` pair, but the public
``save`` / ``save_inventory`` path accepted any ``InventoryLedgerDocument`` and
wrote it without validating. A replacement document could therefore persist two
ledgers for one pair while creation and every later lookup still assumed one
canonical activity/year ledger.

The invariant now lives on the document, so it holds for creation, for bulk
replacement, and at the read boundary alike.

Real behaviour throughout: a real isolated bucket runtime and the real
encrypted secure-object backend. Nothing is mocked.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from .....domain.contribuyente.inventory.records import (
    InventoryLedger,
    InventoryLedgerDocument,
    InventoryLedgerError,
    ValuationMethod,
)
from ...tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ..inventory import InventoryLedgerRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "51515151-5151-4151-8151-515151515151"
_ACTIVIDAD = "retail"
_YEAR = 2025

_runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID)


def _ledger(*, actividad_id: str = _ACTIVIDAD, year: int = _YEAR, opening: str) -> InventoryLedger:
    return InventoryLedger(
        actividad_id=actividad_id,
        year=year,
        valuation_method=ValuationMethod.FIFO,
        opening_stock=Decimal(opening),
        closing_authority_record=None,
    )


def test_duplicate_actividad_year_is_refused_by_the_document() -> None:
    """The invariant is on the document, so no write path can bypass it.

    DISCRIMINATING: this construction used to succeed, and it is the exact
    value ``save`` received. The two ledgers differ in opening stock, so they
    are genuinely distinct rows competing for one natural key rather than an
    accidental repeat of the same object.
    """
    with pytest.raises(ValidationError) as excinfo:
        InventoryLedgerDocument(
            ledgers=(
                _ledger(opening="150.00"),
                _ledger(opening="900.00"),
            ),
        )

    # Names the offending pair, so the refusal is attributable to the duplicate
    # rather than to any other validation failure on the document.
    assert f"{_ACTIVIDAD}/{_YEAR}" in str(excinfo.value)


def test_bulk_save_cannot_persist_two_ledgers_for_one_activity_year() -> None:
    """The bulk path now agrees with ``create``.

    Before, ``repo.save(...)`` accepted the duplicate document and a reload
    returned both rows, including the duplicate key pair.
    """
    repo = InventoryLedgerRepository()

    with pytest.raises(ValidationError):
        repo.save(
            InventoryLedgerDocument(
                ledgers=(
                    _ledger(opening="150.00"),
                    _ledger(opening="900.00"),
                ),
            ),
        )

    assert InventoryLedgerRepository().load().ledgers == ()


def test_create_still_refuses_a_second_ledger_for_the_same_pair() -> None:
    """``create`` keeps its own operator-facing typed refusal.

    The document invariant is the structural backstop; ``create`` stays the
    layer that names the offending pair, so tightening the document did not
    silently downgrade that diagnostic.
    """
    repo = InventoryLedgerRepository()
    repo.create(_ledger(opening="150.00"))

    with pytest.raises(InventoryLedgerError) as excinfo:
        repo.create(_ledger(opening="900.00"))

    # The typed refusal carries the offending pair as structured context, which
    # is what an operator surface renders; asserted on the context rather than
    # on the message prose.
    context = excinfo.value.context
    assert context is not None
    assert context["actividad_id"] == _ACTIVIDAD
    assert context["year"] == _YEAR


def test_distinct_pairs_still_round_trip_through_bulk_save() -> None:
    """POSITIVE CONTROL: legitimate multi-ledger documents still save and load.

    Covers both axes of the composite key -- a second activity in the same
    year, and the same activity in a second year -- so the refusals above
    cannot be satisfied by a document that rejects every multi-row save.
    """
    repo = InventoryLedgerRepository()
    document = InventoryLedgerDocument(
        ledgers=(
            _ledger(opening="150.00"),
            _ledger(actividad_id="wholesale", opening="250.00"),
            _ledger(year=_YEAR + 1, opening="350.00"),
        ),
    )
    repo.save(document)

    loaded = InventoryLedgerRepository().load()
    assert [(ledger.actividad_id, ledger.year) for ledger in loaded.ledgers] == [
        (_ACTIVIDAD, _YEAR),
        ("wholesale", _YEAR),
        (_ACTIVIDAD, _YEAR + 1),
    ]
    assert loaded == document
