"""What a foreign-currency movement or invoice contributes is stated in EUR, or stays unresolved.

Every figure is arithmetic worked out here. The USD invoice states a 1.000,00 base,
210,00 of IVA at 21 % and 150,00 of retención at 15 %, so 1.060,00 is left to be paid.
At the stamped 0,50 that is a 500,00 base, 105,00 of IVA, 75,00 of retención and 530,00
to be paid. Rates and rows are round synthetic values.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.aggregation import LedgerWithholdingDerivation
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.categories.registry import resolve_category_profiles
from ....domain.categories.spending_category import SpendingCategory
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.invoices.enums import IvaRate, PaymentStatus
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.schema import InvoiceKind, IvaCategory
from ....domain.renta.ledger_expenses import RentaDeductibilityContext, RentaDeductibleExpenseObservation
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.transactions.service import link_invoice
from ....domain.user_profile.values import UserProfileFact
from ...actividad_asset.tests.register_support import MemoryRepository
from ...modelo.work_profile import ModeloWorkProfile
from ..activity_asset_ledger_reconciliation import possibly_durable_expense_findings
from ..modelo_bindings import LedgerRentaIncomeAggregationSourceResolver
from ..modelo_bindings_renta_expenses import accrual_coverage_gap
from ..renta_imputation import ImputationCriteria, ImputationFilingHistory
from ..renta_income_diagnostics import rectification_diagnostics
from ..renta_income_evidence import income_withheld_amount
from ..renta_ledger_classification import classify_renta_transaction
from ..renta_ledger_models import RentaLedgerAggregationIssue, RentaLedgerAggregationIssueReason
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution
from .ledger_source_mesh_support import BUCKET_ID, InMemoryTransactionCatalogueRepository, cash_criterion_profile
from .renta_income_aggregation_support import catalogue_read_ports, renta_income_aggregation_period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_YEAR = newest_authored_edition("100")
_ON = date(_YEAR, 3, 10)
_M100_INCOME = "renta-ledger-income-0171"
_M100_CREDIT = "renta-ledger-actividad-retenciones-0599"


def _row(
    cash: str,
    *,
    currency: str = "USD",
    eur: str | None = None,
    base: str | None = None,
    iva: str | None = None,
    direction: TransactionDirection = TransactionDirection.INCOMING,
    provider_id: str = "fila",
    on: date = _ON,
    description: str = "cobro factura",
    **facts: object,
) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=on,
        value_date=on,
        amount=Decimal(cash),
        currency=currency,
        counterparty="Cliente SL",
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(_YEAR, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={},
    )
    conversion = (
        {}
        if eur is None
        else {"fx_rate": Decimal(eur) / Decimal(cash), "value_in_eur": Decimal(eur), "rate_source": "ECB"}
    )
    tax = {} if base is None or iva is None else {"taxable_base": Decimal(base), "iva_amount": Decimal(iva)}
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": direction,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "irpf_category": "actividad_economica" if direction is TransactionDirection.INCOMING else None,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(_YEAR, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
            **conversion,
            **tax,
            **facts,
        },
    )


def _invoice(
    *rows: Transaction,
    currency: str = "USD",
    fx_rate: str | None = "0.50",
    kind: InvoiceKind = InvoiceKind.ISSUED,
    retention: bool = True,
    issued_at: date = _ON,
) -> Invoice:
    line = InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=Decimal("1000.00"),
        subtotal=Decimal("1000.00"),
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=Decimal("210.00"),
    )
    stamp = {} if fx_rate is None else {"fx_rate": Decimal(fx_rate), "fx_rate_date": issued_at, "fx_rate_source": "ECB"}
    withheld = {"retention_rate": Decimal("0.15"), "retention_amount": Decimal("150.00")} if retention else {}
    return Invoice.model_validate(
        {
            "kind": kind,
            "invoice_number": "F-001",
            "issued_at": issued_at,
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B00015016",
            "counterparty_country": "ES",
            "bucket_id": BUCKET_ID,
            "base_total": Decimal("1000.00"),
            "iva_total": Decimal("210.00"),
            "grand_total": Decimal("1210.00"),
            "currency": currency,
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "iva_category": IvaCategory("domestic_general"),
            "linked_transaction_ids": tuple(row.transaction_id for row in rows),
            **stamp,
            **withheld,
        },
    )


def _accrual_profile() -> ModeloWorkProfile:
    cash = cash_criterion_profile(_YEAR)
    facts = tuple(
        UserProfileFact.model_validate(
            {"path": fact.path, "value": "devengo", "valid_from": fact.valid_from, "valid_to": fact.valid_to}
        )
        if fact.path == "irpf.activity_income_imputation_criterion"
        else fact
        for fact in cash.record.facts
    )
    return replace(cash, record=cash.record.model_copy(update={"facts": facts}))


def _m100(
    rows: tuple[Transaction, ...] = (),
    invoice: Invoice | None = None,
    *,
    profile: ModeloWorkProfile | None = None,
) -> CalculationSourceResolution:
    transactions = TransactionCatalogue.from_transactions(rows)
    invoices: InvoiceCatalogue = build_invoice_catalogue(() if invoice is None else (invoice,))
    if invoice is not None:
        for row in rows:
            transactions = link_invoice(transactions, row.transaction_id, invoice.invoice_id)
    repository = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    repository.save(transactions)
    return LedgerRentaIncomeAggregationSourceResolver(
        activity_asset_history_repository=MemoryRepository(),
        transaction_repository=repository,
        ports=catalogue_read_ports(invoices=invoices, transactions=transactions),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="100",
            filing_year=_YEAR,
            period=renta_income_aggregation_period(_YEAR, "0A"),
            revision=published_snapshot("100", filing_year=_YEAR, period="0A").revision,
            profile=cash_criterion_profile(_YEAR) if profile is None else profile,
        ),
    )


def _messages(resolution: CalculationSourceResolution) -> str:
    return " | ".join(str(diagnostic.message) for diagnostic in resolution.diagnostics)


def test_inferred_retencion_on_a_converted_row_is_a_eur_figure() -> None:
    """USD 1.000,00 + 210,00 paid as 1.060,00 at 0,50: 75,00 EUR short, not 150,00."""
    row = _row("1060.00", eur="530.00", base="1000.00", iva="210.00")

    inference = income_withheld_amount(row)

    assert inference.amount == Decimal("75.00")
    assert inference.derivation is LedgerWithholdingDerivation.INFERRED_FROM_DECLARED_CUOTA


def test_the_rate_advisory_reads_eur_over_eur_and_the_credit_stays_out() -> None:
    """75,00 on a 500,00 base is the 15 % professional rate; the native 150,00 read as 30 % and raised a false finding."""
    resolution = _m100((_row("1060.00", eur="530.00", base="1000.00", iva="210.00"),))
    reasons = {diagnostic.reason for diagnostic in resolution.diagnostics}

    assert resolution.binding_values[_M100_CREDIT] == Decimal("0")
    assert "inferred_retencion_rate_unmatched" not in reasons
    assert "75.00 EUR" in _messages(resolution)


def test_rounding_of_a_converted_gross_is_no_retencion() -> None:
    """80,00 + 20,00 is paid whole; 100,00 at 0,87604 stores 87,60 against 87,604, and that gap withholds nothing."""
    row = _row("100.00", eur="87.60", base="80.00", iva="20.00").model_copy(update={"fx_rate": Decimal("0.87604")})

    inference = income_withheld_amount(row)

    assert inference.amount == Decimal("0")
    assert inference.derivation is LedgerWithholdingDerivation.NONE_WITHHELD


def test_an_unconverted_row_infers_nothing_and_stays_unresolved() -> None:
    inference = income_withheld_amount(_row("1060.00", base="1000.00", iva="210.00"))

    assert inference.amount == Decimal("0")
    assert inference.derivation is LedgerWithholdingDerivation.NO_SUBSTRATE


def _rectification(invoice: Invoice, row: Transaction, profile: ModeloWorkProfile) -> str:
    transactions = link_invoice(TransactionCatalogue.from_transactions((row,)), row.transaction_id, invoice.invoice_id)
    findings = rectification_diagnostics(
        transactions,
        build_invoice_catalogue((invoice,)),
        bucket_id=BUCKET_ID,
        year=_YEAR,
        criteria=ImputationCriteria(
            facts=tuple(profile.record.facts),
            filings=ImputationFilingHistory(filed_on={_YEAR: date(_YEAR, 3, 31)}),
        ),
        resolver_id="prueba",
    )
    assert len(findings) == 1
    return str(findings[0].message)


def test_a_late_foreign_retencion_is_named_at_its_eur_figure() -> None:
    """The whole USD invoice is settled after filing: 75,00 EUR, never 150,00 EUR."""
    row = _row("1060.00", eur="530.00", on=date(_YEAR, 7, 1))

    message = _rectification(_invoice(row), row, _accrual_profile())

    assert "75.00 EUR of retencion" in message


def test_a_late_foreign_part_payment_names_its_share_in_eur() -> None:
    """Half of the USD invoice is paid after filing: 37,50 EUR."""
    row = _row("530.00", eur="265.00", on=date(_YEAR, 7, 1))

    message = _rectification(_invoice(row), row, _accrual_profile())

    assert "37.50 EUR of retencion" in message


def test_a_late_retencion_with_no_eur_value_names_its_own_currency() -> None:
    row = _row("1060.00", eur="530.00", on=date(_YEAR, 7, 1))

    message = _rectification(_invoice(row, fx_rate=None), row, _accrual_profile())

    assert "150.00 USD" in message
    assert "with no EUR value" in message
    assert "150.00 EUR" not in message


def test_a_part_payment_in_the_invoice_currency_shares_out_its_eur_figures() -> None:
    """USD 530,00 of 1.060,00 is half: 250,00 of the 500,00 base and 37,50 of retención, out of the credit."""
    row = _row("530.00", eur="290.00")

    resolution = _m100((row,), _invoice(row))

    assert resolution.binding_values[_M100_INCOME] == Decimal("250.00")
    assert resolution.binding_values[_M100_CREDIT] == Decimal("0")
    assert "37.50 EUR" in _messages(resolution)


def test_a_euro_part_payment_of_a_foreign_invoice_shares_by_eur_value() -> None:
    """EUR 265,00 of the 530,00 EUR left to be paid is also half."""
    row = _row("265.00", currency="EUR")

    assert _m100((row,), _invoice(row)).binding_values[_M100_INCOME] == Decimal("250.00")


def test_two_foreign_part_payments_declare_the_whole_eur_base() -> None:
    first = _row("530.00", eur="290.00", provider_id="cobro-1")
    second = _row("530.00", eur="280.00", provider_id="cobro-2")

    resolution = _m100((first, second), _invoice(first, second))

    assert resolution.binding_values[_M100_INCOME] == Decimal("500.00")


def test_a_part_payment_of_an_unrated_invoice_declares_only_the_cash_with_a_finding() -> None:
    """No rate means no EUR figure to share out, so the movement's own 290,00 EUR stands."""
    row = _row("530.00", eur="290.00")

    resolution = _m100((row,), _invoice(row, fx_rate=None))

    assert resolution.binding_values[_M100_INCOME] == Decimal("290.00")
    assert "unusable_sales_invoice_evidence" in {diagnostic.reason for diagnostic in resolution.diagnostics}


