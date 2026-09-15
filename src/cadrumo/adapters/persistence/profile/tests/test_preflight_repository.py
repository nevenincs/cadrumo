"""Repository-backed ledger modelo-readiness preflight tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.transactions import TransactionCatalogueRepository
from cadrumo.adapters.persistence.profile.usage_ratios import load_usage_ratios
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_runtime_profile
from cadrumo.application.ledger.preflight import preflight_ledger_tax_readiness
from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.period import Period
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority as _indexed_authority_for_test
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from cadrumo.domain.transactions.errors import TransactionValidationError
from cadrumo.domain.transactions.models import Transaction, TransactionCatalogue
from cadrumo.domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

_BUCKET_ID = "22222222-2222-4222-8222-222222222222"
_OTHER_BUCKET_ID = "23232323-2323-4323-8323-232323232323"
_Q2_2026 = Period.from_year_and_code(2026, "2T")


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile.repository


def _transaction(
    provider_id: str,
    *,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    amount: Decimal = Decimal("121.00"),
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    category_id: str | None = SpendingCategory.from_registry("material_oficina").value,
) -> Transaction:
    booked_date = date(2026, 4, 5)
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency="EUR",
        counterparty="Cliente o proveedor",
        description=f"ledger row {provider_id}",
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
            "direction": direction,
            "group_label": None,
            "business_classification": business_classification,
            "source_jurisdiction": "ES",
            "business_pct": None,
            "category_id": category_id,
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


pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def test_preflight_repository_path_loads_bucket_catalogue(secure_objects: SecureObjectRepository) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        objects = secure_objects
        repository = TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects)
        repository.save(TransactionCatalogue.from_transactions((_transaction("row-ready"),)))

        report = preflight_ledger_tax_readiness(
            bucket_id=_BUCKET_ID,
            period=_Q2_2026,
            usage_ratio_profile_loader=load_usage_ratios,
            transaction_repository=TransactionCatalogueRepository(bucket_id=_BUCKET_ID, objects=objects),
            operation=_authority_operation_for_test,
        )

        assert report.ready is True
        assert report.checked_transaction_count == 1
        assert report.issues == ()


def test_preflight_default_repository_loads_active_runtime_bucket(tmp_path: Path) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
            TransactionCatalogueRepository(bucket_id=profile.bucket_id).save(
                TransactionCatalogue.from_transactions((_transaction("row-ready"),)),
            )

            report = preflight_ledger_tax_readiness(
                bucket_id=profile.bucket_id,
                period=_Q2_2026,
                usage_ratio_profile_loader=load_usage_ratios,
                operation=_authority_operation_for_test,
            )

        assert report.ready is True
        assert report.checked_transaction_count == 1
        assert report.issues == ()


def test_preflight_rejects_repository_bucket_mismatch(secure_objects: SecureObjectRepository) -> None:
    with _indexed_authority_for_test().operation() as _authority_operation_for_test:
        objects = secure_objects
        with pytest.raises(TransactionValidationError, match="bucket_id"):
            preflight_ledger_tax_readiness(
                bucket_id=_BUCKET_ID,
                period=_Q2_2026,
                usage_ratio_profile_loader=load_usage_ratios,
                transaction_repository=TransactionCatalogueRepository(bucket_id=_OTHER_BUCKET_ID, objects=objects),
                operation=_authority_operation_for_test,
            )
