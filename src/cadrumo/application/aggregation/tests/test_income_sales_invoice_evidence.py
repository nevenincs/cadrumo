"""A linked sales invoice supplies the income row's base, cuota and retención.

``link_invoice`` attaches a foreign key and carries no fiscal content, so before
this evidence path a matched, reciprocal sales invoice still left casilla 01 on
the bank credit: 1060 instead of the 1000 base, with the 150 retención credit
lost. The operator had done everything the product asks.

Derive-on-read, mirroring the expense pipeline: nothing is copied at link time,
so a corrected invoice is reflected on the next aggregation and no stale figure
can outlive it, and a link whose amounts do not correspond is refused rather
than applied.

The figures are invoice arithmetic -- 1000 base, 210 cuota at 21 %, 150
retención at 15 %, so 1060 reaches the bank -- not the output of any registry
formula under test.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ....core.aggregation import LedgerIncomeGrounding, LedgerWithholdingDerivation
from ....core.period import Period
from ....domain.invoices.enums import IvaRate, PaymentStatus, iva_rate_percentage
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.transactions.retencion_parameters import statutory_activity_retencion_rates
from ....domain.transactions.service import link_invoice
from .._renta_income_ledger import (
    SalesInvoiceEvidenceRefusal,
    aggregate_renta_income_ledger,
    aggregate_renta_m100_income_ledger,
)
from .._retencion_rate_advisory import (
    _conforms_to_fixed_rate,
    inferred_actividad_retencion_rate_advisory_observations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
_OTHER_BUCKET = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
_QUARTER = Period.from_year_and_code(2024, "1T")
_ANNUAL = Period.from_year_and_code(2024, "0A")


def _transaction(*, cash: str, provider_id: str = "cobro-1") -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2024, 3, 15),
        value_date=date(2024, 3, 15),
        amount=Decimal(cash),
        currency="EUR",
        counterparty="Cliente SL",
        description="cobro factura",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2024, 4, 6, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={},
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
            "classified_at": datetime(2024, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _invoice(
    *,
    linked_transaction_ids: tuple[str, ...],
    kind: InvoiceKind = InvoiceKind.ISSUED,
    bucket_id: str = _BUCKET,
    retention_amount: str | None = "150.00",
    retention_rate: str = "0.15",
    number: str = "F-2024-001",
    iva_category: IvaCategory | None = IvaCategory.DOMESTIC_GENERAL,
) -> Invoice:
    rate = iva_rate_percentage(IvaRate.RATE_21)
    assert rate is not None
    line = InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=Decimal("1000.00"),
        subtotal=Decimal("1000.00"),
        iva_rate=IvaRate.RATE_21,
        iva_amount=Decimal("1000.00") * rate,
    )
    return Invoice.model_validate(
        {
            "kind": kind,
            "invoice_number": number,
            "issued_at": date(2024, 3, 15),
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "bucket_id": bucket_id,
            "base_total": Decimal("1000.00"),
            "iva_total": line.iva_amount,
            "grand_total": Decimal("1000.00") + line.iva_amount,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "iva_category": iva_category,
            "retention_rate": None if retention_amount is None else Decimal(retention_rate),
            "retention_amount": None if retention_amount is None else Decimal(retention_amount),
            "linked_transaction_ids": linked_transaction_ids,
        },
    )


def _linked(
    *,
    cash: str = "1060.00",
    retention_rate: str = "0.15",
    **invoice_kwargs: Any,
) -> tuple[TransactionCatalogue, InvoiceCatalogue]:
    transaction = _transaction(cash=cash)
    invoice = _invoice(
        linked_transaction_ids=(transaction.transaction_id,),
        retention_rate=retention_rate,
        **invoice_kwargs,  # type: ignore[arg-type]
    )
    catalogue = link_invoice(
        TransactionCatalogue.from_transactions((transaction,)),
        transaction.transaction_id,
        invoice.invoice_id,
    )
    return catalogue, InvoiceCatalogue.from_invoices((invoice,))


def test_a_linked_sales_invoice_puts_casilla_01_on_the_base_not_the_cash() -> None:
    """The defect this path closes: 1060 credited, 1000 declared."""
    transactions, invoices = _linked()

    aggregation = aggregate_renta_income_ledger(transactions, invoices, bucket_id=_BUCKET, period=_QUARTER)

    assert aggregation.issues == ()
    assert aggregation.casilla_aggregation.casilla_values["01"] == Decimal("1000.00")
    observation = aggregation.observations[0]
    assert observation.taxable_base_amount == Decimal("1000.00")
    assert observation.grounding is LedgerIncomeGrounding.SUBSTRATE_DECLARED


def test_the_declared_retencion_is_preferred_over_the_inference() -> None:
    """A figure the invoice states beats one reconstructed from the bank credit."""
    transactions, invoices = _linked()

    observation = aggregate_renta_income_ledger(
        transactions,
        invoices,
        bucket_id=_BUCKET,
        period=_QUARTER,
    ).observations[0]

    assert observation.withheld_amount == Decimal("150.00")
    assert observation.withheld_derivation is LedgerWithholdingDerivation.DECLARED_ON_LINKED_INVOICE


def test_a_declared_retencion_is_never_screened_by_the_rate_advisory() -> None:
    """The advisory discloses INFERENCES; it does not second-guess a document.

    The exclusion is implemented -- ``DECLARED_ON_LINKED_INVOICE`` is absent from
    the advisory's inferred-marker set -- and asserted in prose there, but no gate
    held it, so a marker-set edit could have widened the screen onto declared
    figures silently.

    123,45 on a 1.000,00 base is 12,345 %, which matches no RIRPF art. 95 rate.
    An inferred figure of that shape fires the advisory; this one must not, purely
    because the invoice STATES it. That is why the amount is deliberately
    non-conforming: a conforming figure would pass for the wrong reason and prove
    nothing about the exclusion.
    """
    transactions, invoices = _linked(
        cash="1086.55",
        retention_amount="123.45",
        retention_rate="0.12345",
    )

    observations = aggregate_renta_income_ledger(
        transactions,
        invoices,
        bucket_id=_BUCKET,
        period=_QUARTER,
    ).observations

    assert observations[0].withheld_amount == Decimal("123.45")
    assert observations[0].withheld_derivation is LedgerWithholdingDerivation.DECLARED_ON_LINKED_INVOICE
    assert observations[0].taxable_base_amount == Decimal("1000.00")
    assert not any(
        _conforms_to_fixed_rate(Decimal("1000.00"), observations[0].withheld_amount, rate)
        for rate in statutory_activity_retencion_rates()
    ), "the figure must match no statutory rate, or the silence below proves nothing"

    assert inferred_actividad_retencion_rate_advisory_observations(observations) == ()


def test_the_annual_m100_path_grounds_identically_to_the_quarterly_one() -> None:
    """Both entry points must ground the same row the same way.

    The single production call site chooses between them by modelo, so a row
    grounded on one path and not the other would declare different income on
    the annual return than the quarterly payments it reconciles against.
    """
    transactions, invoices = _linked()

    quarterly = aggregate_renta_income_ledger(transactions, invoices, bucket_id=_BUCKET, period=_QUARTER)
    annual = aggregate_renta_m100_income_ledger(transactions, invoices, bucket_id=_BUCKET, period=_ANNUAL)

    assert quarterly.casilla_aggregation.casilla_values["01"] == Decimal("1000.00")
    assert annual.casilla_aggregation.casilla_values["0171"] == Decimal("1000.00")
    assert quarterly.observations[0].withheld_amount == annual.observations[0].withheld_amount
    assert quarterly.observations[0].grounding is annual.observations[0].grounding


def test_an_unlinked_row_is_untouched_by_the_evidence_path() -> None:
    """The common case -- a bank credit with no invoice -- keeps its old behaviour."""
    transaction = _transaction(cash="1060.00")
    transactions = TransactionCatalogue.from_transactions((transaction,))

    aggregation = aggregate_renta_income_ledger(
        transactions,
        InvoiceCatalogue(),
        bucket_id=_BUCKET,
        period=_QUARTER,
    )

    assert aggregation.casilla_aggregation.casilla_values["01"] == Decimal("1060.00")
    assert aggregation.observations[0].grounding is LedgerIncomeGrounding.CASH_FALLBACK


def test_a_credit_matching_the_gross_rather_than_the_net_is_refused() -> None:
    """The guard that must NOT be copied from the expense side.

    An expense pays the whole contraprestación, so that pipeline asserts the
    cash equals ``grand_total``. A sales invoice under retención is paid net, so
    a credit of the full 1210 does not describe this payment and the link is
    refused rather than applied.
    """
    transactions, invoices = _linked(cash="1210.00")

    aggregation = aggregate_renta_income_ledger(transactions, invoices, bucket_id=_BUCKET, period=_QUARTER)

    assert aggregation.observations[0].sales_invoice_refusal is SalesInvoiceEvidenceRefusal.AMOUNT_MISMATCH
    assert aggregation.casilla_aggregation.casilla_values["01"] == Decimal("1210.00")


def test_an_invoice_without_retencion_is_matched_on_its_gross() -> None:
    """With no retención declared, net and gross coincide and the row grounds."""
    transactions, invoices = _linked(cash="1210.00", retention_amount=None)

    aggregation = aggregate_renta_income_ledger(transactions, invoices, bucket_id=_BUCKET, period=_QUARTER)

    assert aggregation.issues == ()
    assert aggregation.casilla_aggregation.casilla_values["01"] == Decimal("1000.00")
    assert aggregation.observations[0].withheld_amount == Decimal("0")


def test_a_received_invoice_is_refused_as_income_evidence() -> None:
    """A purchase invoice is not this taxpayer's income, whatever it is linked to."""
    transactions, invoices = _linked(kind=InvoiceKind.RECEIVED)

    aggregation = aggregate_renta_income_ledger(transactions, invoices, bucket_id=_BUCKET, period=_QUARTER)

    assert aggregation.observations[0].sales_invoice_refusal is SalesInvoiceEvidenceRefusal.UNSUPPORTED_KIND
    assert aggregation.casilla_aggregation.casilla_values["01"] == Decimal("1060.00")


