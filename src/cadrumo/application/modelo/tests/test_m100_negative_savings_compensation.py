"""The negative savings balances pending from earlier ejercicios are compensated as Ley 35/2006 art. 49.2 orders.

Each pending balance first offsets the positive balance of its own kind (net
gains and losses, or net movable-capital income), oldest ejercicio first; what
is left then offsets the other kind's positive balance up to 25 per cent of it,
less whatever that 25 per cent already absorbed of the current year. A balance
four ejercicios old lapses unapplied; a younger one carries forward.

The oracle is the worked example of the AEAT Manual práctico de Renta 2025
(ahorro, "Compensación de las partidas negativas pendientes de ejercicios
anteriores"): gains 5 600 and losses 1 600 of the year, a negative movable-capital
yield of 800, and pending balances of gains and losses of 700 (fourth previous
ejercicio) and 2 100 (third), and of movable-capital income of 500 (fourth).
The manual applies 700 and 2 100 in full, then 200 of the 500 against the
gains (the 25 per cent cap of 1 000 less the 800 already used), and 300 lapses.

The C.3 boxes the filer applies are entered by hand; the registry computes each
box's maximum and blocks a figure that differs. Where two balances of the same
kind compete for a capacity that does not cover both, the order of the origin
years changes the figures and the registry blocks filing on that.

Real behaviour throughout: the published Modelo 100 revision for every year
the support envelope admits, the production formula runtime and the production
verification predicate evaluator.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

import pytest

from ....core.aggregation import BindingSourceKind
from ....core.authority_grade import RegistryAuthorityGrade
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ....domain.calculations.registry.errors import FilingYearOutsideSupportEnvelopeError
from ....domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.tests.modelo_100_registry_support import neutral_binding_values
from ....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_supported_filing_years,
)
from ....domain.modelos.verification_report import ModeloVerificationFinding, ModeloVerificationFindingKind
from ..verification_predicates import evaluate_verification_predicates
from .verification_substance_fixtures import workflow_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("authority_operation")]


def _box(token: str) -> CasillaId:
    return validated_casilla_id(token, surface="test_m100_negative_savings_compensation")


_GAINS = _box("0392")
_LOSSES = _box("0395")
# Interest, dividends and their expenses come only from linked ledger rows and payer records, so the
# scenario states its negative movable-capital yield in other financial assets, a leaf no source binds.
_OTHER_FINANCIAL_ASSETS = _box("0031")
_SAVINGS_BASE = _box("0460")

# Step 1: each kind's pending balance against its own positive balance, by origin year.
_GAINS_EM4_STEP1, _GAINS_EM3_STEP1 = _box("0439"), _box("0440")
_CAPITAL_EM4_STEP1 = _box("0449")
# Step 2: the rest against the other kind's positive balance, within the 25 per cent cap.
_CAPITAL_EM4_STEP2 = _box("0443")
_GAINS_EM4_STEP2, _GAINS_EM3_STEP2 = _box("0453"), _box("0454")

# Anexo C.3: opening balance, applied this year, pending at the end.
_GAINS_EM4_APPLIED = _box("1260")
_GAINS_EM3_OPENING, _GAINS_EM3_APPLIED, _GAINS_EM3_FORWARD = _box("1261"), _box("1262"), _box("1263")
_CAPITAL_EM4_OPENING, _CAPITAL_EM4_APPLIED = _box("1272"), _box("1273")

_GAINS_EM4 = "renta-saldo-negativo-gyp-ahorro-em4-pendiente-inicio"
_GAINS_EM3 = "renta-saldo-negativo-gyp-ahorro-em3-pendiente-inicio"
_CAPITAL_EM4 = "renta-saldo-negativo-rcm-ahorro-em4-pendiente-inicio"

#: The manual's current-year figures: gains 5 600, losses 1 600, a movable-capital yield of -800.
_MANUAL_YEAR: Mapping[CasillaId, Decimal] = {
    _GAINS: Decimal("5600"),
    _LOSSES: Decimal("1600"),
    _OTHER_FINANCIAL_ASSETS: Decimal("-800"),
}
#: The manual's pending balances: gains and losses 700 and 2 100, movable capital 500.
_MANUAL_PENDING: Mapping[str, Decimal] = {
    _GAINS_EM4: Decimal("700"),
    _GAINS_EM3: Decimal("2100"),
    _CAPITAL_EM4: Decimal("500"),
}
#: What the manual applies, entered in the boxes the filer fills.
_MANUAL_APPLIED: Mapping[CasillaId, Decimal] = {
    _GAINS_EM4_STEP1: Decimal("700"),
    _GAINS_EM3_STEP1: Decimal("2100"),
    _CAPITAL_EM4_STEP2: Decimal("200"),
}


def _renta_years() -> tuple[int, ...]:
    """The Modelo 100 years the envelope admits at calculation grade."""
    support = published_supported_filing_years()
    assert support is not None
    admitted: list[int] = []
    for year in sorted(support.years):
        try:
            _snapshot(year)
        except FilingYearOutsideSupportEnvelopeError:
            continue
        admitted.append(year)
    return tuple(admitted)


def _snapshot(year: int) -> RegistrySnapshot:
    return published_snapshot("100", filing_year=year, period="0A", grade=RegistryAuthorityGrade.CALCULATION)


def _calculate(
    snapshot: RegistrySnapshot,
    year: int,
    inputs: Mapping[CasillaId, Decimal],
    pending: Mapping[str, Decimal],
) -> dict[CasillaId, Decimal]:
    decimals, booleans, dates, enums = neutral_binding_values(
        binding for binding in snapshot.revision.bindings if binding.source is not BindingSourceKind.RELATION_PREFILL
    )
    booleans["renta-modelo-100-estimacion-directa-es-normal"] = True
    decimals |= {"renta-profile-declaration-type": Decimal(1), **pending}
    result = calculate_registry_snapshot(
        snapshot,
        inputs={**inputs, **resolve_available_bound_inputs_by_casilla_id(snapshot.revision, decimals)},
        date_context={"filing_period": date(year, 12, 31)},
        binding_values=decimals,
        enum_binding_values=enums,
        relation_values={
            "renta-modelo-130-pagos-fraccionados": Decimal(0),
            "renta-modelo-131-pagos-fraccionados": Decimal(0),
        },
        date_binding_values=dates,
        boolean_binding_values=booleans,
    )
    return dict(result.values)


def _compensation_findings(
    snapshot: RegistrySnapshot, values: Mapping[CasillaId, Decimal]
) -> list[ModeloVerificationFinding]:
    """The findings of the registry's own art. 49.2 compensation gates, and of no other predicate."""
    predicates = tuple(
        predicate
        for predicate in snapshot.revision.verification_predicates
        if "compensacion-saldo-neg-" in predicate.predicate_id
    )
    assert predicates
    return evaluate_verification_predicates(predicates, values, workflow_profile())


