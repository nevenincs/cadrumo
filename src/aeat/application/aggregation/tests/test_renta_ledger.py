"""Tests for repository-backed Renta ledger expense aggregation."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core import Period
from ....core.resources import resources
from ....domain.categories import SpendingCategory
from ....domain.invoices import (
    Invoice,
    InvoiceCatalogue,
    InvoiceCatalogueRepository,
    InvoiceLine,
    IvaRate,
    PaymentStatus,
)
from ....domain.iva import InvoiceKind
from ....domain.renta import RentaExpenseDirection
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
)
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    AggregationValidationError,
    CalculationSourceContext,
    LedgerRentaExpenseAggregationSourceResolver,
    RentaLedgerAggregationIssueReason,
    aggregate_renta_ledger_expenses,
    aggregate_renta_ledger_expenses_from_repositories,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="test") as profile:
        yield profile.repository


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date = date(2025, 4, 5),
    value_date: date | None = date(2025, 4, 5),
    amount: Decimal = Decimal("121.00"),
    currency: str = "EUR",
) -> RawTransaction:
    return RawTransaction(
        transaction_id=provider_id,
        booked_date=booked_date,
        value_date=value_date,
        amount=amount,
        currency=currency,
        counterparty="Proveedor SL",
        description=f"ledger row {provider_id}",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="a" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2025, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": provider_id},
    )


def _transaction(
    provider_id: str,
    *,
    amount: Decimal = Decimal("121.00"),
    category: SpendingCategory = SpendingCategory.ASESORIA_FISCAL,
    purchase_invoice_evidence_id: str | None = None,
    direction: TransactionDirection = TransactionDirection.OUTGOING,
    business_classification: BusinessClassification = BusinessClassification.BUSINESS,
    business_pct: Decimal | None = None,
    booked_date: date = date(2025, 4, 5),
    value_date: date | None = date(2025, 4, 5),
    currency: str = "EUR",
    taxable_base: Decimal | None = None,
    iva_rate: Decimal | None = None,
    iva_amount: Decimal | None = None,
    lifecycle_state: TransactionLifecycleState = TransactionLifecycleState.ACTIVE,
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw_transaction(
                provider_id,
                booked_date=booked_date,
                value_date=value_date,
                amount=amount,
                currency=currency,
            ),
            "direction": direction,
            "business_classification": business_classification,
            "business_pct": business_pct,
            "purchase_invoice_evidence_id": purchase_invoice_evidence_id,
            "category_id": category.value,
            "taxable_base": taxable_base,
            "iva_rate": iva_rate,
            "iva_amount": iva_amount,
            "lifecycle_state": lifecycle_state,
            "classified_at": datetime(2025, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _invoice(
    tx_id: str,
    *,
    bucket_id: str = "test",
    kind: InvoiceKind = InvoiceKind.RECEIVED,
    issued_at: date = date(2025, 4, 1),
    grand_total: Decimal = Decimal("121.00"),
    linked_transaction_ids: tuple[str, ...] | None = None,
) -> Invoice:
    base_total = grand_total - Decimal("21.00")
    line = InvoiceLine(
        description="Asesoria fiscal",
        quantity=Decimal("1"),
        unit_price=base_total,
        subtotal=base_total,
        iva_rate=IvaRate.RATE_21,
        iva_amount=Decimal("21.00"),
    )
    return Invoice.model_validate(
        {
            "bucket_id": bucket_id,
            "kind": kind,
            "invoice_number": f"INV-{tx_id[:8]}",
            "issued_at": issued_at,
            "counterparty_name": "Proveedor SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "base_total": base_total,
            "iva_total": Decimal("21.00"),
            "grand_total": grand_total,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "linked_transaction_ids": linked_transaction_ids if linked_transaction_ids is not None else (tx_id,),
        },
    )


def test_repository_backed_aggregation_loads_persisted_catalogues_and_emits_casilla_values(
    secure_objects: SecureObjectRepository,
) -> None:
    initial = _transaction("row-linked")
    invoice = _invoice(initial.transaction_id)
    linked = _transaction("row-linked", purchase_invoice_evidence_id=invoice.invoice_id)
    tx_repo = TransactionCatalogueRepository(bucket_id="test", objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id="test", objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions((linked,)))
    invoice_repo.save(InvoiceCatalogue.from_invoices((invoice,)))

    result = aggregate_renta_ledger_expenses_from_repositories(
        bucket_id="test",
        period="2025",
        transaction_repository=TransactionCatalogueRepository(bucket_id="test", objects=secure_objects),
        invoice_repository=InvoiceCatalogueRepository(bucket_id="test", objects=secure_objects),
        profile_year=2025,
    )

    assert result.issues == ()
    assert result.casilla_values == {"0199": Decimal("121.00")}
    assert len(result.observations) == 1
    observation = result.observations[0]
    assert observation.transaction_id == linked.transaction_id
    assert observation.invoice_id == invoice.invoice_id
    assert observation.filing_date == date(2025, 4, 1)
    assert observation.taxable_base == Decimal("100.00")
    assert observation.iva_amount == Decimal("21.00")
    assert result.casilla_aggregation.provenance[0].transaction_ids == (linked.transaction_id,)


def test_repository_backed_aggregation_binds_default_invoice_repository_to_requested_bucket(
    secure_objects: SecureObjectRepository,
) -> None:
    initial = _transaction("row-default-invoice-repository")
    invoice = _invoice(initial.transaction_id)
    linked = _transaction(
        "row-default-invoice-repository",
        purchase_invoice_evidence_id=invoice.invoice_id,
    )
    TransactionCatalogueRepository(bucket_id="test", objects=secure_objects).save(
        TransactionCatalogue.from_transactions((linked,)),
    )
    InvoiceCatalogueRepository(bucket_id="test", objects=secure_objects).save(
        InvoiceCatalogue.from_invoices((invoice,)),
    )

    result = aggregate_renta_ledger_expenses_from_repositories(
        bucket_id="test",
        period="2025",
        transaction_repository=TransactionCatalogueRepository(bucket_id="test", objects=secure_objects),
        profile_year=2025,
    )

    assert result.issues == ()
    assert result.observations[0].invoice_id == invoice.invoice_id
    assert result.casilla_values == {"0199": Decimal("121.00")}


def test_renta_filing_aggregation_resolves_registry_bound_inputs(secure_objects: SecureObjectRepository) -> None:
    """The LedgerRentaExpenseAggregationSourceResolver resolves modelo-100 renta-expense
    ledger bindings from repository-backed transactions, keyed by binding id."""
    transaction = _transaction(
        "row-cli-renta",
        amount=Decimal("121.00"),
        category=SpendingCategory.ASESORIA_FISCAL,
    )
    tx_repo = TransactionCatalogueRepository(bucket_id="test", objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id="test", objects=secure_objects)
    tx_repo.save(TransactionCatalogue.from_transactions((transaction,)))
    invoice_repo.save(InvoiceCatalogue())

    snapshot = resources().modelos.authority.snapshot("100", filing_year=2025, period="0A")
    resolution = LedgerRentaExpenseAggregationSourceResolver(
        transaction_repository=TransactionCatalogueRepository(bucket_id="test", objects=secure_objects),
        invoice_repository=InvoiceCatalogueRepository(bucket_id="test", objects=secure_objects),
    ).resolve(
        CalculationSourceContext(
            bucket_id="test",
            modelo="100",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            revision=snapshot.revision,
        ),
    )
    binding_values = resolution.binding_values

    assert binding_values["renta-2025-ledger-expense-0199-deductible"] == Decimal("121.00")
    assert binding_values["renta-2025-ledger-expense-0186-deductible"] == Decimal("0")
    assert binding_values["renta-2025-ledger-expense-0192-deductible"] == Decimal("0")
    assert binding_values["renta-2025-ledger-expense-0203-deductible"] == Decimal("0")


def test_repository_backed_aggregation_rejects_transaction_repository_bucket_mismatch(
    secure_objects: SecureObjectRepository,
) -> None:
    repo = TransactionCatalogueRepository(bucket_id="other", objects=secure_objects)

    with pytest.raises(AggregationValidationError, match="bucket"):
        aggregate_renta_ledger_expenses_from_repositories(
            bucket_id="test",
            period="2025",
            transaction_repository=repo,
            invoice_repository=InvoiceCatalogueRepository(bucket_id="test", objects=secure_objects),
            profile_year=2025,
        )


def test_repository_backed_aggregation_rejects_invoice_repository_bucket_mismatch(
    secure_objects: SecureObjectRepository,
) -> None:
    tx_repo = TransactionCatalogueRepository(bucket_id="test", objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(bucket_id="other", objects=secure_objects)

    with pytest.raises(AggregationValidationError, match="invoice_bucket_mismatch"):
        aggregate_renta_ledger_expenses_from_repositories(
            bucket_id="test",
            period="2025",
            transaction_repository=tx_repo,
            invoice_repository=invoice_repo,
            profile_year=2025,
        )


def test_repository_backed_aggregation_rejects_unbound_invoice_repository(
    secure_objects: SecureObjectRepository,
) -> None:
    tx_repo = TransactionCatalogueRepository(bucket_id="test", objects=secure_objects)
    invoice_repo = InvoiceCatalogueRepository(objects=secure_objects)

    with pytest.raises(AggregationValidationError, match="invoice_bucket_mismatch"):
        aggregate_renta_ledger_expenses_from_repositories(
            bucket_id="test",
            period="2025",
            transaction_repository=tx_repo,
            invoice_repository=invoice_repo,
            profile_year=2025,
        )


def test_mixed_business_percentage_scales_transaction_only_expenses() -> None:
    mixed = _transaction(
        "row-mixed",
        amount=Decimal("200.00"),
        category=SpendingCategory.GASTOS_BANCARIOS,
        business_classification=BusinessClassification.MIXED,
        business_pct=Decimal("0.25"),
        purchase_invoice_evidence_id=None,
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((mixed,)),
        InvoiceCatalogue(),
        bucket_id="test",
        period="2025",
        profile_year=2025,
    )

    assert result.issues == ()
    assert result.casilla_values == {"0203": Decimal("50.0000")}
    assert result.observations[0].gross_amount == Decimal("50.0000")
    assert result.observations[0].deductible_amount == Decimal("50.0000")


def test_archived_and_stashed_transactions_do_not_feed_renta_expense_aggregation() -> None:
    active = _transaction(
        "row-active",
        amount=Decimal("100.00"),
        category=SpendingCategory.GASTOS_BANCARIOS,
    )
    archived = _transaction(
        "row-archived",
        amount=Decimal("500.00"),
        category=SpendingCategory.GASTOS_BANCARIOS,
        lifecycle_state=TransactionLifecycleState.ARCHIVED,
    )
    stashed = _transaction(
        "row-stashed",
        amount=Decimal("700.00"),
        category=SpendingCategory.GASTOS_BANCARIOS,
        lifecycle_state=TransactionLifecycleState.STASHED,
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((active, archived, stashed)),
        InvoiceCatalogue(),
        bucket_id="test",
        period="2025",
        profile_year=2025,
    )

    assert result.issues == ()
    assert [observation.transaction_id for observation in result.observations] == [active.transaction_id]
    assert result.casilla_values == {"0203": Decimal("100.00")}


def test_manual_transaction_tax_fields_feed_renta_observation_without_invoice_catalogue() -> None:
    manual = _transaction(
        "manual-tax-fields",
        amount=Decimal("121.00"),
        category=SpendingCategory.ASESORIA_FISCAL,
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((manual,)),
        InvoiceCatalogue(),
        bucket_id="test",
        period="2025",
        profile_year=2025,
    )

    assert result.issues == ()
    assert result.observations[0].taxable_base == Decimal("100.00")
    assert result.observations[0].iva_amount == Decimal("21.00")


def test_linked_invoice_issue_date_controls_period_filtering() -> None:
    initial = _transaction("row-outside")
    invoice = _invoice(initial.transaction_id, issued_at=date(2024, 12, 31))
    linked = _transaction("row-outside", purchase_invoice_evidence_id=invoice.invoice_id)

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((linked,)),
        InvoiceCatalogue.from_invoices((invoice,)),
        bucket_id="test",
        period="2025",
        profile_year=2025,
    )

    assert result.observations == ()
    assert result.issues[0].reason is RentaLedgerAggregationIssueReason.OUTSIDE_PERIOD
    assert result.issues[0].transaction_id == linked.transaction_id


def test_multi_transaction_invoice_link_is_excluded_from_first_slice() -> None:
    first = _transaction("row-partial-a")
    second = _transaction("row-partial-b", amount=Decimal("60.50"))
    invoice = _invoice(first.transaction_id, linked_transaction_ids=(first.transaction_id, second.transaction_id))
    linked = _transaction("row-partial-a", purchase_invoice_evidence_id=invoice.invoice_id)

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((linked,)),
        InvoiceCatalogue.from_invoices((invoice,)),
        bucket_id="test",
        period="2025",
        profile_year=2025,
    )

    assert result.observations == ()
    assert (
        result.issues[0].reason
        is RentaLedgerAggregationIssueReason.PARTIAL_OR_MULTI_TRANSACTION_PURCHASE_INVOICE_EVIDENCE
    )


def test_purchase_invoice_evidence_from_other_bucket_is_reported_as_issue() -> None:
    initial = _transaction("row-cross-bucket")
    invoice = _invoice(initial.transaction_id, bucket_id="other")
    linked = _transaction("row-cross-bucket", purchase_invoice_evidence_id=invoice.invoice_id)

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((linked,)),
        InvoiceCatalogue.from_invoices((invoice,)),
        bucket_id="test",
        period="2025",
        profile_year=2025,
    )

    assert result.observations == ()
    assert result.issues[0].reason is RentaLedgerAggregationIssueReason.PURCHASE_INVOICE_EVIDENCE_BUCKET_MISMATCH
    assert result.issues[0].purchase_invoice_evidence_id == invoice.invoice_id


def test_linked_incoming_refund_becomes_negative_binding_value() -> None:
    initial = _transaction(
        "row-refund",
        amount=Decimal("121.00"),
        direction=TransactionDirection.INCOMING,
    )
    invoice = _invoice(initial.transaction_id)
    refund = _transaction(
        "row-refund",
        amount=Decimal("121.00"),
        purchase_invoice_evidence_id=invoice.invoice_id,
        direction=TransactionDirection.INCOMING,
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((refund,)),
        InvoiceCatalogue.from_invoices((invoice,)),
        bucket_id="test",
        period="2025",
        profile_year=2025,
    )

    assert result.issues == ()
    assert result.observations[0].direction is RentaExpenseDirection.REFUND
    assert result.casilla_values == {"0199": Decimal("-121.00")}


def test_transaction_only_renta_expense_buckets_on_value_date_caja_basis() -> None:
    """Document the CAJA-only basis for a transaction-only (un-invoiced) expense.

    For a Renta expense with no linked invoice, the first-slice ``filing_date``
    falls back to ``operation_date`` = ``value_date or booked_date`` — a CASH
    (caja) basis. There is no accrual/devengo basis selector.

    This pins the current behaviour as the regression anchor for the future
    devengo follow-on (#58): the row whose VALUE_DATE lands in the tax year is
    aggregated; the mirror row whose value_date is outside (but booked_date
    inside) is excluded. A devengo basis would invert both outcomes.

    Note ``test_linked_invoice_issue_date_controls_period_filtering`` covers the
    *linked-invoice* branch, where the invoice issue date (not the payment date)
    drives period selection — that is invoice-date provenance, NOT an accrual
    basis selector. This test covers the un-invoiced branch where caja governs.
    """
    # value_date in-year (caja), booked_date in the prior year (devengo would differ).
    caja_in_year = _transaction(
        "row-caja-in-year",
        amount=Decimal("100.00"),
        category=SpendingCategory.GASTOS_BANCARIOS,
        booked_date=date(2024, 12, 31),
        value_date=date(2025, 1, 2),
        purchase_invoice_evidence_id=None,
    )
    # value_date in the prior year (caja), booked_date in-year (devengo would include).
    caja_out_of_year = _transaction(
        "row-caja-out-of-year",
        amount=Decimal("100.00"),
        category=SpendingCategory.GASTOS_BANCARIOS,
        booked_date=date(2025, 1, 2),
        value_date=date(2024, 12, 31),
        purchase_invoice_evidence_id=None,
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((caja_in_year, caja_out_of_year)),
        InvoiceCatalogue(),
        bucket_id="test",
        period="2025",
        profile_year=2025,
    )

    # Caja basis: only the row whose VALUE_DATE is in-year is aggregated, and the
    # observation's filing_date is that value_date (operation_date fallback).
    assert [observation.transaction_id for observation in result.observations] == [caja_in_year.transaction_id]
    assert result.observations[0].filing_date == date(2025, 1, 2)
    assert result.casilla_values == {"0203": Decimal("100.00")}
    # The mirror row is excluded keyed on value_date — a devengo basis
    # (booked_date 2025-01-02) would instead have INCLUDED it.
    assert [issue.transaction_id for issue in result.issues] == [caja_out_of_year.transaction_id]
    assert result.issues[0].reason is RentaLedgerAggregationIssueReason.OUTSIDE_PERIOD
    assert "2024-12-31" in result.issues[0].detail


def test_non_eur_transaction_is_reported_as_issue_before_fact_creation() -> None:
    usd_expense = _transaction(
        "row-usd",
        category=SpendingCategory.GASTOS_BANCARIOS,
        purchase_invoice_evidence_id=None,
        currency="USD",
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((usd_expense,)),
        InvoiceCatalogue(),
        bucket_id="test",
        period="2025",
        profile_year=2025,
    )

    assert result.observations == ()
    assert result.issues[0].reason is RentaLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY


def test_zero_business_amount_is_reported_as_invalid_fact_issue() -> None:
    zero_business = _transaction(
        "row-zero-business",
        amount=Decimal("200.00"),
        category=SpendingCategory.GASTOS_BANCARIOS,
        business_classification=BusinessClassification.MIXED,
        business_pct=Decimal("0"),
        purchase_invoice_evidence_id=None,
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((zero_business,)),
        InvoiceCatalogue(),
        bucket_id="test",
        period="2025",
        profile_year=2025,
    )

    assert result.observations == ()
    assert result.issues[0].reason is RentaLedgerAggregationIssueReason.INVALID_LEDGER_FACT
