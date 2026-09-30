"""The actividad-económica retención credit takes only a declared figure.

A ledger row records no retención of its own. The figure is either read from the
retención the linked sales invoice DECLARES, or reconstructed from invoice gross
minus the cash the bank credited. Only the first is a recorded fact, and the
credit against the cuota rests on one (LIRPF art. 99; RIRPF arts. 95 and 108.4),
so the ``declared_withheld_amount_sum`` fact totals the declared figures alone.

What that exclusion must not do is read as a zero. A reconstructed figure is
reported with its count and amount so the operator can record it on the invoice
and claim it; a figure the substrate does not determine, or one the registry's
maximum supported rate refused, is reported as UNKNOWN rather than as nothing
withheld. Both travel beside the value through the derivation partition.

Every figure below is invoice arithmetic, hand-derived in the test that uses it,
not the output of any registry formula under test. Two rates are exercised
because a single rate cannot tell a per-invoice read apart from one that applies
one rate to a total: 1.000,00 at 15 % and 2.000,00 at 7 % give 150,00 and 140,00,
which no single rate over the 3.000,00 combined base reproduces.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from cadrumo.domain.invoices.tests.catalogue_support import build_invoice_catalogue

from ....core.aggregation import LedgerWithholdingDerivation
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.period import Period
from ....domain.calculations.registry.ledger_renta_income_bindings import (
    ledger_renta_withholding_derivation_partition,
    resolve_ledger_renta_income_aggregation_binding_values,
    unrouted_ledger_renta_income_quantities,
)
from ....domain.invoices.enums import IvaRate, PaymentStatus, iva_rate_percentage
from ....domain.invoices.models import Invoice, InvoiceCatalogue, InvoiceLine
from ....domain.iva.classification import InvoiceKind
from ....domain.iva.schema import IvaCategory
from ....domain.transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....domain.transactions.service import link_invoice
from ..renta_income_ledger import aggregate_renta_income_ledger
from .renta_income_aggregation_support import (
    m130_activity_category_matcher,
    m130_employment_category_matcher,
)
from .test_renta_income_actividad_contract import (
    _m130_2026_q1_revision,
    _m130_revision_without_the_retenciones_binding,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
_Q1 = Period.from_year_and_code(2026, "1T")
_Q4 = Period.from_year_and_code(2026, "4T")
_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_RETENCIONES_BINDING = "modelo-130-actividad-economica-retenciones-cumulative"
_DOMESTIC_GENERAL = IvaCategory("domestic_general")

# Hand-derived: 1.000,00 base at RIRPF art. 95.1's general 15 % leaves 150,00
# withheld, and 1.000,00 + 210,00 IVA - 150,00 = 1.060,00 reaches the bank.
_PROFESIONAL_BASE = Decimal("1000.00")
_PROFESIONAL_RETENCION = Decimal("150.00")
_PROFESIONAL_CASH = Decimal("1060.00")
# Hand-derived: 2.000,00 base at the art. 95.2 reduced 7 % leaves 140,00
# withheld, and 2.000,00 + 420,00 IVA - 140,00 = 2.280,00 reaches the bank.
_REDUCED_BASE = Decimal("2000.00")
_REDUCED_RETENCION = Decimal("140.00")
_REDUCED_CASH = Decimal("2280.00")
# Hand-derived: 150,00 + 140,00.
_DECLARED_CREDIT = Decimal("290.00")


def _transaction(
    *,
    provider_id: str,
    cash: Decimal,
    irpf_category: str | None = "actividad_economica",
) -> Transaction:
    raw = RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2026, 2, 10),
        value_date=date(2026, 2, 10),
        amount=cash,
        currency="EUR",
        counterparty="Cliente SL",
        description="cobro factura",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="e" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 6, 12, 0, tzinfo=UTC),
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
            "irpf_category": irpf_category,
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(2026, 4, 6, 13, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _issued_invoice(
    *,
    number: str,
    base: Decimal,
    linked_transaction_ids: tuple[str, ...],
    retention_amount: Decimal | None,
    retention_rate: Decimal | None,
) -> Invoice:
    rate = iva_rate_percentage(IvaRate.from_registry("RATE_21"), date(2026, 1, 1))
    assert rate is not None
    line = InvoiceLine(
        description="Servicios profesionales",
        quantity=Decimal("1"),
        unit_price=base,
        subtotal=base,
        iva_rate=IvaRate.from_registry("RATE_21"),
        iva_amount=base * rate,
    )
    return Invoice.model_validate(
        {
            "kind": InvoiceKind.ISSUED,
            "invoice_number": number,
            "issued_at": date(2026, 2, 10),
            "counterparty_name": "Cliente SL",
            "counterparty_tax_id": "B12345674",
            "counterparty_country": "ES",
            "bucket_id": _BUCKET,
            "base_total": base,
            "iva_total": line.iva_amount,
            "grand_total": base + line.iva_amount,
            "currency": "EUR",
            "lines": (line,),
            "payment_status": PaymentStatus.PAID,
            "iva_category": _DOMESTIC_GENERAL,
            "retention_rate": retention_rate,
            "retention_amount": retention_amount,
            "linked_transaction_ids": linked_transaction_ids,
        },
    )


def _declared_pair() -> tuple[TransactionCatalogue, InvoiceCatalogue]:
    """Two issued invoices whose retención each invoice states, at 15 % and 7 %."""
    profesional = _transaction(provider_id="cobro-15", cash=_PROFESIONAL_CASH)
    reduced = _transaction(provider_id="cobro-07", cash=_REDUCED_CASH)
    catalogue = TransactionCatalogue.from_transactions((profesional, reduced))
    invoices = (
        _issued_invoice(
            number="F-2026-001",
            base=_PROFESIONAL_BASE,
            linked_transaction_ids=(profesional.transaction_id,),
            retention_amount=_PROFESIONAL_RETENCION,
            retention_rate=Decimal("0.15"),
        ),
        _issued_invoice(
            number="F-2026-002",
            base=_REDUCED_BASE,
            linked_transaction_ids=(reduced.transaction_id,),
            retention_amount=_REDUCED_RETENCION,
            retention_rate=Decimal("0.07"),
        ),
    )
    for invoice, transaction in zip(invoices, (profesional, reduced), strict=True):
        catalogue = link_invoice(catalogue, transaction.transaction_id, invoice.invoice_id)
    return catalogue, build_invoice_catalogue(invoices)


def _aggregate(
    transactions: TransactionCatalogue,
    invoices: InvoiceCatalogue,
    *,
    period: Period = _Q1,
):
    return aggregate_renta_income_ledger(
        transactions,
        invoices,
        bucket_id=_BUCKET,
        period=period,
        modelo="130",
        target_casilla_id=_M130_INGRESOS_CASILLA,
        activity_category_matcher=m130_activity_category_matcher,
        employment_category_matcher=m130_employment_category_matcher,
    )


def test_declared_retenciones_at_two_rates_reach_the_credit() -> None:
    """Both invoices' stated retención enters the credit, each at its own rate.

    The oracle is invoice arithmetic: 150,00 at 15 % of 1.000,00 and 140,00 at
    7 % of 2.000,00, so the credit is 290,00. No single rate over the combined
    3.000,00 base reproduces that figure, which is why two rates are used.
    """
    transactions, invoices = _declared_pair()

    aggregation = _aggregate(transactions, invoices)
    revision = _m130_2026_q1_revision()
    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, aggregation.observations)

    assert resolved[_M130_RETENCIONES_BINDING] == _DECLARED_CREDIT
    partition = ledger_renta_withholding_derivation_partition(revision, aggregation.observations)
    assert partition.declared_total == _DECLARED_CREDIT
    assert partition.inferred_observations == ()
    assert partition.unresolved_observations == ()


def test_every_consumed_row_carries_its_declaring_marker() -> None:
    """Marker propagation: the credit's rows say where their figure came from.

    The marker is what the fact dispatches on, so a row whose figure the invoice
    states and one reconstructed from cash must not arrive indistinguishable.
    """
    transactions, invoices = _declared_pair()

    observations = _aggregate(transactions, invoices).observations

    assert len(observations) == 2
    assert {observation.withheld_derivation for observation in observations} == {
        LedgerWithholdingDerivation.DECLARED_ON_LINKED_INVOICE
    }
    assert {observation.withheld_amount for observation in observations} == {
        _PROFESIONAL_RETENCION,
        _REDUCED_RETENCION,
    }


def test_an_inferred_row_raises_the_advisory_and_leaves_the_credit_unchanged() -> None:
    """An unlinked net-paid receipt is reported, and adds nothing to the credit.

    Same two declared invoices as the positive case, plus a third receipt banked
    short of its invoice with no linked invoice to state the shortfall. Its
    retención is reconstructed, so the credit stays at 290,00 and the excluded
    amount is reported with its count.
    """
    transactions, invoices = _declared_pair()
    inferred = _transaction(provider_id="cobro-sin-factura", cash=Decimal("850.00"))
    transactions = TransactionCatalogue.from_transactions((*transactions.values(), inferred))

    aggregation = _aggregate(transactions, invoices)
    revision = _m130_2026_q1_revision()
    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, aggregation.observations)
    partition = ledger_renta_withholding_derivation_partition(revision, aggregation.observations)

    assert resolved[_M130_RETENCIONES_BINDING] == _DECLARED_CREDIT, (
        "an inferred row must leave the declared credit exactly where it stood"
    )
    assert partition.declared_total == _DECLARED_CREDIT
    reported = {observation.transaction_id for observation in partition.inferred_observations} | {
        observation.transaction_id for observation in partition.unresolved_observations
    }
    assert inferred.transaction_id in reported, "the excluded row must be reported, not silently dropped"


def test_a_substrate_less_row_is_unresolved_rather_than_a_proven_zero() -> None:
    """A row the substrate cannot price reports UNKNOWN, never nothing withheld.

    An activity receipt with no taxable base and no linked invoice leaves the
    retención undetermined. Reporting it as zero would assert the client withheld
    nothing, which the ledger does not know, so it is reported as unresolved and
    the credit stays at the declared 290,00.
    """
    transactions, invoices = _declared_pair()
    substrate_less = _transaction(provider_id="cobro-sin-base", cash=Decimal("400.00"))
    transactions = TransactionCatalogue.from_transactions((*transactions.values(), substrate_less))

    aggregation = _aggregate(transactions, invoices)
    revision = _m130_2026_q1_revision()
    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, aggregation.observations)
    partition = ledger_renta_withholding_derivation_partition(revision, aggregation.observations)

    assert resolved[_M130_RETENCIONES_BINDING] == _DECLARED_CREDIT
    observation = next(
        candidate for candidate in aggregation.observations if candidate.transaction_id == substrate_less.transaction_id
    )
    assert observation.withheld_derivation is LedgerWithholdingDerivation.NO_SUBSTRATE
    assert observation.withheld_amount == Decimal("0")
    assert observation in partition.unresolved_observations, (
        "a row whose retención is unknown must be reported as unresolved, not read as a zero"
    )
    assert observation not in partition.inferred_observations


def test_employment_and_non_activity_rows_never_reach_the_credit() -> None:
    """Only actividad-económica receipts feed the credit.

    An employment receipt's withholding is Modelo 100 casilla 0596's subject and
    an uncategorised receipt is not activity income at all, so neither may enter
    the actividades-económicas credit however it was paid.

    Both rows are still projected, and that is the point: they arrive carrying
    ``NOT_APPLICABLE`` rather than absent, so the exclusion is a typed state a
    reader can see instead of a row that quietly went missing. Neither is
    reported as inferred or unresolved, because neither leaves a retención
    undetermined: there is none to determine.
    """
    transactions, invoices = _declared_pair()
    employment = _transaction(
        provider_id="nomina",
        cash=Decimal("1800.00"),
        irpf_category="rendimientos_trabajo",
    )
    uncategorised = _transaction(provider_id="sin-categoria", cash=Decimal("500.00"), irpf_category=None)
    transactions = TransactionCatalogue.from_transactions((*transactions.values(), employment, uncategorised))

    aggregation = _aggregate(transactions, invoices)
    revision = _m130_2026_q1_revision()
    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, aggregation.observations)

    assert resolved[_M130_RETENCIONES_BINDING] == _DECLARED_CREDIT
    by_transaction = {observation.transaction_id: observation for observation in aggregation.observations}
    for excluded in (employment, uncategorised):
        observation = by_transaction[excluded.transaction_id]
        assert observation.withheld_derivation is LedgerWithholdingDerivation.NOT_APPLICABLE
        assert observation.withheld_amount == Decimal("0")
    partition = ledger_renta_withholding_derivation_partition(revision, aggregation.observations)
    reported = {observation.transaction_id for observation in partition.inferred_observations} | {
        observation.transaction_id for observation in partition.unresolved_observations
    }
    assert reported == set()


def test_the_unrouted_quantity_screen_is_silent_while_a_binding_draws_the_retencion() -> None:
    """The screen reports only a retención no binding draws.

    Silence here is not a property of the rows: strip the retención binding from
    the revision and the same rows produce the finding, which is what proves the
    screen was watching rather than switched off.
    """
    transactions, invoices = _declared_pair()
    observations = _aggregate(transactions, invoices).observations

    assert unrouted_ledger_renta_income_quantities(_m130_2026_q1_revision(), observations) == ()

    stripped = unrouted_ledger_renta_income_quantities(
        _m130_revision_without_the_retenciones_binding(),
        observations,
    )
    assert len(stripped) == 1
    assert stripped[0].fact == "declared_withheld_amount_sum"
    assert stripped[0].total == _DECLARED_CREDIT


def test_the_fourth_quarter_credit_agrees_with_the_same_ledger_read_annually() -> None:
    """The cumulative fourth quarter credits exactly the ejercicio's declared retención.

    Modelo 130 casilla 06 accumulates from the start of the year, so the fourth
    quarter's credit IS the ejercicio's figure over the same ledger. This is the
    consistency the annual declaration has to agree with, asserted against the
    hand-derived 290,00 rather than against either read's own output.
    """
    transactions, invoices = _declared_pair()

    fourth_quarter = _aggregate(transactions, invoices, period=_Q4)
    revision = _m130_2026_q1_revision()
    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, fourth_quarter.observations)

    assert resolved[_M130_RETENCIONES_BINDING] == _DECLARED_CREDIT
    first_quarter = _aggregate(transactions, invoices, period=_Q1)
    assert (
        resolve_ledger_renta_income_aggregation_binding_values(revision, first_quarter.observations)[
            _M130_RETENCIONES_BINDING
        ]
        == _DECLARED_CREDIT
    ), "every February receipt is inside both cumulative windows"
