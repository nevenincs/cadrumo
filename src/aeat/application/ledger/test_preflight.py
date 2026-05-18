"""Tests for ledger modelo-readiness preflight."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from ...adapters.persistence.storage import EphemeralMasterKeyProvider
from ...adapters.persistence.storage.sql import SecureObjectRepository, create_engine_from_settings
from ...adapters.persistence.storage.sql._orm import Base
from ...core.config import Settings
from ...domain.categories import SpendingCategory
from ...domain.transactions import (
    BusinessClassification,
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionCatalogueRepository,
    TransactionDirection,
    TransactionLifecycleState,
    TransactionValidationError,
)
from . import LedgerPreflightIssueReason, preflight_ledger_tax_readiness, preflight_transaction_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def secure_engine(tmp_path: Path) -> Iterator[Engine]:
    provider = EphemeralMasterKeyProvider()
    with provider:
        engine = create_engine_from_settings(Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}"))
        Base.metadata.create_all(engine)
        try:
            yield engine
        finally:
            engine.dispose()


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date = date(2026, 4, 5),
    amount: Decimal = Decimal("-121.00"),
    currency: str = "EUR",
) -> RawTransaction:
    return RawTransaction(
        transaction_id=provider_id,
        booked_date=booked_date,
        value_date=booked_date,
        amount=amount,
        currency=currency,
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
        raw_fields={"source_kind": "ledger_transaction"},
    )


def _transaction(
    provider_id: str,
    *,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    amount: Decimal = Decimal("-121.00"),
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    business_pct: Decimal | None = None,
    category_id: str | None = SpendingCategory.MATERIAL_OFICINA.value,
    taxable_base: Decimal | None = Decimal("100.00"),
    iva_rate: Decimal | None = Decimal("0.21"),
    iva_amount: Decimal | None = Decimal("21.00"),
    usage_ratio_id: str | None = None,
    booked_date: date = date(2026, 4, 5),
    currency: str = "EUR",
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(provider_id, booked_date=booked_date, amount=amount, currency=currency),
            "direction": direction,
            "business_classification": business_classification,
            "business_pct": business_pct,
            "category_id": category_id,
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "usage_ratio_id": usage_ratio_id,
            "lifecycle_state": lifecycle_state,
            "classified_at": datetime(2026, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        }
    )


def test_preflight_reports_all_missing_modelo_readiness_facts() -> None:
    unclassified = _transaction(
        "row-unclassified",
        business_classification=BusinessClassification.NOT_YET_PROCESSED,
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
    )
    missing_business_facts = _transaction(
        "row-missing-facts",
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
    )
    mixed_missing_ratio = _transaction(
        "row-mixed",
        business_classification=BusinessClassification.MIXED,
        business_pct=Decimal("0.40"),
        category_id=SpendingCategory.TELEFONIA_MOVIL.value,
        usage_ratio_id=None,
    )

    report = preflight_transaction_catalogue(
        bucket_id="bucket-a",
        period="2026Q2",
        transactions=TransactionCatalogue.from_transactions(
            (unclassified, missing_business_facts, mixed_missing_ratio)
        ),
    )

    assert report.ready is False
    assert report.checked_transaction_count == 3
    assert sorted(issue.reason for issue in report.issues) == sorted(
        (
            LedgerPreflightIssueReason.MISSING_BUSINESS_CLASSIFICATION,
            LedgerPreflightIssueReason.MISSING_CATEGORY,
            LedgerPreflightIssueReason.MISSING_TAXABLE_BASE,
            LedgerPreflightIssueReason.MISSING_IVA_AMOUNT,
            LedgerPreflightIssueReason.MISSING_IVA_RATE,
            LedgerPreflightIssueReason.MISSING_PROPORTIONALITY_REFERENCE,
        )
    )


def test_preflight_ignores_personal_internal_transfer_and_out_of_period_rows() -> None:
    personal = _transaction(
        "row-personal",
        business_classification=BusinessClassification.PERSONAL,
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
    )
    transfer = _transaction(
        "row-transfer",
        direction=TransactionDirection.INTERNAL_TRANSFER,
        business_classification=BusinessClassification.NOT_YET_PROCESSED,
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
    )
    old = _transaction(
        "row-old",
        booked_date=date(2026, 1, 5),
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
    )

    report = preflight_transaction_catalogue(
        bucket_id="bucket-a",
        period="2026Q2",
        transactions=TransactionCatalogue.from_transactions((personal, transfer, old)),
    )

    assert report.checked_transaction_count == 2
    assert report.issues == ()
    assert report.ready is True


def test_preflight_ignores_archived_and_stashed_rows() -> None:
    ready = _transaction("row-ready")
    archived_missing_facts = _transaction(
        "row-archived",
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
        lifecycle_state=TransactionLifecycleState.ARCHIVED,
    )
    stashed_missing_facts = _transaction(
        "row-stashed",
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
        lifecycle_state=TransactionLifecycleState.STASHED,
    )

    report = preflight_transaction_catalogue(
        bucket_id="bucket-a",
        period="2026Q2",
        transactions=TransactionCatalogue.from_transactions((ready, archived_missing_facts, stashed_missing_facts)),
    )

    assert report.checked_transaction_count == 1
    assert report.issues == ()
    assert report.ready is True


def test_preflight_reports_unsupported_currency_before_modelo_aggregation() -> None:
    usd = _transaction("row-usd", currency="USD")

    report = preflight_transaction_catalogue(
        bucket_id="bucket-a",
        period="2026Q2",
        transactions=TransactionCatalogue.from_transactions((usd,)),
    )

    assert report.ready is False
    assert [issue.reason for issue in report.issues] == [LedgerPreflightIssueReason.UNSUPPORTED_CURRENCY]


def test_preflight_repository_path_loads_bucket_catalogue(secure_engine: Engine) -> None:
    objects = SecureObjectRepository(engine=secure_engine)
    repository = TransactionCatalogueRepository(bucket_id="bucket-a", objects=objects)
    repository.save(TransactionCatalogue.from_transactions((_transaction("row-ready"),)))

    report = preflight_ledger_tax_readiness(
        bucket_id="bucket-a",
        period="2026Q2",
        transaction_repository=TransactionCatalogueRepository(bucket_id="bucket-a", objects=objects),
    )

    assert report.ready is True
    assert report.checked_transaction_count == 1
    assert report.issues == ()


def test_preflight_rejects_repository_bucket_mismatch() -> None:
    with pytest.raises(TransactionValidationError, match="bucket_id"):
        preflight_ledger_tax_readiness(
            bucket_id="bucket-a",
            period="2026Q2",
            transaction_repository=TransactionCatalogueRepository(bucket_id="bucket-b"),
        )
