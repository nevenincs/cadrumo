"""Tests for repository-backed Renta ledger expense aggregation."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.published_authority import (
    leased_profile_create_context as _profile_creation_context_for_test,
)
from cadrumo.domain.categories.proportionality_catalogue import require_proportionality_kind
from cadrumo.domain.categories.spending_category import SpendingCategory
from cadrumo.domain.invoices.enums import resolve_iva_rate_token
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test

from ....core.aggregation import BindingAggregation, BindingAggregationOp
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.i18n.translatable import Translatable as tr
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from ....domain.calculations.registry.schema_references import PeriodSelector
from ....domain.categories.profile import CategoryProfile
from ....domain.categories.proportionality import (
    CategoryCitation,
    CategoryCitationSource,
    ProportionalityRule,
    parse_http_url,
)
from ....domain.contribuyente.ccaa import CCAA
from ....domain.invoices.enums import PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ....domain.iva.schema import InvoiceKind
from ....domain.renta.ledger_expenses import RentaExpenseDirection
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.aeat_literal_fixtures import RENTA_REGIMEN_CITATION_URL_FIXTURE
from ..renta_ledger import (
    RentaLedgerAggregationIssueReason,
    aggregate_renta_ledger_expenses,
)
from .renta_income_aggregation_support import _period
from .usage_ratio_support import (
    HOME_OFFICE_DEGREE_OF_USE,
    HOME_OFFICE_SUMINISTRO_RATIO,
    dwelling_classify_share,
    dwelling_profile,
    dwelling_usage_ratios,
)

SECURE_OBJECTS_BUCKET_ID = "78804f92-b6f7-4daf-9ddf-a8ce3829dbb1"
_DEFAULT_SPENDING_CATEGORY = SpendingCategory.from_registry("asesoria_fiscal")

pytestmark = [
    pytest.mark.unit,
    pytest.mark.hex_application,
    pytest.mark.usefixtures("authority_operation"),
    pytest.mark.usefixtures("operation"),
]


def _m100_renta_expense_binding(binding_id: str, casilla_id: str) -> BindingDefinition:
    return BindingDefinition(
        id=binding_id,
        provider={
            "kind": "ledger_renta_gastos_estimacion_directa_aggregation",
            **{
                "modelo": "100",
                "period": "0A",
                "target_casilla_id": casilla_id,
                "fact": "deductible_amount_sum",
            },
        },
        value={"data_type": "money", "channel": "decimal"},
        aggregation=BindingAggregation(op=BindingAggregationOp.SUM),
        legal_refs=("ley-35-2006:art-28", "ley-35-2006:art-30"),
        source_refs=("aeat-renta-2025-manual-parte1",),
    )


def _m100_2025_renta_expense_revision() -> ModeloRevision:
    return ModeloRevision(
        id="2025",
        localization_key="test.schema.revision.2025.label",
        valid_from=date(2026, 1, 1),
        period_selector=PeriodSelector(years=(2025,), periods=("0A",)),
        legal_refs=("ley-35-2006:art-28", "ley-35-2006:art-30"),
        source_refs=("aeat-renta-2025-manual-parte1",),
        bindings=(
            _m100_renta_expense_binding("renta-ledger-expense-0186-deductible", "0186"),
            _m100_renta_expense_binding("renta-ledger-expense-0192-deductible", "0192"),
            _m100_renta_expense_binding("renta-ledger-expense-0199-deductible", "0199"),
            _m100_renta_expense_binding("renta-ledger-expense-0203-deductible", "0203"),
        ),
    )


_ANNUAL_2025 = _period(2025, "0A")
_Q1_2025 = _period(2025, "1T")
_M100_ASESORIA_CASILLA: CasillaId = validated_casilla_id("0199", surface="_M100_ASESORIA_CASILLA")
_M100_GASTOS_FINANCIEROS_CASILLA: CasillaId = validated_casilla_id(
    "0203",
    surface="_M100_GASTOS_FINANCIEROS_CASILLA",
)
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02", surface="_M130_GASTOS_CASILLA")


def _raw_transaction(
    provider_id: str,
    *,
    booked_date: date = date(2025, 4, 5),
    value_date: date | None = date(2025, 4, 5),
    amount: Decimal = Decimal("121.00"),
    currency: str = "EUR",
) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
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
    category: SpendingCategory = _DEFAULT_SPENDING_CATEGORY,
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
    usage_ratio_id: str | None = None,
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
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": business_classification,
            "business_pct": business_pct,
            "usage_ratio_id": usage_ratio_id,
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
    bucket_id: str = SECURE_OBJECTS_BUCKET_ID,
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
        iva_rate=resolve_iva_rate_token("RATE_21", date.today()),
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


def test_mixed_business_percentage_scales_transaction_only_expenses() -> None:
    mixed = _transaction(
        "row-mixed",
        amount=Decimal("200.00"),
        category=SpendingCategory.from_registry("gastos_bancarios"),
        business_classification=BusinessClassification.MIXED,
        business_pct=Decimal("0.25"),
        purchase_invoice_evidence_id=None,
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((mixed,)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    assert result.issues == ()
    assert result.casilla_values == {_M100_GASTOS_FINANCIEROS_CASILLA: Decimal("50.0000")}
    assert result.observations[0].gross_amount == Decimal("50.0000")
    assert result.observations[0].deductible_amount == Decimal("50.0000")


def test_archived_and_stashed_transactions_do_not_feed_renta_expense_aggregation() -> None:
    active = _transaction(
        "row-active",
        amount=Decimal("100.00"),
        category=SpendingCategory.from_registry("gastos_bancarios"),
    )
    archived = _transaction(
        "row-archived",
        amount=Decimal("500.00"),
        category=SpendingCategory.from_registry("gastos_bancarios"),
        lifecycle_state=TransactionLifecycleState.ARCHIVED,
    )
    stashed = _transaction(
        "row-stashed",
        amount=Decimal("700.00"),
        category=SpendingCategory.from_registry("gastos_bancarios"),
        lifecycle_state=TransactionLifecycleState.STASHED,
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((active, archived, stashed)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    assert result.issues == ()
    assert [observation.transaction_id for observation in result.observations] == [active.transaction_id]
    assert result.casilla_values == {_M100_GASTOS_FINANCIEROS_CASILLA: Decimal("100.00")}


def test_manual_transaction_tax_fields_feed_renta_observation_without_invoice_catalogue() -> None:
    manual = _transaction(
        "manual-tax-fields",
        amount=Decimal("121.00"),
        category=SpendingCategory.from_registry("asesoria_fiscal"),
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((manual,)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    assert result.issues == ()
    assert result.observations[0].taxable_base == Decimal("100.00")
    assert result.observations[0].iva_amount == Decimal("21.00")
    assert result.observations[0].deductible_amount == Decimal("100.00")
    assert result.casilla_values == {_M100_ASESORIA_CASILLA: Decimal("100.00")}


def test_an_equipment_purchase_above_the_low_value_limit_is_not_deducted_whole() -> None:
    """DISCRIMINATING. A 2,000 EUR computer is amortized (LIS art. 12.1), not written off in its purchase year.

    Only a new item of up to 300 EUR may be written off at once (LIS art. 12.3.e).
    Without an asset-register entry the purchase deducts nothing and says why.
    """
    equipment = _transaction(
        "unscheduled-equipment-acquisition",
        amount=Decimal("2420.00"),
        category=SpendingCategory.from_registry("hardware_amortizable"),
        taxable_base=Decimal("2000.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("420.00"),
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((equipment,)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    assert result.observations == ()
    assert result.casilla_values == {}
    assert [issue.reason for issue in result.issues] == [RentaLedgerAggregationIssueReason.ASSET_REGISTER_REQUIRED]


def test_a_low_value_equipment_purchase_is_written_off_in_its_year() -> None:
    chair = _transaction(
        "low-value-chair",
        amount=Decimal("302.50"),
        category=SpendingCategory.from_registry("mobiliario_amortizable"),
        taxable_base=Decimal("250.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("52.50"),
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((chair,)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    assert result.issues == ()
    assert result.casilla_values == {validated_casilla_id("0208", surface="test"): Decimal("250.00")}


def test_low_value_write_offs_of_every_equipment_category_share_one_annual_limit() -> None:
    """DISCRIMINATING. LIS art. 12.3.e allows 25,000 EUR per period across all such items, not per row.

    Eighty-four items of 300 EUR, split over hardware and furniture, total 25,200 EUR:
    the latest write-off loses the 200 EUR above the limit.
    """
    rows = tuple(
        _transaction(
            f"low-value-{index:03d}",
            amount=Decimal("363.00"),
            category=SpendingCategory.from_registry(
                "hardware_amortizable" if index % 2 else "mobiliario_amortizable",
            ),
            booked_date=date(2025, 1 + index % 12, 1 + index // 12),
            value_date=date(2025, 1 + index % 12, 1 + index // 12),
            taxable_base=Decimal("300.00"),
            iva_rate=Decimal("0.21"),
            iva_amount=Decimal("63.00"),
        )
        for index in range(84)
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions(rows),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    assert result.issues == ()
    deducted = sum((observation.deductible_amount for observation in result.observations), Decimal("0"))
    assert deducted == Decimal("25000.00")
    latest = max(result.observations, key=lambda observation: (observation.filing_date, observation.transaction_id))
    assert latest.deductible_amount == Decimal("100.00")


@pytest.mark.parametrize("category_id", ["telefonia_movil", "vehiculo_combustible"])
def test_a_shared_use_line_or_vehicle_deducts_nothing_and_says_why(category_id: str) -> None:
    """DISCRIMINATING. A mobile line or a turismo is affected only by exclusive use (RIRPF art. 22).

    A MIXED row states private use, so its stated share is not deducted: the
    element admits no partial affectation, and the refusal is a review issue.
    """
    shared = _transaction(
        "shared-use",
        category=SpendingCategory.from_registry(category_id),
        business_classification=BusinessClassification.MIXED,
        business_pct=Decimal("0.50"),
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((shared,)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    assert result.observations == ()
    assert result.casilla_values == {}
    assert [issue.reason for issue in result.issues] == [RentaLedgerAggregationIssueReason.EXCLUSIVE_USE_REQUIRED]


@pytest.mark.parametrize("category_id", ["telefonia_movil", "vehiculo_combustible"])
def test_an_exclusively_business_line_or_vehicle_deducts_in_full(category_id: str) -> None:
    business = _transaction(
        "business-use",
        category=SpendingCategory.from_registry(category_id),
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((business,)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    assert result.issues == ()
    assert [observation.deductible_amount for observation in result.observations] == [Decimal("100.00")]


def test_an_annual_cap_holds_across_the_rows_of_the_year() -> None:
    """DISCRIMINATING. Two 300 EUR premiums are each under the 500 EUR limit, and together above it.

    LIRPF art. 30.2, regla 5.a a) allows 500 EUR a year for the insured person,
    so the second premium deducts only the 200 EUR the first left.
    """
    premiums = tuple(
        _transaction(
            f"premium-{month}",
            amount=Decimal("300.00"),
            category=SpendingCategory.from_registry("seguros_salud_autonomo"),
            booked_date=date(2025, month, 1),
            value_date=date(2025, month, 1),
        )
        for month in (3, 9)
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions(premiums),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    assert result.issues == ()
    by_date = sorted(result.observations, key=lambda observation: observation.filing_date)
    assert [observation.deductible_amount for observation in by_date] == [Decimal("300.00"), Decimal("200.00")]


def test_linked_invoice_issue_date_controls_period_filtering() -> None:
    initial = _transaction("row-outside")
    invoice = _invoice(initial.transaction_id, issued_at=date(2024, 12, 31))
    linked = _transaction("row-outside", purchase_invoice_evidence_id=invoice.invoice_id)

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((linked,)),
        build_invoice_catalogue((invoice,)),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
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
        build_invoice_catalogue((invoice,)),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
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
        build_invoice_catalogue((invoice,)),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
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
        build_invoice_catalogue((invoice,)),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    assert result.issues == ()
    assert result.observations[0].direction is RentaExpenseDirection.REFUND
    assert result.casilla_values == {_M100_ASESORIA_CASILLA: -invoice.base_total}


def test_transaction_only_renta_expense_buckets_on_value_date_caja_basis() -> None:
    """Document the CAJA-only basis for a transaction-only (un-invoiced) expense.

    For a Renta expense with no linked invoice, the first-slice ``filing_date``
    falls back to ``operation_date`` = ``value_date or booked_date`` — a CASH
    (caja) basis. There is no accrual/devengo basis selector.

    This pins the current behaviour as the regression anchor for a future
    devengo addition: the row whose VALUE_DATE lands in the tax year is
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
        category=SpendingCategory.from_registry("gastos_bancarios"),
        booked_date=date(2024, 12, 31),
        value_date=date(2025, 1, 2),
        purchase_invoice_evidence_id=None,
    )
    # value_date in the prior year (caja), booked_date in-year (devengo would include).
    caja_out_of_year = _transaction(
        "row-caja-out-of-year",
        amount=Decimal("100.00"),
        category=SpendingCategory.from_registry("gastos_bancarios"),
        booked_date=date(2025, 1, 2),
        value_date=date(2024, 12, 31),
        purchase_invoice_evidence_id=None,
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((caja_in_year, caja_out_of_year)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    # Caja basis: only the row whose VALUE_DATE is in-year is aggregated, and the
    # observation's filing_date is that value_date (operation_date fallback).
    assert [observation.transaction_id for observation in result.observations] == [caja_in_year.transaction_id]
    assert result.observations[0].filing_date == date(2025, 1, 2)
    assert result.casilla_values == {_M100_GASTOS_FINANCIEROS_CASILLA: Decimal("100.00")}
    # The mirror row is excluded keyed on value_date — a devengo basis
    # (booked_date 2025-01-02) would instead have INCLUDED it.
    assert [issue.transaction_id for issue in result.issues] == [caja_out_of_year.transaction_id]
    assert result.issues[0].reason is RentaLedgerAggregationIssueReason.OUTSIDE_PERIOD
    assert "2024-12-31" in result.issues[0].detail


def test_non_eur_transaction_is_reported_as_issue_before_fact_creation() -> None:
    usd_expense = _transaction(
        "row-usd",
        category=SpendingCategory.from_registry("gastos_bancarios"),
        purchase_invoice_evidence_id=None,
        currency="USD",
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((usd_expense,)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    assert result.observations == ()
    assert result.issues[0].reason is RentaLedgerAggregationIssueReason.UNSUPPORTED_CURRENCY


def test_zero_business_amount_is_reported_as_invalid_fact_issue() -> None:
    zero_business = _transaction(
        "row-zero-business",
        amount=Decimal("200.00"),
        category=SpendingCategory.from_registry("gastos_bancarios"),
        business_classification=BusinessClassification.MIXED,
        business_pct=Decimal("0"),
        purchase_invoice_evidence_id=None,
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((zero_business,)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
    )

    assert result.observations == ()
    assert result.issues[0].reason is RentaLedgerAggregationIssueReason.INVALID_LEDGER_FACT


# ---------------------------------------------------------------------------
# Territorial-regime region-scoped deductibility (region-Renta D1/D2/D4)
# ---------------------------------------------------------------------------


def _region_override_profile(category: SpendingCategory) -> CategoryProfile:
    """A SYNTHETIC per-comunidad override profile for wiring tests only.

    Fixed 50% deductibility, distinct from the GASTOS_BANCARIOS state profile
    (full deductible), so a selection is observable. This is a test double for
    the SELECTION MECHANISM, never a real territorial-regime figure.
    """
    return CategoryProfile(
        category=category,
        display_label=tr("Override territorial de prueba"),
        proportionality=ProportionalityRule(
            kind=require_proportionality_kind("fixed_percentage"),
            fixed_pct=Decimal("0.50"),
            citations=(
                CategoryCitation(
                    source=CategoryCitationSource.MANUAL_RENTA,
                    reference="Manual práctico Renta 2025, regla de prueba territorial",
                    locator="test",
                    url=parse_http_url(RENTA_REGIMEN_CITATION_URL_FIXTURE),
                    quote=tr("Texto de prueba para override territorial."),
                    source_ref="aeat-renta-2025-manual-parte1",
                    valid_from=date(2025, 1, 1),
                    valid_to=date(2025, 12, 31),
                ),
            ),
            notes=tr("Override territorial de prueba."),
        ),
    )


def test_non_regional_category_profile_preserves_result_across_region() -> None:
    """With the empty override layer, the residence CCAA is inert.

    A category with no territorial-regime override produces byte-identical
    observations whether the residence comunidad is declared or not.
    """
    row = _transaction(
        "row-region-inert", amount=Decimal("100.00"), category=SpendingCategory.from_registry("gastos_bancarios")
    )
    catalogue = TransactionCatalogue.from_transactions((row,))

    without_region = aggregate_renta_ledger_expenses(
        catalogue, InvoiceCatalogue(), bucket_id=SECURE_OBJECTS_BUCKET_ID, period=_ANNUAL_2025, profile_year=2025
    )
    with_region = aggregate_renta_ledger_expenses(
        catalogue,
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
        residence_ccaa=CCAA.MADRID,
    )

    assert with_region.observations == without_region.observations
    assert with_region.casilla_values == without_region.casilla_values
    assert with_region.issues == without_region.issues == ()


def test_region_override_selected_when_residence_matches() -> None:
    """A declared residence with a territorial override selects the override.

    The synthetic 50% override for the residence comunidad halves the deductible
    versus the full-deductible state profile, proving selection by CCAA.
    """
    row = _transaction(
        "row-region-hit", amount=Decimal("100.00"), category=SpendingCategory.from_registry("gastos_bancarios")
    )
    overrides = {
        CCAA.CANARIAS: {
            SpendingCategory.from_registry("gastos_bancarios"): _region_override_profile(
                SpendingCategory.from_registry("gastos_bancarios")
            )
        }
    }

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((row,)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
        residence_ccaa=CCAA.CANARIAS,
        region_category_overrides=overrides,
    )

    assert result.issues == ()
    assert result.observations[0].proportionality_kind == require_proportionality_kind("fixed_percentage")
    assert result.observations[0].deductible_amount == Decimal("50.0000")


def test_region_override_undeclared_residence_fails_closed() -> None:
    """A category carrying an override with no declared residence fails closed."""
    row = _transaction(
        "row-region-undeclared", amount=Decimal("100.00"), category=SpendingCategory.from_registry("gastos_bancarios")
    )
    overrides = {
        CCAA.CANARIAS: {
            SpendingCategory.from_registry("gastos_bancarios"): _region_override_profile(
                SpendingCategory.from_registry("gastos_bancarios")
            )
        }
    }

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((row,)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
        residence_ccaa=None,
        region_category_overrides=overrides,
    )

    assert result.observations == ()
    assert result.issues[0].reason is RentaLedgerAggregationIssueReason.REGION_UNDECLARED_FOR_OVERRIDE


# ---------------------------------------------------------------------------
# Residence CCAA derived from the active profile at the repository boundary.
# ---------------------------------------------------------------------------


def _profile_with_ccaa(ccaa_value: str | None) -> UserProfileRecord:
    """A user profile carrying an optional ``tax_residence.ccaa`` fact."""
    facts = (UserProfileFact(path="identity.tax_id", value="X1234567L"),)
    if ccaa_value is not None:
        facts = (*facts, UserProfileFact(path="tax_residence.ccaa", value=ccaa_value))
    return _create_profile_record_for_test(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="11111111-1111-4111-8111-111111111111",
        facts=facts,
        context=_profile_creation_context_for_test(),
    )


# ---------------------------------------------------------------------------
# One proportion, one application: the category rule applies the usage ratio, and
# a row's business share (the degree of use, which feeds IVA) never scales it again.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "classification",
    [BusinessClassification.BUSINESS, BusinessClassification.MIXED],
    ids=["business", "mixed"],
)
def test_home_office_utility_bill_deducts_the_statutory_share_once(
    classification: BusinessClassification,
    operation: PinnedAuthorityOperation,
) -> None:
    """LIRPF art. 30.2.5.b: 30 per cent of office m2 over total m2, applied one time.

    Expected figure, worked by hand: 20 / 100 = 0.20; 0.30 * 0.20 = 0.06; the bill
    is a 100.00 EUR base, so 100.00 * 0.06 = 6.00. The row's stored share is the
    degree of use, 0.20, which IVA deducts; the category's usage ratio is 0.06.
    Both come out of the real resolvers for the same profile. Applying the share
    as well would give 1.20, not 6.00, which is the double application this
    guards against.
    """
    category = SpendingCategory.from_registry("suministros_home_office_luz")
    profile = dwelling_profile()
    usage_ratios = dwelling_usage_ratios(profile, bucket_id=SECURE_OBJECTS_BUCKET_ID, operation=operation)
    stamped_share = dwelling_classify_share(profile, category, operation=operation)
    assert usage_ratios[category] == HOME_OFFICE_SUMINISTRO_RATIO
    assert stamped_share == HOME_OFFICE_DEGREE_OF_USE

    bill = _transaction(
        "home-office-luz",
        amount=Decimal("121.00"),
        category=category,
        business_classification=classification,
        business_pct=stamped_share if classification is BusinessClassification.MIXED else None,
        usage_ratio_id=category.value if classification is BusinessClassification.MIXED else None,
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((bill,)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
        usage_ratios=usage_ratios,
        profile_record=profile,
        operation=operation,
    )

    assert result.issues == ()
    deducted = result.observations[0].deductible_amount
    assert deducted == Decimal("6.00"), f"{classification.value} home-office bill deducted {deducted}, expected 6.00"
    assert sum(result.casilla_values.values()) == Decimal("6.00")


def test_a_40_of_100_m2_home_office_bill_deducts_12_per_cent_in_renta_though_its_row_share_is_40(
    operation: PinnedAuthorityOperation,
) -> None:
    """The Manual de Renta 2025 example: 30% x 40% = 12% of the base, here 12.00 of 100.00.

    The row's stamped share is the 0.40 degree of use, which IVA deducts. Renta
    must not read it: the IRPF factor reaches the base only through the category
    rule over the usage-ratio store.
    """
    category = SpendingCategory.from_registry("suministros_home_office_luz")
    profile = dwelling_profile(office_m2=Decimal("40"))
    usage_ratios = dwelling_usage_ratios(profile, bucket_id=SECURE_OBJECTS_BUCKET_ID, operation=operation)
    stamped_share = dwelling_classify_share(profile, category, operation=operation)
    assert usage_ratios[category] == Decimal("0.12")
    assert stamped_share == Decimal("0.40")
    bill = _transaction(
        "home-office-luz-40",
        amount=Decimal("121.00"),
        category=category,
        business_classification=BusinessClassification.MIXED,
        business_pct=stamped_share,
        usage_ratio_id=category.value,
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((bill,)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
        usage_ratios=usage_ratios,
        profile_record=profile,
        operation=operation,
    )

    assert result.issues == ()
    assert result.observations[0].deductible_amount == Decimal("12.00")


@pytest.mark.parametrize(
    "classification",
    [BusinessClassification.BUSINESS, BusinessClassification.MIXED],
    ids=["business", "mixed"],
)
def test_operator_usage_ratio_on_a_dwelling_lease_applies_once(
    classification: BusinessClassification,
    operation: PinnedAuthorityOperation,
) -> None:
    """A stored 25 per cent dwelling-lease ratio deducts 25.00 of a 100.00 base, not 6.25."""
    category = SpendingCategory.from_registry("arrendamiento_vivienda_afecto")
    bill = _transaction(
        "lease-bill",
        amount=Decimal("121.00"),
        category=category,
        business_classification=classification,
        business_pct=Decimal("0.25") if classification is BusinessClassification.MIXED else None,
        usage_ratio_id=category.value if classification is BusinessClassification.MIXED else None,
        taxable_base=Decimal("100.00"),
        iva_rate=Decimal("0.21"),
        iva_amount=Decimal("21.00"),
    )

    result = aggregate_renta_ledger_expenses(
        TransactionCatalogue.from_transactions((bill,)),
        InvoiceCatalogue(),
        bucket_id=SECURE_OBJECTS_BUCKET_ID,
        period=_ANNUAL_2025,
        profile_year=2025,
        usage_ratios={category: Decimal("0.25")},
        operation=operation,
    )

    assert result.issues == ()
    deducted = result.observations[0].deductible_amount
    assert deducted == Decimal("25.00"), f"{classification.value} lease deducted {deducted}, expected 25.00"
