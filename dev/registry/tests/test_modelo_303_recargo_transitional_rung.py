"""Modelo 303 recargo cuota lands in the rung the design states for its applied rate.

The 2023 design prints one rung [16]/[17]/[18] for the recargo of the 0 %, 0,5 % and
0,62 % tiers and a separate rung [19]/[20]/[21] whose Tipo is the constant "00140". The
5 % and 7,5 % transitional reducido recargo (0,62 % and 1 %) therefore belongs in [18]
and the 10 % reducido recargo in [21]. From 10/4T of the year the second tranche opens
the 4 % recargo moves to [168]/[169]/[170] (Nota 10).

Every date below is read from the authored recargo schedule, which carries each rate's own
legal window, and every year is enumerated from the registry's support envelope. The
expected box comes from the design notes above, never from the registry under test.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.facts.payloads import MappingFactPayload
from cadrumo.domain.calculations.registry.facts.schema import GovernedFact
from cadrumo.domain.iva.recargo_equivalencia import IVA_RECARGO_FACT_ID
from cadrumo.domain.iva.schema import IvaCategory, IvaRateKind

from ..compiler.fact_loader import load_governed_facts
from .ledger_iva_aggregation_support import (
    calculate_303_from_observations,
    ledger_iva_aggregation_category,
    ledger_iva_aggregation_observation,
    ledger_iva_aggregation_rate_kind,
)
from .profile_schema_support import committed_supported_filing_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]

_SUPPORT = committed_supported_filing_years()
_RUNG_0_050_062 = validated_casilla_id("18", surface="_RUNG_0_050_062")
_RUNG_ORDINARY_REDUCED = validated_casilla_id("21", surface="_RUNG_ORDINARY_REDUCED")
_RUNG_SUPER_REDUCED_LATE = validated_casilla_id("170", surface="_RUNG_SUPER_REDUCED_LATE")


def _schedule() -> GovernedFact:
    return next(
        fact
        for fact in load_governed_facts(bundled_path("registry", "aeat", "facts"))
        if fact.fact_id == IVA_RECARGO_FACT_ID
    )


def _window(applied_rate: Decimal) -> tuple[date, date | None]:
    (variant,) = (item for item in _schedule().variants if Decimal(str(item.selectors[0].value)) == applied_rate)
    assert variant.valid_from is not None
    return variant.valid_from, variant.valid_to


def _recargo_rate(applied_rate: Decimal) -> Decimal:
    (variant,) = (item for item in _schedule().variants if Decimal(str(item.selectors[0].value)) == applied_rate)
    payload = variant.payload
    assert isinstance(payload, MappingFactPayload)
    return Decimal(str(next(entry.value for entry in payload.entries if entry.key == "recargo_rate")))


def _period_of(day: date) -> str:
    return f"{(day.month - 1) // 3 + 1}T"


def _recargo_boxes(*, day: date, applied_rate: Decimal, category: str, rate_kind: str) -> dict[str, Decimal]:
    base = Decimal("1000")
    observation = ledger_iva_aggregation_observation(
        txn_date=day,
        category=ledger_iva_aggregation_category(category, effective_date=day),
        rate_kind=ledger_iva_aggregation_rate_kind(rate_kind, effective_date=day),
        applied_rate=applied_rate,
        base=base,
        iva=base * applied_rate,
        recargo=base * _recargo_rate(applied_rate),
    )
    result = calculate_303_from_observations(
        filing_year=day.year,
        period=_period_of(day),
        observations=(observation,),
    )
    return {
        str(box): result.values.get(box, Decimal("0"))
        for box in (_RUNG_0_050_062, _RUNG_ORDINARY_REDUCED, _RUNG_SUPER_REDUCED_LATE)
    }


def _transitional_days(applied_rate: Decimal) -> tuple[date, ...]:
    start, end = _window(applied_rate)
    assert end is not None
    return (start, end)


@pytest.mark.parametrize("applied_rate", [Decimal("0.05"), Decimal("0.075")])
def test_transitional_reducido_recargo_goes_to_the_zero_050_062_rung_not_the_ordinary_reducido_rung(
    applied_rate: Decimal,
) -> None:
    expected = Decimal("1000") * _recargo_rate(applied_rate)
    for day in _transitional_days(applied_rate):
        boxes = _recargo_boxes(day=day, applied_rate=applied_rate, category="domestic_reduced", rate_kind="reduced")
        assert boxes[str(_RUNG_0_050_062)] == expected, (day, boxes)
        assert boxes[str(_RUNG_ORDINARY_REDUCED)] == 0, (day, boxes)
        assert boxes[str(_RUNG_SUPER_REDUCED_LATE)] == 0, (day, boxes)


@pytest.mark.parametrize("filing_year", _SUPPORT.years)
def test_ordinary_reducido_recargo_goes_to_its_own_rung_in_every_supported_year(filing_year: int) -> None:
    day = date(filing_year, 5, 15)
    boxes = _recargo_boxes(day=day, applied_rate=Decimal("0.10"), category="domestic_reduced", rate_kind="reduced")
    assert boxes[str(_RUNG_ORDINARY_REDUCED)] == Decimal("1000") * _recargo_rate(Decimal("0.10"))
    assert boxes[str(_RUNG_0_050_062)] == 0
    assert boxes[str(_RUNG_SUPER_REDUCED_LATE)] == 0


@pytest.mark.parametrize("filing_year", _SUPPORT.years)
@pytest.mark.parametrize("month", [5, 11])
def test_super_reducido_recargo_follows_the_design_rung_for_its_date(filing_year: int, month: int) -> None:
    day = date(filing_year, month, 15)
    second_tranche_start, _ = _window(Decimal("0.075"))
    expected_rung = _RUNG_SUPER_REDUCED_LATE if day >= second_tranche_start else _RUNG_0_050_062
    boxes = _recargo_boxes(
        day=day, applied_rate=Decimal("0.04"), category="domestic_super_reduced", rate_kind="super_reduced"
    )
    expected = Decimal("1000") * _recargo_rate(Decimal("0.04"))
    assert {box: value for box, value in boxes.items() if value} == {str(expected_rung): expected}


def test_the_rate_vocabulary_used_here_is_registered() -> None:
    assert IvaCategory("domestic_reduced")
    assert IvaRateKind("reduced")