@pytest.mark.parametrize("year", _renta_years())
def test_the_manual_worked_example_compensates_and_lapses_as_the_manual_does(year: int) -> None:
    snapshot = _snapshot(year)
    values = _calculate(snapshot, year, {**_MANUAL_YEAR, **_MANUAL_APPLIED}, _MANUAL_PENDING)

    # The maxima the registry computes are the manual's figures.
    assert values[_box("saldo-neg-gyp-ahorro-em4-paso1-maxima")] == Decimal("700")
    assert values[_box("saldo-neg-gyp-ahorro-em3-paso1-maxima")] == Decimal("2100")
    assert values[_box("saldo-neg-rcm-ahorro-em4-paso1-maxima")] == Decimal("0")
    assert values[_box("saldo-neg-rcm-ahorro-em4-paso2-maxima")] == Decimal("200")
    # Anexo C.3: 700 and 2 100 applied, nothing left of 2 100; 200 of the 500 applied and the rest lapses.
    assert values[_GAINS_EM4_APPLIED] == Decimal("700")
    assert values[_GAINS_EM3_OPENING] == Decimal("2100")
    assert values[_GAINS_EM3_APPLIED] == Decimal("2100")
    assert values[_GAINS_EM3_FORWARD] == Decimal("0")
    assert values[_CAPITAL_EM4_OPENING] == Decimal("500")
    assert values[_CAPITAL_EM4_APPLIED] == Decimal("200")
    # 4 000 net gains - 800 current yield - 2 800 - 200 of earlier balances.
    assert values[_SAVINGS_BASE] == Decimal("200")
    assert _compensation_findings(snapshot, values) == []