def test_under_accrual_a_part_paid_foreign_invoice_counts_wholly_in_eur() -> None:
    """The 250,00 share and the 250,00 left unpaid are the invoice's whole 500,00 EUR base."""
    row = _row("530.00", eur="290.00")

    resolution = _m100((row,), _invoice(row), profile=_accrual_profile())

    assert resolution.binding_values[_M100_INCOME] == Decimal("500.00")


def test_under_accrual_an_unpaid_foreign_invoice_counts_in_eur() -> None:
    resolution = _m100((), _invoice(), profile=_accrual_profile())

    assert resolution.binding_values[_M100_INCOME] == Decimal("500.00")


def test_under_accrual_an_unrated_unpaid_invoice_stays_unresolved() -> None:
    """Silence would read as an income box complete at zero; the box is held until the rate is stamped."""
    resolution = _m100((), _invoice(fx_rate=None), profile=_accrual_profile())

    assert resolution.binding_values[_M100_INCOME] == Decimal("0")
    assert "unresolved_binding" in {diagnostic.reason for diagnostic in resolution.diagnostics}
    assert "eur_value_unknown" in _messages(resolution)


def test_under_accrual_an_unrated_invoice_its_receipt_settles_is_not_held() -> None:
    row = _row("1060.00", eur="636.00")

    resolution = _m100((row,), _invoice(row, fx_rate=None), profile=_accrual_profile())

    assert resolution.binding_values[_M100_INCOME] == Decimal("636.00")
    assert "eur_value_unknown" not in _messages(resolution)


