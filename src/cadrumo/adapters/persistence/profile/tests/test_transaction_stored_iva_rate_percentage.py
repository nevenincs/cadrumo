"""A stored row whose IVA rate was kept as a percentage stays readable.

The write boundary refuses an IVA rate above one. A profile written before that
refusal can still hold such a row, and one bad row must not make the whole
ledger unreadable. These tests run the real encrypted store with the stored
bytes edited below the model validation: every read path loads the row as
stored, the full re-validation and every write still refuse it, and a patch
that states a fraction replaces it.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from .....domain.calculations.registry.authority import bundled_indexed_authority
from .....domain.transactions.models import Transaction
from ...storage.envelope.contract import Envelope
from ..transactions import TransactionCatalogueRepository
from .test_transaction_authenticated_reads import (
    _BUCKET_ID,
    _mutate_payload,
    _rewrite_row,
    _seeded,
    _stored_payload,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_PERCENTAGE = "21"


@pytest.fixture(autouse=True)
def _authority_operation() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def test_a_stored_row_with_a_percentage_rate_loads_on_every_read_path(tmp_path: Path) -> None:
    with _seeded(tmp_path, count=24) as (objects, saved):
        target = next(row for row in saved.values() if row.iva_rate is not None)
        _rewrite_row(objects, _BUCKET_ID, target.transaction_id, _mutate_payload("iva_rate", _PERCENTAGE))

        loaded = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects).load()
        targeted = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects).load_by_ids(
            [target.transaction_id],
        )

        assert loaded.transactions[target.transaction_id].iva_rate == Decimal(_PERCENTAGE)
        assert targeted.transactions[target.transaction_id].iva_rate == Decimal(_PERCENTAGE)
        assert len(loaded.transactions) == len(saved.transactions)
        untouched = next(row for row in saved.values() if row.transaction_id != target.transaction_id)
        assert loaded.transactions[untouched.transaction_id] == untouched


def test_the_rate_is_still_refused_off_the_stored_row_read_and_replaced_by_a_fraction(tmp_path: Path) -> None:
    with _seeded(tmp_path, count=24) as (objects, saved):
        target = next(row for row in saved.values() if row.iva_rate is not None)
        _rewrite_row(objects, _BUCKET_ID, target.transaction_id, _mutate_payload("iva_rate", _PERCENTAGE))
        stored = _stored_payload(objects, _BUCKET_ID, target.transaction_id)
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
        opened = repository.load().transactions[target.transaction_id]

        with pytest.raises(ValidationError):
            Transaction.model_validate(opened.model_dump())
        with pytest.raises(ValidationError):
            Envelope[Transaction].model_validate_json(stored)

        corrected = opened.model_copy(update={"iva_rate": Decimal("0.21")})
        repository.replace_if_current_with_secure_object_writes(opened, corrected, ())
        reread = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects).load()
        assert reread.transactions[target.transaction_id].iva_rate == Decimal("0.21")
