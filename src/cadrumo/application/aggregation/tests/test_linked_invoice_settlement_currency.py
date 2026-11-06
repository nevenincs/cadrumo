"""A movement settles its linked sales invoice only for what it is worth in a common currency.

``ledger.link`` takes whatever pair a person gives it, so the read decides what the
link proves. A USD movement of 1.060,00 worth 530,00 EUR once matched a 1.060,00 EUR
net invoice digit for digit and put the invoice's whole 1.000,00 base into casillas
0171 and 01, with no finding.

Every figure is invoice arithmetic worked out here, not an engine output. The invoice
states a 1.000,00 base, 210,00 of IVA at 21 % and 150,00 of retención at 15 %, so
1.210,00 less 150,00 leaves 1.060,00 to be paid. A share of that is the receipt's EUR
value over 1.060,00. The rates are round synthetic multipliers, stated beside each case.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition
from cadrumo.domain.calculations.registry.tests.published_authority import published_snapshot
from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.invoices.catalogue import InvoiceCatalogue
from ....domain.invoices.enums import IvaRate, PaymentStatus, resolve_invoice_legal_mention
from ....domain.invoices.models import Invoice, InvoiceLine
from ....domain.iva.schema import InvoiceKind, IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.transactions.service import link_invoice
from ...actividad_asset.tests.register_support import MemoryRepository
from ...invoices.source_observations import M347Filer, invoice_observation
from ..modelo_bindings import LedgerRentaIncomeAggregationSourceResolver
from ..renta_income_evidence import (
    SalesInvoiceEvidencePayload,
    SalesInvoiceEvidenceRefusal,
    sales_invoice_evidence_payload,
)
from ..source_mesh import CalculationSourceContext, CalculationSourceResolution
from .ledger_source_mesh_support import InMemoryTransactionCatalogueRepository, cash_criterion_profile
from .renta_income_aggregation_support import catalogue_read_ports, renta_income_aggregation_period

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET = "d5a2b3c4-6e7f-4a81-9b02-c3d4e5f60718"
_YEAR = newest_authored_edition("100")
_ON = date(_YEAR, 3, 10)
_M100_INCOME = "renta-ledger-income-0171"
_M100_CREDIT = "renta-ledger-actividad-retenciones-0599"
_M130_INCOME = "modelo-130-actividad-economica-ingresos-cumulative"
_M130_CREDIT = "modelo-130-actividad-economica-retenciones-cumulative"


def _movement(
    cash: str,
    *,
    currency: str = "USD",
    eur: str | None = None,
    provider_id: str = "cobro",
) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=_ON,
        value_date=_ON,
        amount=Decimal(cash),
        currency=currency,
        counterparty="Cliente SL",
        description="cobro factura",
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
        else {
            "fx_rate": Decimal(eur) / Decimal(cash),
            "value_in_eur": Decimal(eur),
            "rate_source": "ECB",
            "rate_date": _ON.isoformat(),
        }
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "irpf_category": "actividad_economica",
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(_YEAR, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
            **conversion,
        },
    )


def _invoice(
    *receipts: Transaction,
    currency: str = "EUR",
    fx_rate: str | None = None,
    legal_mentions: tuple[str, ...] = (),
) -> Invoice:
    line = InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=Decimal("1000.00"),
        subtotal=Decimal("1000.00"),
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=Decimal("210.00"),
    )
    stamp = (
        {}
        if fx_rate is None
        else {
            "fx_rate": Decimal(fx_rate),
            "fx_rate_date": _ON,
            "fx_rate_source": "ECB",
            "fx_rate_observation_date": _ON,
        }
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": "F-001",
            "issued_at": _ON,
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B00015016",
            "counterparty_country": "ES",
            "bucket_id": _BUCKET,
            "base_total": Decimal("1000.00"),
            "iva_total": Decimal("210.00"),
            "grand_total": Decimal("1210.00"),
            "currency": currency,
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "iva_category": IvaCategory("domestic_general"),
            "retention_rate": Decimal("0.15"),
            "retention_amount": Decimal("150.00"),
            "linked_transaction_ids": tuple(receipt.transaction_id for receipt in receipts),
            "legal_mentions": legal_mentions,
            **stamp,
        },
    )


def _linked(invoice: Invoice, *receipts: Transaction) -> tuple[TransactionCatalogue, InvoiceCatalogue]:
    catalogue = TransactionCatalogue.from_transactions(receipts)
    for receipt in receipts:
        catalogue = link_invoice(catalogue, receipt.transaction_id, invoice.invoice_id)
    return catalogue, build_invoice_catalogue((invoice,))


def _evidence(
    invoice: Invoice, movement: Transaction
) -> tuple[SalesInvoiceEvidencePayload, SalesInvoiceEvidenceRefusal | None]:
    transactions, invoices = _linked(invoice, movement)
    linked = transactions.get(movement.transaction_id)
    assert linked is not None
    return sales_invoice_evidence_payload(invoices=invoices, bucket_id=_BUCKET, transaction=linked)


def _resolve(
    transactions: TransactionCatalogue,
    invoices: InvoiceCatalogue,
    *,
    revision: ModeloRevision,
    modelo: str,
    period_code: str,
) -> CalculationSourceResolution:
    repository = InMemoryTransactionCatalogueRepository(bucket_id=_BUCKET)
    repository.save(transactions)
    resolver = LedgerRentaIncomeAggregationSourceResolver(
        activity_asset_history_repository=MemoryRepository(),
        transaction_repository=repository,
        ports=catalogue_read_ports(invoices=invoices, transactions=transactions),
    )
    return resolver.resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET,
            modelo=modelo,
            filing_year=_YEAR,
            period=renta_income_aggregation_period(_YEAR, period_code),
            revision=revision,
            profile=cash_criterion_profile(_YEAR),
        ),
    )


def _m100(transactions: TransactionCatalogue, invoices: InvoiceCatalogue) -> CalculationSourceResolution:
    revision = published_snapshot("100", filing_year=_YEAR, period="0A").revision
    return _resolve(transactions, invoices, revision=revision, modelo="100", period_code="0A")


def _m130(transactions: TransactionCatalogue, invoices: InvoiceCatalogue) -> CalculationSourceResolution:
    revision = published_snapshot("130", filing_year=_YEAR, period="1T").revision
    return _resolve(transactions, invoices, revision=revision, modelo="130", period_code="1T")


def _reasons(resolution: CalculationSourceResolution) -> set[str]:
    return {diagnostic.reason for diagnostic in resolution.diagnostics}


def _source_refs(resolution: CalculationSourceResolution) -> set[str | None]:
    return {diagnostic.source_ref for diagnostic in resolution.diagnostics}


def test_a_movement_worth_half_the_invoice_declares_half_the_base_on_both_modelos() -> None:
    """USD 1.060,00 worth 530,00 EUR pays half: 500,00 of base, and no stated credit; never the whole 1.000,00."""
    movement = _movement("1060.00", eur="530.00")
    transactions, invoices = _linked(_invoice(movement), movement)

    annual = _m100(transactions, invoices)
    instalment = _m130(transactions, invoices)

    assert annual.binding_values[_M100_INCOME] == Decimal("500.00")
    assert annual.binding_values[_M100_CREDIT] == Decimal("0")
    assert instalment.binding_values[_M130_INCOME] == Decimal("500.00")
    assert instalment.binding_values[_M130_CREDIT] == Decimal("0")
    assert "part_payment_allocated" in _source_refs(annual)


def test_the_foreign_movement_reads_exactly_as_a_euro_movement_of_the_same_value() -> None:
    """The currency a movement arrived in changes nothing once its EUR value is stated."""
    foreign = _movement("1060.00", eur="530.00")
    euro = _movement("530.00", currency="EUR")

    foreign_read = _m100(*_linked(_invoice(foreign), foreign))
    euro_read = _m100(*_linked(_invoice(euro), euro))

    assert foreign_read.binding_values == euro_read.binding_values


def test_without_part_payment_allocation_the_same_figures_in_another_currency_are_refused() -> None:
    """The digit-for-digit USD match that used to pass is an amount mismatch."""
    movement = _movement("1060.00", eur="530.00")
    payload, refusal = _evidence(_invoice(movement), movement)

    assert refusal is SalesInvoiceEvidenceRefusal.AMOUNT_MISMATCH
    assert payload.taxable_base is None


def test_a_foreign_movement_worth_the_whole_invoice_grounds_it() -> None:
    """USD 2.120,00 worth 1.060,00 EUR settles it: the base and the stated retención both stand."""
    movement = _movement("2120.00", eur="1060.00")
    transactions, invoices = _linked(_invoice(movement), movement)

    annual = _m100(transactions, invoices)

    assert annual.binding_values[_M100_INCOME] == Decimal("1000.00")
    assert annual.binding_values[_M100_CREDIT] == Decimal("150.00")
    assert "unusable_sales_invoice_evidence" not in _reasons(annual)


@pytest.mark.parametrize(
    ("eur", "settled"),
    [
        pytest.param("1060.01", True, id="one-cent-over"),
        pytest.param("1059.99", True, id="one-cent-under"),
        pytest.param("1060.02", False, id="two-cents-over"),
        pytest.param("1059.98", False, id="two-cents-under"),
    ],
)
def test_the_link_tolerance_decides_a_settlement(eur: str, settled: bool) -> None:
    """One cent either way is the same payment; two cents is not."""
    movement = _movement("2000.00", eur=eur)
    payload, refusal = _evidence(_invoice(movement), movement)

    assert payload.taxable_base == (Decimal("1000.00") if settled else None)
    assert refusal is (None if settled else SalesInvoiceEvidenceRefusal.AMOUNT_MISMATCH)


def test_two_cents_over_declares_the_cash_and_says_why_through_the_resolver() -> None:
    """Above the tolerance no invoice figure stands: 1.060,02 of cash and the unusable-evidence finding."""
    movement = _movement("2000.00", eur="1060.02")
    transactions, invoices = _linked(_invoice(movement), movement)

    annual = _m100(transactions, invoices)

    assert annual.binding_values[_M100_INCOME] == Decimal("1060.02")
    assert "unusable_sales_invoice_evidence" in _reasons(annual)


def test_two_cents_under_is_a_part_payment_through_the_resolver() -> None:
    """Below the tolerance it is a share: 1.000,00 x 1.059,98 / 1.060,00 rounds to 999,98."""
    movement = _movement("2000.00", eur="1059.98")
    transactions, invoices = _linked(_invoice(movement), movement)

    assert _m100(transactions, invoices).binding_values[_M100_INCOME] == Decimal("999.98")


def test_two_foreign_part_payments_add_up_by_their_eur_values() -> None:
    """USD 1.100,00 twice is 2.200,00 raw but 530,00 EUR twice: the invoice exactly, not an overpayment."""
    first = _movement("1100.00", eur="530.00", provider_id="cobro-1")
    second = _movement("1100.00", eur="530.00", provider_id="cobro-2")
    transactions, invoices = _linked(_invoice(first, second), first, second)

    annual = _m100(transactions, invoices)

    assert annual.binding_values[_M100_INCOME] == Decimal("1000.00")
    assert not any("overpaid_invoice" in diagnostic.message for diagnostic in annual.diagnostics)


def test_receipts_overpay_by_their_eur_values_whatever_their_raw_sum() -> None:
    """USD 500,00 twice is 1.000,00 raw, under the 1.060,00 owed, but 600,00 EUR twice exceeds it."""
    first = _movement("500.00", eur="600.00", provider_id="cobro-1")
    second = _movement("500.00", eur="600.00", provider_id="cobro-2")
    transactions, invoices = _linked(_invoice(first, second), first, second)

    annual = _m100(transactions, invoices)

    assert any("overpaid_invoice" in diagnostic.message for diagnostic in annual.diagnostics)


def test_a_movement_with_no_eur_value_is_refused_and_never_compared_raw() -> None:
    """A USD 1.060,00 movement with no conversion matches nothing, and the row stays out as unresolved."""
    movement = _movement("1060.00")
    payload, refusal = _evidence(_invoice(movement), movement)
    annual = _m100(*_linked(_invoice(movement), movement))

    assert refusal is SalesInvoiceEvidenceRefusal.NO_EUR_VALUE
    assert payload.taxable_base is None
    assert annual.binding_values[_M100_INCOME] == Decimal("0")
    assert any("USD" in diagnostic.message for diagnostic in annual.diagnostics)


def test_an_unrated_foreign_invoice_paid_in_euro_has_no_common_currency() -> None:
    """An invoice with no stamped rate has no EUR total, so EUR 1.060,00 cannot settle it digit for digit."""
    movement = _movement("1060.00", currency="EUR")
    payload, refusal = _evidence(_invoice(movement, currency="USD"), movement)

    assert refusal is SalesInvoiceEvidenceRefusal.NO_EUR_VALUE
    assert payload.taxable_base is None


def test_an_unrated_foreign_invoice_paid_in_its_own_currency_declares_the_cash_with_a_finding() -> None:
    """The USD figures settle, but USD is no figure for a casilla: the movement's 636,00 EUR stands, flagged."""
    movement = _movement("1060.00", eur="636.00")
    invoice = _invoice(movement, currency="USD")

    payload, refusal = _evidence(invoice, movement)
    annual = _m100(*_linked(invoice, movement))

    assert refusal is SalesInvoiceEvidenceRefusal.NO_EUR_VALUE
    assert payload.taxable_base is None
    assert annual.binding_values[_M100_INCOME] == Decimal("636.00")
    assert "unusable_sales_invoice_evidence" in _reasons(annual)