@pytest.mark.parametrize("year", _renta_years())
def test_an_applied_figure_other_than_the_maximum_blocks(year: int) -> None:
    snapshot = _snapshot(year)
    applied = {**_MANUAL_APPLIED, _CAPITAL_EM4_STEP2: Decimal("300")}
    values = _calculate(snapshot, year, {**_MANUAL_YEAR, **applied}, _MANUAL_PENDING)

    findings = _compensation_findings(snapshot, values)
    assert findings
    assert all(finding.kind is ModeloVerificationFindingKind.BLOCKING_RULE for finding in findings)
    assert {finding.message_facts["predicate_id"] for finding in findings} == {
        next(
            predicate.predicate_id
            for predicate in snapshot.revision.verification_predicates
            if predicate.expression
            == 'application_equals_present_maximum(["0443", "saldo-neg-rcm-ahorro-em4-paso2-maxima"])'
        )
    }


@pytest.mark.parametrize("year", _renta_years())
def test_a_single_balance_larger_than_the_capacity_applies_the_capacity_and_carries_the_rest(year: int) -> None:
    snapshot = _snapshot(year)
    # Net gains 4 000, no current-year movable-capital loss: 4 000 of capacity for 5 000 pending.
    year_figures = {_GAINS: Decimal("5600"), _LOSSES: Decimal("1600")}
    values = _calculate(
        snapshot, year, {**year_figures, _GAINS_EM3_STEP1: Decimal("4000")}, {_GAINS_EM3: Decimal("5000")}
    )

    assert values[_box("saldo-neg-gyp-ahorro-em3-paso1-maxima")] == Decimal("4000")
    assert values[_GAINS_EM3_APPLIED] == Decimal("4000")
    assert values[_GAINS_EM3_FORWARD] == Decimal("1000")
    assert values[_SAVINGS_BASE] == Decimal("0")
    # One balance alone: its origin year has nothing to be ordered against.
    assert _compensation_findings(snapshot, values) == []


@pytest.mark.parametrize("year", _renta_years())
def test_two_balances_the_capacity_covers_are_both_applied_without_an_order_question(year: int) -> None:
    snapshot = _snapshot(year)
    pending = {_GAINS_EM4: Decimal("1500"), _GAINS_EM3: Decimal("2000")}
    applied = {_GAINS_EM4_STEP1: Decimal("1500"), _GAINS_EM3_STEP1: Decimal("2000")}
    values = _calculate(snapshot, year, {_GAINS: Decimal("5600"), _LOSSES: Decimal("1600"), **applied}, pending)

    assert values[_SAVINGS_BASE] == Decimal("500")
    assert _compensation_findings(snapshot, values) == []


@pytest.mark.parametrize("year", _renta_years())
def test_two_balances_competing_for_a_capacity_that_does_not_cover_both_block_on_their_order(year: int) -> None:
    snapshot = _snapshot(year)
    pending = {_GAINS_EM4: Decimal("3000"), _GAINS_EM3: Decimal("2000")}
    # The oldest first would apply 3 000 and 1 000; another order gives other figures.
    applied = {_GAINS_EM4_STEP1: Decimal("3000"), _GAINS_EM3_STEP1: Decimal("1000")}
    values = _calculate(snapshot, year, {_GAINS: Decimal("5600"), _LOSSES: Decimal("1600"), **applied}, pending)

    findings = _compensation_findings(snapshot, values)
    unsettled = [
        finding
        for finding in findings
        if finding.message_locale_key == "application.modelo.findings.application_order_unsettled"
    ]
    assert len(unsettled) == 1, findings
    assert unsettled[0].kind is ModeloVerificationFindingKind.BLOCKING_RULE
    assert unsettled[0].message_facts["capacity"] == Decimal("4000")
    assert unsettled[0].message_facts["pending_total"] == Decimal("5000")