def _expense(row: Transaction, invoice: Invoice, operation: PinnedAuthorityOperation) -> object:
    linked = Transaction.model_validate(
        {
            **{name: getattr(row, name) for name in type(row).model_fields if name != "transaction_id"},
            "purchase_invoice_evidence_id": invoice.invoice_id,
        }
    )
    return classify_renta_transaction(
        linked,
        invoices=build_invoice_catalogue((invoice,)),
        bucket_id=BUCKET_ID,
        resolved_period=Period.from_year_and_code(_YEAR, "0A"),
        resolved_profile_year=_YEAR,
        profiles=resolve_category_profiles(_YEAR, operation=operation),
        region_overrides={},
        context=RentaDeductibilityContext(profile_year=_YEAR),
        activity_key="activity-1",
    )


def _payment(cash: str, *, currency: str = "EUR", eur: str | None = None) -> Transaction:
    return _row(
        cash,
        currency=currency,
        eur=eur,
        direction=TransactionDirection.OUTGOING,
        category_id=SpendingCategory.from_registry("cuotas_autonomos_ss").value,
    )


@pytest.mark.parametrize(
    ("cash", "grounded"),
    [
        pytest.param("1210.01", True, id="one-cent-over"),
        pytest.param("1209.99", True, id="one-cent-under"),
        pytest.param("1210.02", False, id="two-cents-over"),
        pytest.param("1209.98", False, id="two-cents-under"),
    ],
)
def test_an_expense_settles_within_the_link_tolerance(
    cash: str, grounded: bool, operation: PinnedAuthorityOperation
) -> None:
    """A cent's rounding on a payment no longer costs the expense its deduction; two cents still does."""
    row = _payment(cash)
    invoice = _invoice(row, currency="EUR", fx_rate=None, kind=InvoiceKind.RECEIVED, retention=False)

    result = _expense(row, invoice, operation)

    if grounded:
        assert isinstance(result, RentaDeductibleExpenseObservation), result
        assert result.taxable_base == Decimal("1000.00")
    else:
        assert isinstance(result, RentaLedgerAggregationIssue)
        assert result.reason is RentaLedgerAggregationIssueReason.AMOUNT_MISMATCH


