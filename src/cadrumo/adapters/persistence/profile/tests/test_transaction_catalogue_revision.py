"""The transaction catalogue revision changes with every stored change and never lies.

A capture that reuses ledger work keys it on this revision, so a revision that
stayed equal across a real change would serve stale data. Every case writes
through the real encrypted store; the revision is read without decrypting rows.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.storage.secure_object_namespaces import TRANSACTION_CATALOGUE_NAMESPACE
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from cadrumo.domain.transactions.repository import transaction_object_key

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "33333333-3333-4333-8333-333333333333"


def _transaction(provider_id: str, *, description: str = "ledger row") -> Transaction:
    booked = date(2026, 4, 5)
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked,
        value_date=booked,
        amount=Decimal("121.00"),
        currency="EUR",
        counterparty="Proveedor",
        description=f"{description} {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.MANUAL,
            ingested_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="manual-ledger",
        ),
        raw_fields={"source_kind": BindingSourceKind.LEDGER_TRANSACTION.value},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "business_pct": None,
            "category_id": None,
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
            "iva_category": None,
            "counterparty_country": None,
            "counterparty_identification_state": None,
            "irpf_category": None,
            "usage_ratio_id": None,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2026, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _catalogue(*transactions: Transaction) -> TransactionCatalogue:
    return TransactionCatalogue.from_transactions(transactions)


@pytest.mark.usefixtures("operation")
def test_the_revision_follows_every_stored_change(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        reader = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        writer = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        first, second = _transaction("row-1"), _transaction("row-2")

        empty = reader.load_revision()
        writer.save(_catalogue(first))
        one_row = reader.load_revision()
        writer.save(_catalogue(first))
        unchanged = reader.load_revision()
        writer.save(_catalogue(first, second))
        added = reader.load_revision()
        edited_first = first.model_copy(update={"group_label": "edited", "modified_at": datetime.now(UTC)})
        writer.save(_catalogue(edited_first, second))
        edited = reader.load_revision()
        writer.save(_catalogue(edited_first))
        deleted = reader.load_revision()

    states = [empty, one_row, added, edited, deleted]
    assert None not in states
    assert len(set(states)) == len(states), "every stored change must move the revision"
    assert unchanged == one_row, "rewriting identical content is not a change"


@pytest.mark.usefixtures("operation")
def test_a_listed_row_missing_from_storage_has_no_revision(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        repository = TransactionCatalogueRepository(bucket_id=profile.bucket_id)
        first, second = _transaction("row-a"), _transaction("row-b")
        repository.save(_catalogue(first, second))
        before = repository.load_revision()
        objects = profile.repository
        assert objects.delete(
            TRANSACTION_CATALOGUE_NAMESPACE.namespace,
            transaction_object_key(profile.bucket_id, second.transaction_id),
        )

        after = repository.load_revision()

    assert before is not None
    assert after is None, "a listed row that is gone must not hash like a present one"
