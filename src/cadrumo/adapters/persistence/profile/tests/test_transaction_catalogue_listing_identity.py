"""The full catalogue read and the manual listing return exactly what full validation builds.

``TransactionCatalogueRepository.load`` assembles its catalogue from rows that
already passed envelope, identity and model validation, and
``list_manual_transactions`` wraps catalogue members without validating them a
second time. These tests seed a varied encrypted catalogue and compare both
reads with an oracle that decodes every stored row independently, through the
fully validated constructors: same transactions, same listing order, same
fields.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

import pytest

from cadrumo.application.ledger.actions_common import build_manual_ledger_result
from cadrumo.application.ledger.actions_manual import list_manual_transactions
from cadrumo.application.ledger.read_ports import LedgerReadPorts

from .....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from .....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from .....domain.transactions.models import Transaction, TransactionCatalogue
from .....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from .....domain.transactions.repository import transaction_object_key
from ...storage.envelope.contract import Envelope
from ...storage.secure_object_namespaces import TRANSACTION_CATALOGUE_NAMESPACE
from ...storage.sql.secure_objects import SecureObjectRepository
from ...storage.tests.secure_sql import isolated_runtime_profile
from ..buckets import BucketEventHistoryRepository
from ..transactions import TransactionCatalogueRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_BUCKET_ID = "51515151-5151-4515-8515-515151515151"
_ROWS = 36


@pytest.fixture
def authority_operation() -> Iterator[PinnedAuthorityOperation]:
    with bundled_indexed_authority().operation() as operation:
        yield operation


def _varied_transaction(index: int) -> Transaction:
    """Build one row; the set varies every axis the listing sorts or carries.

    Every third row has no value date, so the listing falls back to the booked
    date. Rows share booked dates in pairs, so the transaction id breaks ties.
    Classification, direction, tax substrate, grouping and lifecycle stamps all
    vary so a dropped or defaulted field would show in the comparison.
    """
    booked = date(2023, 1, 1) + timedelta(days=(index // 2) * 11)
    value_date = None if index % 3 == 0 else booked + timedelta(days=index % 5)
    created = datetime(2023, 1, 1, 8, 0, tzinfo=UTC) + timedelta(hours=index)
    payload: dict[str, object] = {
        "raw": RawTransaction(
            provider_transaction_id=f"identity-row-{index:03d}",
            booked_date=booked,
            value_date=value_date,
            amount=Decimal("121.00") if index % 4 == 0 else Decimal(f"{10 + index}.{index % 100:02d}"),
            currency="EUR",
            counterparty=f"Counterparty {index % 7} SL",
            description=f"identity listing row {index}",
            provenance=RawProvenance(
                source_path=Path(__file__),
                source_sha256=f"{index % 16:x}" * 64,
                source_row_index=index + 1,
                source_format=SourceFormat.CSV,
                ingested_at=created,
                provider_name="identity provider",
            ),
            raw_fields={"Concepto": f"row {index}", "Referencia": f"R{index:04d}"},
        ),
        "direction": TransactionDirection.INCOMING if index % 5 == 0 else TransactionDirection.OUTGOING,
        "group_label": None if index % 2 else f"grupo-{index % 3}",
        "source_jurisdiction": "ES",
        "created_at": created,
        "modified_at": created + timedelta(days=index % 9, minutes=index),
    }
    if index % 4 == 0:
        payload |= {
            "business_classification": BusinessClassification.BUSINESS,
            "category_id": "material_oficina",
            "taxable_base": Decimal("100.00"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("21.00"),
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": created + timedelta(hours=1),
            "classified_by": "manual",
        }
    elif index % 4 == 1:
        payload |= {"business_classification": BusinessClassification.MIXED, "business_pct": Decimal("0.60")}
    elif index % 4 == 2:
        payload |= {"business_classification": BusinessClassification.PERSONAL}
    else:
        payload |= {"business_classification": BusinessClassification.BUSINESS, "notes": f"nota {index}"}
    return Transaction.model_validate(payload)


def _oracle_catalogue(objects: SecureObjectRepository, transaction_ids: list[str]) -> TransactionCatalogue:
    """Decode each stored row on its own through the fully validated constructors."""
    transactions: list[Transaction] = []
    for transaction_id in transaction_ids:
        record = objects.load(
            TRANSACTION_CATALOGUE_NAMESPACE.namespace,
            transaction_object_key(_BUCKET_ID, transaction_id),
            expected_class=TRANSACTION_CATALOGUE_NAMESPACE.sensitivity,
            max_supported_version=TRANSACTION_CATALOGUE_NAMESPACE.schema_version,
        )
        assert record is not None
        transactions.append(Envelope[Transaction].model_validate_json(record.payload).payload)
    return TransactionCatalogue.from_transactions(transactions)


def test_full_load_and_manual_listing_equal_the_fully_validated_oracle(
    tmp_path: Path,
    authority_operation: PinnedAuthorityOperation,
) -> None:
    """Load and listing carry the same transactions, order and fields as full validation."""
    seeded = TransactionCatalogue.from_transactions(_varied_transaction(index) for index in range(_ROWS))
    assert len(seeded) == _ROWS

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository).save(seeded)
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=profile.repository)
        loaded = repository.load()
        oracle = _oracle_catalogue(profile.repository, list(loaded.transactions))
        ports = LedgerReadPorts(
            operation=authority_operation,
            transaction_repository=repository,
            bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
        )
        listed = list_manual_transactions(bucket_id=_BUCKET_ID, ports=ports)
        listed_from_held_catalogue = list_manual_transactions(bucket_id=_BUCKET_ID, ports=ports, catalogue=loaded)

    # The load: same members as the seed and the oracle, each field for field,
    # under the immutable catalogue mapping.
    assert type(loaded) is TransactionCatalogue
    assert isinstance(loaded.transactions, MappingProxyType)
    assert sorted(loaded.transactions) == sorted(seeded.transactions)
    assert list(loaded.transactions) == list(oracle.transactions)
    assert loaded == oracle
    assert loaded.model_dump(mode="json") == oracle.model_dump(mode="json")
    for transaction_id, transaction in loaded.transactions.items():
        assert transaction.transaction_id == transaction_id
        assert transaction.model_dump(mode="json") == seeded.transactions[transaction_id].model_dump(mode="json")
        assert transaction.model_fields_set == oracle.transactions[transaction_id].model_fields_set

    # The listing: the validated constructor over the seed, sorted
    # independently by effective date then id.
    expected_order = sorted(
        seeded.values(),
        key=lambda transaction: (transaction.raw.value_date or transaction.raw.booked_date, transaction.transaction_id),
    )
    expected = tuple(build_manual_ledger_result(_BUCKET_ID, transaction, ()) for transaction in expected_order)
    # Date order is not id order here, so a listing that lost its date key fails.
    assert [row.ref.transaction_id for row in expected] != sorted(row.ref.transaction_id for row in expected)
    for rows in (listed, listed_from_held_catalogue):
        assert len(rows) == _ROWS
        assert [row.ref.transaction_id for row in rows] == [row.ref.transaction_id for row in expected]
        assert rows == expected
        assert [row.model_dump(mode="json") for row in rows] == [row.model_dump(mode="json") for row in expected]
        assert [row.model_fields_set for row in rows] == [row.model_fields_set for row in expected]
        assert all(row.ref.bucket_id == _BUCKET_ID for row in rows)
        assert all(row.bucket_event_ids == () and row.stale_finalized_revisions == () for row in rows)
    assert all(row.transaction is loaded.transactions[row.ref.transaction_id] for row in listed_from_held_catalogue)