def test_an_expense_paid_in_the_invoice_currency_at_another_rate_is_grounded(
    operation: PinnedAuthorityOperation,
) -> None:
    """USD 1.210,00 pays USD 1.210,00 whatever each rate says; the base is the invoice's 500,00 EUR."""
    row = _payment("1210.00", currency="USD", eur="665.50")
    invoice = _invoice(row, kind=InvoiceKind.RECEIVED, retention=False)

    result = _expense(row, invoice, operation)

    assert isinstance(result, RentaDeductibleExpenseObservation), result
    assert result.taxable_base == Decimal("500.00")
    assert result.iva_amount == Decimal("105.00")


def test_an_expense_with_retencion_settles_at_what_it_leaves_to_be_paid(operation: PinnedAuthorityOperation) -> None:
    """The payer keeps the retención, so 1.060,00 pays it and 1.210,00 does not."""
    net = _payment("1060.00")
    gross = _payment("1210.00")

    grounded = _expense(net, _invoice(net, currency="EUR", fx_rate=None, kind=InvoiceKind.RECEIVED), operation)
    refused = _expense(gross, _invoice(gross, currency="EUR", fx_rate=None, kind=InvoiceKind.RECEIVED), operation)

    assert isinstance(grounded, RentaDeductibleExpenseObservation), grounded
    assert isinstance(refused, RentaLedgerAggregationIssue)