def test_a_rated_foreign_invoice_paid_in_its_own_currency_at_another_rate_gives_eur_figures() -> None:
    """Settled in USD whatever the two rates: at the invoice's 0,50 the base is 500,00 and the retención 75,00."""
    movement = _movement("1060.00", eur="636.00")
    transactions, invoices = _linked(_invoice(movement, currency="USD", fx_rate="0.50"), movement)

    annual = _m100(transactions, invoices)

    assert annual.binding_values[_M100_INCOME] == Decimal("500.00")
    assert annual.binding_values[_M100_CREDIT] == Decimal("75.00")


def test_a_third_currency_settles_a_rated_foreign_invoice_through_eur() -> None:
    """GBP against USD meet in EUR: 605,00 total less 75,00 retención at 0,50 is the 530,00 the movement is worth."""
    movement = _movement("450.00", currency="GBP", eur="530.00")
    payload, refusal = _evidence(_invoice(movement, currency="USD", fx_rate="0.50"), movement)

    assert refusal is None
    assert payload.taxable_base == Decimal("500.00")
    assert payload.retencion_amount == Decimal("75.00")


def test_modelo_347_reads_a_cash_accounting_invoice_the_same_with_or_without_a_link() -> None:
    """Its record comes from the invoice and its printed mention; a mismatched link moves nothing on it."""
    mention = resolve_invoice_legal_mention("CASH_ACCOUNTING_REGIME", _ON)
    movement = _movement("1060.00", eur="530.00")
    revision = published_snapshot("347", filing_year=_YEAR, period="0A").revision
    context = CalculationSourceContext(
        bucket_id=_BUCKET,
        modelo="347",
        filing_year=_YEAR,
        period=renta_income_aggregation_period(_YEAR, "0A"),
        revision=revision,
        profile=cash_criterion_profile(_YEAR),
    )

    # A withholding would exclude the operation under art. 33.2.i, which is not what this case reads.
    unwithheld = {"retention_rate": None, "retention_amount": None}
    unlinked = invoice_observation(
        _invoice(legal_mentions=(mention,)).model_copy(update=unwithheld), context=context, m347_filer=M347Filer()
    )
    linked = invoice_observation(
        _invoice(movement, legal_mentions=(mention,)).model_copy(update=unwithheld),
        context=context,
        m347_filer=M347Filer(),
    )

    assert linked is not None
    assert linked.cash_accounting_operation is True
    assert linked == unlinked
    assert linked.base_amount == Decimal("1000.00")
