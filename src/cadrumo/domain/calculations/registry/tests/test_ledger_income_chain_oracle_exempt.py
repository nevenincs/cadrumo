"""The exempt professional service, driven to the casilla the registry binds.

The sibling module covers a rated invoice, where an unrecorded base moves
casilla 01 UP: the IVA collected on Hacienda's behalf outweighs the retencion,
so the bank credit exceeds the ingresos integros and the taxpayer over-declares.
This module covers the case that runs the other way, and it is the dangerous
one. An IVA-exempt professional service (LIVA art. 20) has no cuota to offset
the withholding, so the bank credit is strictly BELOW the ingresos integros:
without its base, casilla 01 receives the net-of-retencion cash and the return
under-declares by exactly the withheld amount, while the offsetting retenciones
credit disappears at the same time. One missing field, two losses, both in the
taxpayer's disfavour and neither previously watched.

The invoice::

    base imponible      1000.00
    IVA repercutido        0.00   (exempt, LIVA art. 20 -- no cuota exists)
    retencion            150.00   (15 % of the BASE, RIRPF art. 95.1)
    ---------------------------------
    total                1000.00   = base + cuota
    cash received         850.00   = total - retencion

**Where every expected figure comes from.** The 1000 is the base imponible the
invoice states, which the bundled AEAT Modelo 130 instructions call the
"ingresos integros fiscalmente computables" that casilla 01 consigns. The zero
cuota is not a missing figure: the declared category makes it zero by law, which
is precisely what lets the withholding be recovered here at all. The 150 is the
RIRPF art. 95.1 general rate on those ingresos integros -- the bundled
consolidated text of RD 439/2007 art. 95 reads "15 por ciento sobre los ingresos
integros satisfechos" -- read from the registry parameter catalogue rather than
restated. The 850 follows from ``cash = total - retencion``.

None of those figures is engine output. The engine derives the withholding by
subtracting cash from the invoice gross and never applies a rate, so the
statutory-rate expectation below reaches 150 by an unrelated route; the two
meeting is the grounding. Cuota-lessness is what makes this case worth pinning
separately: the derivation only reaches it because the declared category
determines the cuota, and a regression that went back to requiring a recorded
``iva_amount`` would silently return the withholding to zero here while the
rated module stayed green.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from .....application.aggregation import aggregate_renta_income_ledger
from .....core import CasillaId, Period, validated_casilla_id
from .....core.aggregation import LedgerIncomeGrounding, LedgerWithholdingDerivation
from ....iva import InvoiceKind, IvaCategory, category_cuota_is_zero_by_law
from ....transactions.enums import BusinessClassification, TransactionDirection, TransactionLifecycleState
from ....transactions.models import Transaction, TransactionCatalogue
from ....transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ....transactions.retencion_parameters import load_retencion_actividades_rates
from ..ledger_bindings import (
    resolve_ledger_renta_income_aggregation_binding_values,
    ungrounded_ledger_renta_income_observations,
)
from ._ledger_income_chain_oracle_support import modelo_130_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

# The invoice, stated once from the document and the cited rate.
_BASE = Decimal("1000.00")
_CUOTA = Decimal("0.00")
_TOTAL = _BASE + _CUOTA
_RETENCION = Decimal("150.00")
_CASH = _TOTAL - _RETENCION

_INGRESOS_BINDING = "modelo-130-actividad-economica-ingresos-cumulative"
_RETENCIONES_BINDING = "modelo-130-actividad-economica-retenciones-cumulative"
_TAXABLE_BASE_BINDING = "modelo-130-actividad-economica-ingresos-taxable-base-cumulative"

_FILING_YEAR = 2026
_PERIOD = Period.from_year_and_code(_FILING_YEAR, "1T")
_VALUE_DATE = date(_FILING_YEAR, 3, 4)
_BUCKET = "eeb87dd1-12bd-4e70-8f3e-751d9bb85455"  # was 'bucket-oracle-exempt'

_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")


def _invoice_row(*, declares_substrate: bool) -> Transaction:
    """The one exempt invoice as a ledger row, with or without its substrate.

    The substrate-less variant declares no category either, which is the whole
    ambiguity: a base with no cuota and a bank credit with nothing recorded
    against it are indistinguishable on the amounts alone. Only the declared
    category separates exempt income from untagged income, which is why the
    category travels with the base rather than being kept when the base is
    dropped.
    """
    raw = RawTransaction(
        provider_transaction_id="exempt-professional-invoice",
        booked_date=_VALUE_DATE,
        value_date=_VALUE_DATE,
        amount=_CASH,
        currency="EUR",
        counterparty="Clinica Ejemplo SL",
        description="Servicios profesionales exentos F-2026-042",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=42,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(_FILING_YEAR, 4, 6, 9, 30, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": "F-2026-042"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": _BASE if declares_substrate else None,
            "iva_amount": None,
            "iva_rate": None,
            "iva_category": IvaCategory.DOMESTIC_EXEMPT if declares_substrate else None,
            "irpf_category": "actividad_economica",
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(_FILING_YEAR, 4, 6, 10, 30, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _aggregated(*, declares_substrate: bool):
    """Drive one invoice through the production aggregation link of the chain."""
    return aggregate_renta_income_ledger(
        TransactionCatalogue.from_transactions((_invoice_row(declares_substrate=declares_substrate),)),
        bucket_id=_BUCKET,
        period=_PERIOD,
    )


def test_the_worked_example_figures_satisfy_the_invoice_identity() -> None:
    """The scenario's own arithmetic, and the direction that makes it dangerous.

    The rated sibling's cash EXCEEDS its base; this one's falls short of it.
    Stating that inequality here fixes the case's identity: an edit that gave
    this invoice a cuota would turn it into the other module's scenario while
    every assertion below still passed for the wrong reason.
    """
    assert _TOTAL == _BASE + _CUOTA
    assert _CASH == _TOTAL - _RETENCION
    assert _CASH < _BASE, "the exempt case is the under-declaring direction; that is why it is separate"


def test_the_declared_category_is_what_makes_the_cuota_zero() -> None:
    """Zero cuota here is a legal fact about the category, not an absent field.

    The whole recovery depends on this distinction: an absent ``iva_amount``
    with no category is unknown data, while an absent one under a cuota-less
    category is an operation that has no cuota to record. Reading the Axis-A
    table rather than testing for nullness is what separates them, so the
    premise is asserted rather than assumed.
    """
    assert category_cuota_is_zero_by_law(IvaCategory.DOMESTIC_EXEMPT, InvoiceKind.ISSUED)
    assert not category_cuota_is_zero_by_law(IvaCategory.DOMESTIC_GENERAL, InvoiceKind.ISSUED)


def test_the_declared_invoice_reaches_casilla_01_as_its_published_base() -> None:
    """Casilla 01 receives the full 1000 ingresos integros, not the 850 banked."""
    revision = modelo_130_revision()
    aggregation = _aggregated(declares_substrate=True)

    assert aggregation.issues == ()
    assert len(aggregation.observations) == 1
    observation = aggregation.observations[0]
    assert observation.grounding is LedgerIncomeGrounding.SUBSTRATE_DECLARED
    assert observation.withheld_derivation is LedgerWithholdingDerivation.INFERRED_FROM_CATEGORY_ZERO_CUOTA

    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, aggregation.observations)

    assert resolved[_INGRESOS_BINDING] == _BASE
    assert resolved[_INGRESOS_BINDING] != _CASH, "casilla 01 is pre-retencion, not what the bank credited"
    assert resolved[_TAXABLE_BASE_BINDING] == _BASE


def test_the_exempt_invoice_recovers_its_retencion_at_the_statutory_figure() -> None:
    """The withheld binding resolves to the statutory 15 % of the base.

    This is the assertion the old both-fields precondition made impossible: no
    cuota was recorded, so the derivation never ran and the credit was zero.
    The expectation arrives from RIRPF art. 95.1 on the base; the engine
    arrives by subtracting cash from a gross whose cuota the category supplied.

    The rated sibling additionally proves the figure is not a rate inverted off
    the cash. That guard cannot discriminate HERE and is deliberately absent:
    with no cuota the total IS the base, so ``cash = base * (1 - r)`` exactly
    and inverting the rate returns the same 150 by coincidence. Asserting it
    would look like a check while excluding nothing -- the cuota is what breaks
    the coincidence, which is why the inversion guard belongs to the rated
    case.
    """
    revision = modelo_130_revision()
    aggregation = _aggregated(declares_substrate=True)

    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, aggregation.observations)
    statutory = (_BASE * load_retencion_actividades_rates().general_rate).quantize(Decimal("0.01"))

    assert resolved[_RETENCIONES_BINDING] == statutory
    assert resolved[_RETENCIONES_BINDING] == _RETENCION
    assert resolved[_RETENCIONES_BINDING] != Decimal("0"), (
        "a cuota-less invoice still withholds; a zero here is the pre-relaxation defect"
    )


def test_the_declared_invoice_raises_no_ungrounded_advisory() -> None:
    """A fully declared exempt invoice must not fire the advisory.

    Cuota-less is not substrate-less. An exempt row that declares its base has
    given the casilla everything it asks for, and a screen that reported it
    would make the advisory fire on the ordinary exempt professional -- the
    fastest way to train an operator to ignore the case below.
    """
    revision = modelo_130_revision()
    aggregation = _aggregated(declares_substrate=True)

    screened = ungrounded_ledger_renta_income_observations(revision, aggregation.observations)

    assert screened.observations == ()


def test_the_unrecorded_invoice_under_declares_by_exactly_the_withheld_amount() -> None:
    """Without its base, casilla 01 falls to the cash and the credit is lost.

    The shortfall is not incidental: casilla 01 loses exactly what the payer
    withheld, and the retenciones casilla loses the same figure again, so the
    taxpayer both declares too little income and claims too little credit for
    it. Pinning the shortfall to the withheld amount rather than to a bare 150
    keeps the two halves tied to one another rather than to a literal.
    """
    revision = modelo_130_revision()
    aggregation = _aggregated(declares_substrate=False)

    assert len(aggregation.observations) == 1
    observation = aggregation.observations[0]
    assert observation.grounding is LedgerIncomeGrounding.CASH_FALLBACK
    assert observation.withheld_derivation is LedgerWithholdingDerivation.NO_SUBSTRATE

    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, aggregation.observations)

    assert resolved[_INGRESOS_BINDING] == _CASH
    assert _BASE - resolved[_INGRESOS_BINDING] == _RETENCION
    assert resolved[_RETENCIONES_BINDING] == Decimal("0")
    assert resolved[_TAXABLE_BASE_BINDING] == Decimal("0")


def test_the_under_declaration_is_surfaced_rather_than_silently_folded() -> None:
    """The under-declaring row fires the advisory, naming both facts.

    This is the only thing standing between the exempt freelancer and a
    silently short return: the fallback is kept deliberately (dropping the row
    would under-declare by the whole 850 rather than by 150), so the screen
    firing IS the closure of the under-declaration direction.
    """
    revision = modelo_130_revision()
    aggregation = _aggregated(declares_substrate=False)

    screened = ungrounded_ledger_renta_income_observations(revision, aggregation.observations)

    assert len(screened.observations) == 1
    assert screened.observations[0].target_casilla_id == _M130_INGRESOS_CASILLA
    assert screened.facts == frozenset({"ingresos_integros_sum", "taxable_base_sum"})