def test_an_expense_on_an_invoice_with_no_eur_value_is_refused_by_name(operation: PinnedAuthorityOperation) -> None:
    row = _payment("1210.00", currency="USD", eur="605.00")

    result = _expense(row, _invoice(row, fx_rate=None, kind=InvoiceKind.RECEIVED, retention=False), operation)

    assert isinstance(result, RentaLedgerAggregationIssue)
    assert result.reason is RentaLedgerAggregationIssueReason.AMOUNT_MISMATCH
    assert "no EUR value" in result.detail


def _received(*, currency: str = "USD", fx_rate: str | None = "0.50") -> Invoice:
    return _invoice(currency=currency, fx_rate=fx_rate, kind=InvoiceKind.RECEIVED, retention=False)


def test_a_euro_row_covers_a_foreign_invoice_by_its_eur_base() -> None:
    """EUR 500,00 of base is the whole USD 1.000,00 at 0,50, not half of it."""
    row = _row("605.00", currency="EUR", base="500.00", iva="105.00", direction=TransactionDirection.OUTGOING)

    assert accrual_coverage_gap(_received(), (row,)) is None


def test_a_foreign_row_does_not_cover_a_euro_invoice_digit_for_digit() -> None:
    """USD 1.000,00 of base at 0,50 is 500,00 EUR of a 1.000,00 EUR base: half is still unclassified."""
    row = _row("1210.00", eur="605.00", base="1000.00", iva="210.00", direction=TransactionDirection.OUTGOING)

    gap = accrual_coverage_gap(_received(currency="EUR", fx_rate=None), (row,))

    assert gap is not None
    assert "accrues 1000.00" in gap
    assert "state 500.00" in gap


def test_rows_with_no_eur_value_leave_the_coverage_unknown() -> None:
    row = _row("1210.00", base="1000.00", iva="210.00", direction=TransactionDirection.OUTGOING)

    gap = accrual_coverage_gap(_received(currency="EUR", fx_rate=None), (row,))

    assert gap is not None
    assert "not known" in gap


def test_the_durable_expense_question_quotes_the_row_in_eur() -> None:
    """The note prints this figure as money, so USD 200,00 worth 100,00 EUR reads 100,00."""
    row = _row(
        "200.00",
        eur="100.00",
        direction=TransactionDirection.OUTGOING,
        description="Monitor Dell",
        category_id="material_oficina",
    )
    ledger = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    ledger.save(TransactionCatalogue.from_transactions((row,)))

    findings = possibly_durable_expense_findings(
        (row.transaction_id,),
        revisions=(),
        ledger=ledger,
        invoices=catalogue_read_ports(invoices=InvoiceCatalogue(), transactions=TransactionCatalogue()).invoice_reader,
        tax_year=_YEAR,
        source_kind="ledger_renta_gastos_estimacion_directa_aggregation",
        resolver_id="ledger_renta_gastos_estimacion_directa_aggregation",
    )

    assert len(findings) == 1
    assert findings[0].fact is not None
    assert "100.00" in str(findings[0].fact.model_dump())
    assert "200.00" not in str(findings[0].fact.model_dump())
