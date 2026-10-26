"""Loading stored transactions outside an authority operation is a scope refusal, not drift.

A persisted row validates against registry vocabulary. Decoding it with no
governed-fact scope fails for that reason alone, and reporting the failure as
schema drift sent the operator to repair data that is perfectly current. These
cases persist a real row inside an operation and read it back outside one;
they live above the profile test package, which scopes every test to a lease.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....core.errors.hierarchy import InternalInvariantError
from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.errors import StoredTransactionDriftError
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ..profile.transactions import TransactionCatalogueRepository
from ..storage.tests.secure_sql import isolated_runtime_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "44444444-4444-4444-8444-444444444444"


def _transaction() -> Transaction:
    raw = RawTransaction(
        provider_transaction_id="scope-row-1",
        booked_date=date(2024, 4, 10),
        value_date=date(2024, 4, 10),
        amount=Decimal("50.00"),
        currency="EUR",
        counterparty="Supplier SL",
        description="Office supplies",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2024, 4, 14, 9, 30, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": "Office supplies"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "group_label": None,
            # A registry-vocabulary field: its decode resolves through the
            # governed income-concept catalogue, so it needs a scope.
            "concepto_ingreso": "subvencion_corriente",
        }
    )


def _persist_one_row(bucket_id: str) -> None:
    with bundled_indexed_authority().operation():
        catalogue = TransactionCatalogue.from_transactions([_transaction()])
        TransactionCatalogueRepository(bucket_id=bucket_id).save(catalogue)


def test_a_load_outside_an_operation_refuses_for_the_missing_scope(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _persist_one_row(profile.bucket_id)

        with pytest.raises(
            InternalInvariantError, match="requires an explicit authority operation or scope"
        ) as refusal:
            TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()

    assert not isinstance(refusal.value, StoredTransactionDriftError)
    assert isinstance(refusal.value.__cause__, ValidationError)


def test_the_same_row_loads_inside_an_operation(tmp_path: Path) -> None:
    """CONTROL: the refusal above is the missing scope, not the stored row."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _persist_one_row(profile.bucket_id)

        with bundled_indexed_authority().operation():
            loaded = TransactionCatalogueRepository(bucket_id=profile.bucket_id).load()

    assert [transaction.raw.description for transaction in loaded.transactions.values()] == ["Office supplies"]
