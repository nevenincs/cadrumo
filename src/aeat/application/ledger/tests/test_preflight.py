"""Tests for ledger modelo-readiness preflight."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....domain.categories import SpendingCategory
from ....domain.transactions import (
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
from ....tests.secure_sql import isolated_runtime_profile
from .. import LedgerPreflightIssueReason, preflight_ledger_tax_readiness, preflight_transaction_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _period(year: int, code: str) -> Period:
    return Period.from_year_and_code(year, code)


_Q2_2026 = _period(2026, "2T")


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        yield profile.repository


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date = date(2026, 4, 5),
    amount: Decimal = Decimal("121.00"),
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
    amount: Decimal = Decimal("121.00"),
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    business_pct: Decimal | None = None,
    category_id: str | None = SpendingCategory.MATERIAL_OFICINA.value,
    taxable_base: Decimal | None = Decimal("100.00"),
    iva_rate: Decimal | None = Decimal("0.21"),
    iva_amount: Decimal | None = Decimal("21.00"),
    irpf_category: str | None = None,
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
            "irpf_category": irpf_category,
            "usage_ratio_id": usage_ratio_id,
            "lifecycle_state": lifecycle_state,
            "classified_at": datetime(2026, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
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
        period=_Q2_2026,
        transactions=TransactionCatalogue.from_transactions(
            (unclassified, missing_business_facts, mixed_missing_ratio),
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
        ),
    )


def test_preflight_does_not_flag_missing_category_on_income_transaction() -> None:
    """An INCOMING (income) transaction with no category_id must not be
    flagged missing_category.

    ``category_id`` is a SpendingCategory foreign key — a
    deductible-expense taxonomy. The only modelo binding that reads it
    is the Renta first-slice expense aggregation, which never admits a
    pure-income transaction. Income is classified by direction alone,
    so forcing an expense category onto it is a modelling error.
    """

    income = _transaction(
        "row-income",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("1500.00"),
        category_id=None,
        taxable_base=Decimal("1239.67"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("260.33"),
    )

    report = preflight_transaction_catalogue(
        bucket_id="bucket-a",
        period=_Q2_2026,
        transactions=TransactionCatalogue.from_transactions((income,)),
    )

    assert report.checked_transaction_count == 1
    assert LedgerPreflightIssueReason.MISSING_CATEGORY not in {issue.reason for issue in report.issues}
    assert report.ready is True


def test_preflight_still_flags_missing_category_on_expense_transaction() -> None:
    """An OUTGOING (expense) transaction with no category_id must still
    be flagged missing_category; the deductible-expense pipeline
    genuinely needs the spending-category foreign key."""

    expense = _transaction(
        "row-expense",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("121.00"),
        category_id=None,
    )

    report = preflight_transaction_catalogue(
        bucket_id="bucket-a",
        period=_Q2_2026,
        transactions=TransactionCatalogue.from_transactions((expense,)),
    )

    assert LedgerPreflightIssueReason.MISSING_CATEGORY in {issue.reason for issue in report.issues}


def test_preflight_flags_missing_category_on_income_refund_with_purchase_evidence() -> None:
    """An INCOMING transaction that carries a purchase-invoice evidence
    id is an expense refund — it feeds the Renta expense pipeline and
    therefore does need a deductible-expense category."""

    refund = Transaction.model_validate(
        {
            "raw": _raw_transaction("row-refund", amount=Decimal("45.00")),
            "direction": TransactionDirection.INCOMING,
            "business_classification": BusinessClassification.BUSINESS,
            "business_pct": None,
            "category_id": None,
            "purchase_invoice_evidence_id": "evidence-001",
            "taxable_base": Decimal("37.19"),
            "iva_rate": Decimal("0.21"),
            "iva_amount": Decimal("7.81"),
            "usage_ratio_id": None,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2026, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )

    report = preflight_transaction_catalogue(
        bucket_id="bucket-a",
        period=_Q2_2026,
        transactions=TransactionCatalogue.from_transactions((refund,)),
    )

    assert LedgerPreflightIssueReason.MISSING_CATEGORY in {issue.reason for issue in report.issues}


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
        period=_Q2_2026,
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
        period=_Q2_2026,
        transactions=TransactionCatalogue.from_transactions((ready, archived_missing_facts, stashed_missing_facts)),
    )

    assert report.checked_transaction_count == 1
    assert report.issues == ()
    assert report.ready is True


def test_preflight_skips_iva_facts_on_trabajo_income_rows() -> None:
    """An INCOMING transaction with ``irpf_category="trabajo"`` (nómina) is
    IVA-exempt: the IRPF retenciones binding consumes the gross amount and
    the IVA aggregation never reads taxable_base / iva_rate / iva_amount.
    Preflight must NOT flag missing_taxable_base + missing_iva_amount +
    missing_iva_rate on these rows.

    Closes the R9-ANDREA-HIGH false-positive surfaced in cross-domain-
    continuity contract.
    """
    nomina = _transaction(
        "row-nomina",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("1850.00"),
        irpf_category="trabajo",
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
    )

    report = preflight_transaction_catalogue(
        bucket_id="bucket-a",
        period=_Q2_2026,
        transactions=TransactionCatalogue.from_transactions((nomina,)),
    )

    assert report.ready is True, [issue.reason for issue in report.issues]
    assert report.issues == ()


def test_preflight_still_flags_iva_facts_on_non_trabajo_income_rows() -> None:
    """Anti-regression: an INCOMING row WITHOUT ``irpf_category="trabajo"``
    still surfaces missing-IVA-fact findings. Only the nómina-shaped row
    is exempt; the trabajo guard must not silence general income rows."""

    income_no_irpf = _transaction(
        "row-income-no-irpf",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("500.00"),
        irpf_category=None,
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
    )

    report = preflight_transaction_catalogue(
        bucket_id="bucket-a",
        period=_Q2_2026,
        transactions=TransactionCatalogue.from_transactions((income_no_irpf,)),
    )

    assert report.ready is False
    surfaced = {issue.reason for issue in report.issues}
    assert LedgerPreflightIssueReason.MISSING_TAXABLE_BASE in surfaced
    assert LedgerPreflightIssueReason.MISSING_IVA_AMOUNT in surfaced
    assert LedgerPreflightIssueReason.MISSING_IVA_RATE in surfaced


def test_preflight_reports_unsupported_currency_before_modelo_aggregation() -> None:
    usd = _transaction("row-usd", currency="USD")

    report = preflight_transaction_catalogue(
        bucket_id="bucket-a",
        period=_Q2_2026,
        transactions=TransactionCatalogue.from_transactions((usd,)),
    )

    assert report.ready is False
    assert [issue.reason for issue in report.issues] == [LedgerPreflightIssueReason.UNSUPPORTED_CURRENCY]


def test_preflight_repository_path_loads_bucket_catalogue(secure_objects: SecureObjectRepository) -> None:
    objects = secure_objects
    repository = TransactionCatalogueRepository(bucket_id="bucket-a", objects=objects)
    repository.save(TransactionCatalogue.from_transactions((_transaction("row-ready"),)))

    report = preflight_ledger_tax_readiness(
        bucket_id="bucket-a",
        period=_Q2_2026,
        transaction_repository=TransactionCatalogueRepository(bucket_id="bucket-a", objects=objects),
    )

    assert report.ready is True
    assert report.checked_transaction_count == 1
    assert report.issues == ()


def test_preflight_default_repository_loads_active_runtime_bucket(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="bucket-a") as profile:
        TransactionCatalogueRepository(bucket_id=profile.bucket_id).save(
            TransactionCatalogue.from_transactions((_transaction("row-ready"),)),
        )

        report = preflight_ledger_tax_readiness(bucket_id=profile.bucket_id, period=_Q2_2026)

    assert report.ready is True
    assert report.checked_transaction_count == 1
    assert report.issues == ()


def test_preflight_rejects_repository_bucket_mismatch(secure_objects: SecureObjectRepository) -> None:
    objects = secure_objects
    with pytest.raises(TransactionValidationError, match="bucket_id"):
        preflight_ledger_tax_readiness(
            bucket_id="bucket-a",
            period=_Q2_2026,
            transaction_repository=TransactionCatalogueRepository(bucket_id="bucket-b", objects=objects),
        )