def test_an_invoice_from_another_bucket_is_refused() -> None:
    """Evidence must belong to the bucket whose return is being built."""
    transactions, invoices = _linked(bucket_id=_OTHER_BUCKET)

    aggregation = aggregate_renta_income_ledger(transactions, invoices, bucket_id=_BUCKET, period=_QUARTER)

    assert aggregation.observations[0].sales_invoice_refusal is SalesInvoiceEvidenceRefusal.BUCKET_MISMATCH
    assert aggregation.casilla_aggregation.casilla_values["01"] == Decimal("1060.00")


def test_a_one_directional_link_is_refused() -> None:
    """The invoice must name the transaction back, or the pairing is unconfirmed."""
    transaction = _transaction(cash="1060.00")
    invoice = _invoice(linked_transaction_ids=("f" * 64,))
    transactions = link_invoice(
        TransactionCatalogue.from_transactions((transaction,)),
        transaction.transaction_id,
        invoice.invoice_id,
    )

    aggregation = aggregate_renta_income_ledger(
        transactions,
        InvoiceCatalogue.from_invoices((invoice,)),
        bucket_id=_BUCKET,
        period=_QUARTER,
    )

    assert aggregation.observations[0].sales_invoice_refusal is SalesInvoiceEvidenceRefusal.LINK_NOT_RECIPROCAL
    assert aggregation.casilla_aggregation.casilla_values["01"] == Decimal("1060.00")


