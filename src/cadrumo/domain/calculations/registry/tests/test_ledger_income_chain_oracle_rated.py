"""The rated professional invoice, driven to the casilla the registry binds.

The income chain has three links -- a ledger row, the aggregation that builds an
observation from it, and the registry binding that resolves an observation set
into a casilla value -- and each was covered alone. What nothing pinned was the
whole run: a chain can be green link by link and still deliver the wrong figure
to casilla 01, because no test read the resolved binding value for a row that
started as a real invoice.

The invoice is one ordinary Spanish professional service::

    base imponible      1000.00
    IVA repercutido      210.00   (21 %, LIVA art. 90)
    retencion            150.00   (15 % of the BASE, RIRPF art. 95.1)
    ---------------------------------
    total                1210.00   = base + cuota
    cash received        1060.00   = total - retencion

**Where every expected figure comes from, and why none of it is the engine.**
The 1000 is the base imponible the invoice states; the bundled AEAT Modelo 130
instructions define casilla 01 as the "ingresos integros fiscalmente
computables", and the IVA repercutido is not an ingreso of the issuer, so 1000
is the published measure and 1210 is not. That last step rests on PGC NRV
12.a/14.a, which is NOT in the bundled corpus: it is a reading of cited
authority, not bundled text this repo can re-verify. Retrieval was attempted
against the BOE consolidated API for RD 1514/2007 and returned 404 on every
endpoint tried, so the gap is recorded rather than papered over. The assertions
below do not depend on it -- the bundled Modelo 130 instructions already name
casilla 01 as the ingresos integros, and the accounting norm only explains WHY
the cuota is excluded. The 150 is
the RIRPF art. 95.1 general rate applied to those ingresos integros -- the
bundled consolidated text of RD 439/2007 art. 95 reads "15 por ciento sobre los
ingresos integros satisfechos", and the rate itself is read here from the
registry parameter catalogue rather than restated as a literal. The 1060 is
what the payer transfers, by the settlement identity ``cash = total -
retencion``.

That makes the retencion assertion an independent cross-check rather than a
restatement. The engine derives the withholding one way only -- invoice gross
minus cash, 1210 - 1060 -- and never applies a rate. The expectation below
arrives the other way, from the statutory rate on the statutory base. Two
unrelated routes landing on 150 is the grounding; had the test recomputed
1210 - 1060 it would have agreed with the engine by construction and proved
nothing.

The second half is the same invoice with its base unrecorded, which is the
common state of a clean bank import. It is not a degraded version of the first:
casilla 01 receives 1060 instead of 1000, so the taxpayer OVER-declares by 60
while the 150 credit disappears. Both movements are visible only because the
ungrounded screen fires, which is the property pinned here.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from .....application.aggregation import aggregate_renta_income_ledger
from .....core import CasillaId, Period, validated_casilla_id
from .....core.aggregation import LedgerIncomeGrounding, LedgerWithholdingDerivation
from ....iva.schema import IvaCategory
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

# The invoice, stated once from the document and the two cited rates.
_BASE = Decimal("1000.00")
_CUOTA = Decimal("210.00")
_IVA_RATE = Decimal("0.21")
_TOTAL = _BASE + _CUOTA
_RETENCION = Decimal("150.00")
_CASH = _TOTAL - _RETENCION

_INGRESOS_BINDING = "modelo-130-actividad-economica-ingresos-cumulative"
_RETENCIONES_BINDING = "modelo-130-actividad-economica-retenciones-cumulative"
_TAXABLE_BASE_BINDING = "modelo-130-actividad-economica-ingresos-taxable-base-cumulative"

_FILING_YEAR = 2026
_PERIOD = Period.from_year_and_code(_FILING_YEAR, "1T")
_VALUE_DATE = date(_FILING_YEAR, 2, 16)
_BUCKET = "46f1b1e3-e3c7-4522-8f3b-0689c804cd52"  # was 'bucket-oracle-rated'

_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")


def _invoice_row(*, declares_substrate: bool, cash: Decimal | None = None) -> Transaction:
    """The one invoice as a ledger row, with or without its recorded substrate.

    Both variants describe the SAME real invoice and carry the same bank
    movement; they differ only in whether the base and cuota were ever recorded
    against it. That is the single-field difference the chain has to survive.
    """
    raw = RawTransaction(
        provider_transaction_id="rated-professional-invoice",
        booked_date=_VALUE_DATE,
        value_date=_VALUE_DATE,
        amount=_CASH if cash is None else cash,
        currency="EUR",
        counterparty="Cliente Profesional SL",
        description="Servicios profesionales F-2026-011",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=11,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(_FILING_YEAR, 4, 6, 9, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": "F-2026-011"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.INCOMING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "business_classification": BusinessClassification.BUSINESS,
            "taxable_base": _BASE if declares_substrate else None,
            "iva_amount": _CUOTA if declares_substrate else None,
            "iva_rate": _IVA_RATE if declares_substrate else None,
            "iva_category": IvaCategory.DOMESTIC_GENERAL if declares_substrate else None,
            "irpf_category": "actividad_economica",
            "lifecycle_state": TransactionLifecycleState.ACTIVE,
            "classified_at": datetime(_FILING_YEAR, 4, 6, 10, 0, tzinfo=UTC),
            "classified_by": "manual",
        },
    )


def _aggregated(*, declares_substrate: bool, cash: Decimal | None = None):
    """Drive one invoice through the production aggregation link of the chain.

    Deliberately runs the real classifier rather than hand-building an
    observation: the grounding marker and the withholding derivation are set
    there, so constructing the observation here would skip exactly the link
    this module exists to cover.
    """
    return aggregate_renta_income_ledger(
        TransactionCatalogue.from_transactions((_invoice_row(declares_substrate=declares_substrate, cash=cash),)),
        bucket_id=_BUCKET,
        period=_PERIOD,
    )


def test_the_worked_example_figures_satisfy_the_invoice_identity() -> None:
    """The scenario's own arithmetic, before any engine sees it.

    The expectations every assertion below rests on are only external
    authority if they hold together as one document. Stating the two
    identities here means a later edit that adjusts one figure and forgets
    another reddens at the source instead of quietly re-grounding the whole
    module on a document that never existed.
    """
    assert _TOTAL == _BASE + _CUOTA
    assert _CASH == _TOTAL - _RETENCION
    assert (_BASE * _IVA_RATE).quantize(Decimal("0.01")) == _CUOTA


def test_the_retencion_expectation_is_the_statutory_rate_not_the_engine_route() -> None:
    """150 is 15 % of the base, read from the registry, not gross minus cash.

    The engine only ever computes ``gross - cash``. If this module expected
    that same subtraction it would agree with the engine whatever the engine
    did. The expectation is therefore anchored on the RIRPF art. 95.1 general
    rate as the registry publishes it, applied to the ingresos integros the
    article names as the base -- and the fact that the two routes meet is what
    the assertions further down are entitled to rely on.
    """
    statutory = (_BASE * load_retencion_actividades_rates().general_rate).quantize(Decimal("0.01"))

    assert statutory == _RETENCION
    assert statutory != (_TOTAL * load_retencion_actividades_rates().general_rate).quantize(Decimal("0.01")), (
        "the retencion base is the base imponible, never the IVA-inclusive total"
    )


def test_the_declared_invoice_reaches_casilla_01_as_its_published_base() -> None:
    """Casilla 01 receives 1000: the ingresos integros, not the gross, not the cash."""
    revision = modelo_130_revision()
    aggregation = _aggregated(declares_substrate=True)

    assert aggregation.issues == ()
    assert len(aggregation.observations) == 1
    observation = aggregation.observations[0]
    assert observation.grounding is LedgerIncomeGrounding.SUBSTRATE_DECLARED
    assert observation.withheld_derivation is LedgerWithholdingDerivation.INFERRED_FROM_DECLARED_CUOTA

    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, aggregation.observations)

    assert resolved[_INGRESOS_BINDING] == _BASE
    assert resolved[_INGRESOS_BINDING] != _TOTAL, "IVA repercutido is not an ingreso of the issuer"
    assert resolved[_INGRESOS_BINDING] != _CASH, "casilla 01 is pre-retencion, not what the bank credited"
    assert resolved[_TAXABLE_BASE_BINDING] == _BASE


def test_the_declared_invoice_reaches_the_retenciones_casilla_at_the_statutory_figure() -> None:
    """The withheld binding resolves to the statutory 15 % of the base.

    The engine reached 150 by subtracting cash from gross; the expectation
    reached it from RIRPF art. 95.1. Asserting the resolved binding equals the
    statutory product is the independent check -- an engine that inferred from
    the IVA-inclusive total, or that inverted a rate off the cash, would land
    somewhere else.
    """
    revision = modelo_130_revision()
    aggregation = _aggregated(declares_substrate=True)

    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, aggregation.observations)
    statutory = (_BASE * load_retencion_actividades_rates().general_rate).quantize(Decimal("0.01"))

    rate = load_retencion_actividades_rates().general_rate

    assert resolved[_RETENCIONES_BINDING] == statutory
    assert resolved[_RETENCIONES_BINDING] == _RETENCION
    assert resolved[_RETENCIONES_BINDING] != (_TOTAL * rate).quantize(Decimal("0.01")), (
        "withholding on the IVA-inclusive total would over-state the credit"
    )
    assert resolved[_RETENCIONES_BINDING] != (_CASH / (Decimal("1") - rate) - _CASH).quantize(Decimal("0.01")), (
        "the base is never reconstructed from the cash by assuming a rate"
    )


def test_the_declared_invoice_raises_no_ungrounded_advisory() -> None:
    """A fully declared invoice must not fire the advisory.

    The advisory only earns operator attention if every fire is a real
    ungrounded contribution; a row that declared everything the casilla needs
    has nothing to report, and a screen that fired here would train the
    operator to ignore the case below.
    """
    revision = modelo_130_revision()
    aggregation = _aggregated(declares_substrate=True)

    screened = ungrounded_ledger_renta_income_observations(revision, aggregation.observations)

    assert screened.observations == ()


def test_the_unrecorded_invoice_over_declares_casilla_01_and_loses_its_credit() -> None:
    """One missing field moves casilla 01 up by 60 and destroys the 150 credit.

    This is the rated invoice's error direction, and it is the OPPOSITE of the
    exempt case: the cash the bank credited (1060) exceeds the ingresos
    integros (1000) because the IVA collected on Hacienda's behalf outweighs
    the retencion withheld. So the taxpayer over-declares income AND
    under-claims the credit at once -- 210 worse off on one invoice, in two
    directions nothing would otherwise watch.
    """
    revision = modelo_130_revision()
    aggregation = _aggregated(declares_substrate=False)

    assert len(aggregation.observations) == 1
    observation = aggregation.observations[0]
    assert observation.grounding is LedgerIncomeGrounding.CASH_FALLBACK
    assert observation.withheld_derivation is LedgerWithholdingDerivation.NO_SUBSTRATE

    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, aggregation.observations)

    assert resolved[_INGRESOS_BINDING] == _CASH
    assert resolved[_INGRESOS_BINDING] - _BASE == Decimal("60.00")
    assert resolved[_RETENCIONES_BINDING] == Decimal("0")
    assert resolved[_TAXABLE_BASE_BINDING] == Decimal("0")


def test_the_unrecorded_invoice_is_surfaced_rather_than_silently_folded() -> None:
    """The cash-fallback contribution fires the advisory, naming both facts.

    The fallback is deliberately kept -- dropping the row would under-declare
    by its whole value, strictly worse than mis-measuring it -- so visibility
    is the entire safeguard. The screen must name the row and both base-reading
    facts it disturbed: cash folded into ``ingresos_integros_sum`` AND nothing
    contributed to ``taxable_base_sum``.
    """
    revision = modelo_130_revision()
    aggregation = _aggregated(declares_substrate=False)

    screened = ungrounded_ledger_renta_income_observations(revision, aggregation.observations)

    assert len(screened.observations) == 1
    assert screened.observations[0].target_casilla_id == _M130_INGRESOS_CASILLA
    assert screened.facts == frozenset({"ingresos_integros_sum", "taxable_base_sum"})


# --------------------------------------------------------------------------- #
# The same chain at a rate BELOW the inference bound
# --------------------------------------------------------------------------- #
#
# Every case above withholds at the RIRPF art. 95.1 general rate, which is also
# the ceiling the withheld inference refuses to exceed. Calibrated at one point
# only, and that point is the bound itself: an inference that clamped every
# result to its maximum would satisfy all of them.
#
# So the chain is driven once more at the art. 95.1 second-paragraph rate for
# the periodo of inicio de actividades and the two following. Same invoice,
# same base, same cuota -- only the withheld figure and the cash it implies
# differ, which is what a real practitioner in their first years actually
# invoices.

_INICIO_RETENCION = (_BASE * load_retencion_actividades_rates().inicio_actividad_rate).quantize(Decimal("0.01"))
_INICIO_CASH = _TOTAL - _INICIO_RETENCION


def test_the_inicio_de_actividad_rate_is_genuinely_below_the_general_rate() -> None:
    """The two registry rates differ, so the case below calibrates a second point.

    Cheap, and it is what makes the case below more than a duplicate: if the registry ever
    published the same figure for both, this case would silently stop testing a
    sub-cap path while still passing, and the calibration claim would be false.
    """
    rates = load_retencion_actividades_rates()

    assert rates.inicio_actividad_rate < rates.general_rate
    assert _INICIO_RETENCION < _RETENCION
    assert _INICIO_CASH > _CASH


def test_a_sub_cap_withholding_is_inferred_at_its_own_rate_not_clamped_to_the_bound() -> None:
    """The inference reports what was withheld, not the most it would accept.

    This is the calibration the module lacked. The general-rate cases sit
    exactly on the bound, so a derivation that returned its ceiling whenever
    the arithmetic ran would pass every one of them. Here the correct answer is
    strictly below the ceiling, and returning the ceiling is wrong by 80 euros
    on a single invoice -- an over-claimed credit against the pago fraccionado.
    """
    aggregation = _aggregated(declares_substrate=True, cash=_INICIO_CASH)

    observation = aggregation.observations[0]

    assert observation.withheld_amount == _INICIO_RETENCION
    assert observation.withheld_amount != _RETENCION, "the bound is a ceiling, never the answer"
    assert observation.taxable_base_amount == _BASE


def test_the_sub_cap_invoice_reaches_the_retenciones_casilla_at_its_own_statutory_figure() -> None:
    """The filed casilla carries the 7 % figure, resolved through the registry.

    Asserted against the statutory product rather than against the engine's
    derivation, so the two routes to 70 stay independent: one from RIRPF art.
    95.1 second paragraph, one from gross minus cash. Casilla 01 is asserted
    unchanged, because the rate the payer applied does not alter the ingresos
    integros the article names as the base.
    """
    revision = modelo_130_revision()
    aggregation = _aggregated(declares_substrate=True, cash=_INICIO_CASH)

    resolved = resolve_ledger_renta_income_aggregation_binding_values(revision, aggregation.observations)
    statutory = (_BASE * load_retencion_actividades_rates().inicio_actividad_rate).quantize(Decimal("0.01"))

    assert resolved[_RETENCIONES_BINDING] == statutory
    assert resolved[_INGRESOS_BINDING] == _BASE