def test_an_invoice_spanning_several_transactions_is_refused() -> None:
    """A part-paid invoice cannot attribute its whole base to one credit."""
    transaction = _transaction(cash="1060.00")
    invoice = _invoice(linked_transaction_ids=(transaction.transaction_id, "e" * 64))
    transactions = link_invoice(
        TransactionCatalogue.from_transactions((transaction,)),
        transaction.transaction_id,
        invoice.invoice_id,
    )

    aggregation = aggregate_renta_income_ledger(
        transactions,
        InvoiceCatalogue.from_invoices((invoice,)),
        bucket_id=_BUCKET,
        period=_QUARTER,
    )

    assert aggregation.observations[0].sales_invoice_refusal is (
        SalesInvoiceEvidenceRefusal.PARTIAL_OR_MULTI_TRANSACTION
    )
    assert aggregation.casilla_aggregation.casilla_values["01"] == Decimal("1060.00")


def test_each_guard_reports_its_own_reason() -> None:
    """Five distinct repairs must not present as one generic mismatch."""
    reasons = {
        aggregate_renta_income_ledger(*_linked(kind=InvoiceKind.RECEIVED), bucket_id=_BUCKET, period=_QUARTER)
        .observations[0]
        .sales_invoice_refusal,
        aggregate_renta_income_ledger(*_linked(bucket_id=_OTHER_BUCKET), bucket_id=_BUCKET, period=_QUARTER)
        .observations[0]
        .sales_invoice_refusal,
        aggregate_renta_income_ledger(*_linked(cash="1210.00"), bucket_id=_BUCKET, period=_QUARTER)
        .observations[0]
        .sales_invoice_refusal,
    }

    assert len(reasons) == 3, "distinct guards collapsed onto one reason"


def test_an_instalment_paid_invoice_still_declares_its_cash() -> None:
    """The regression that made this path degrade rather than exclude.

    One invoice settled in two instalments is ordinary for professional work.
    Returning an exclusion for the multi-transaction guard removed BOTH rows
    from the aggregation, so 1060 of real income declared zero -- a 100 %
    under-declaration, in the sanction direction, replacing an over-declaration
    of 60.

    The assertion that matters is the income figure. A test checking only that
    a refusal was recorded passes just as happily while the money disappears.
    """
    first = _transaction(cash="530.00", provider_id="instalment-1")
    second = _transaction(cash="530.00", provider_id="instalment-2")
    invoice = _invoice(linked_transaction_ids=(first.transaction_id, second.transaction_id))
    transactions = TransactionCatalogue.from_transactions((first, second))
    for transaction in (first, second):
        transactions = link_invoice(transactions, transaction.transaction_id, invoice.invoice_id)

    aggregation = aggregate_renta_income_ledger(
        transactions,
        InvoiceCatalogue.from_invoices((invoice,)),
        bucket_id=_BUCKET,
        period=_QUARTER,
    )

    assert aggregation.casilla_aggregation.casilla_values["01"] == Decimal("1060.00")
    assert len(aggregation.observations) == 2
    assert aggregation.issues == ()
    assert all(
        observation.sales_invoice_refusal is SalesInvoiceEvidenceRefusal.PARTIAL_OR_MULTI_TRANSACTION
        for observation in aggregation.observations
    )
    assert all(observation.grounding is LedgerIncomeGrounding.CASH_FALLBACK for observation in aggregation.observations)


def test_no_evidence_guard_ever_removes_income_from_the_aggregation() -> None:
    """The contract the issue-reason enum already stated, now enforced.

    An unevidenced ingreso must still be declared -- only an unevidenced gasto
    may be dropped. Every guard is exercised here so a sixth one added later
    cannot quietly reintroduce an exclusion.
    """
    cases = (
        _linked(kind=InvoiceKind.RECEIVED),
        _linked(bucket_id=_OTHER_BUCKET),
        _linked(cash="1210.00"),
    )
    for transactions, invoices in cases:
        aggregation = aggregate_renta_income_ledger(transactions, invoices, bucket_id=_BUCKET, period=_QUARTER)
        assert len(aggregation.observations) == 1, "an evidence guard excluded a declarable income row"
        assert aggregation.issues == ()
        assert aggregation.casilla_aggregation.casilla_values["01"] > Decimal("0")


def test_an_uncategorised_invoice_is_refused_even_though_it_reconciles_perfectly() -> None:
    """Linkage and coherence are different questions, and passing one is not passing the other.

    This invoice satisfies every linkage guard: same bucket, ISSUED, reciprocal
    single link, and a credit matching its total net of retención exactly. What
    it does not do is declare an IVA treatment, so its base is ambiguous between
    untagged and exempt — the distinction the grounding contract exists to
    preserve, and one no amount reconciliation can settle.

    Before the coherence check, this row folded its 1000.00 base into casilla 01
    with no diagnostic at all, which is the grounding contract's own D1 rule
    being bypassed by the path that reads invoices.
    """
    transactions, invoices = _linked(iva_category=None)

    result = aggregate_renta_income_ledger(
        transactions,
        period=Period.from_year_and_code(2024, "1T"),
        bucket_id=_BUCKET,
        invoices=invoices,
    )

    (observation,) = result.observations
    assert observation.sales_invoice_refusal is SalesInvoiceEvidenceRefusal.UNGROUNDED_DECOMPOSITION
    # Degraded, not dropped: the income is still declared, on its cash.
    assert result.casilla_aggregation.casilla_values["01"] == Decimal("1060.00")
    assert observation.grounding is LedgerIncomeGrounding.CASH_FALLBACK


def test_a_categorised_invoice_still_grounds_on_its_base() -> None:
    """The coherence check must not refuse the invoices this path exists to ground.

    The companion to the case above: identical in every respect except that the
    IVA treatment is declared. A guard that rejected both would look correct on
    the refusal test alone while destroying the feature.
    """
    transactions, invoices = _linked()

    result = aggregate_renta_income_ledger(
        transactions,
        period=Period.from_year_and_code(2024, "1T"),
        bucket_id=_BUCKET,
        invoices=invoices,
    )

    (observation,) = result.observations
    assert observation.sales_invoice_refusal is None
    assert result.casilla_aggregation.casilla_values["01"] == Decimal("1000.00")
