"""A statutory cap the law re-fixes each ejercicio carries dated rows, not a constant.

LIRPF art. 30.2.1a caps the deductible mutualidad-alternativa premium at the
cuota maxima por contingencias comunes established "en cada ejercicio economico"
in the RETA. That figure moves every year with the cotizacion orden, so a single
constant cannot express it -- and the registry shipped one anyway: a flat 15000
that matches no ejercicio at all.

The direction of that error is worth naming. Every real year's figure is HIGHER
than 15000, so the constant under-stated the allowance and cost the taxpayer
deduction. Nothing in this repository watches over-payment: it produces a valid
return, no refusal, and no signal. A gate that only watches under-declaration
would never have found it.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.i18n import Translatable as tr
from .._proportionality import (
    CategoryCitation,
    CategoryCitationSource,
    ProportionalityKind,
    ProportionalityRule,
    StatutoryCapAmount,
    StatutoryCapPeriod,
    parse_http_url,
)
from .._registry import category_profile_years, load_category_profiles, resolve_category_profiles
from .._spending_category import SpendingCategory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The amounts AEAT prints in the Manual practico Renta for each ejercicio,
#: with 2026 derived from Orden PJC/297/2026 by AEAT's own published method.
#: These are external authority, not values re-derived from the code under test.
_AEAT_PUBLISHED_CUOTA_MAXIMA = {
    2022: Decimal("14057.40"),
    2023: Decimal("15266.72"),
    2024: Decimal("16030.82"),
    2025: Decimal("16672.66"),
    2026: Decimal("17323.68"),
}


def _citation() -> CategoryCitation:
    return CategoryCitation(
        source=CategoryCitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 30.2.1.a",
        url=parse_http_url("https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764"),
        quote=tr("Texto autoritativo de prueba."),
        legal_ref="ley-35-2006:art-30",
        valid_from=date(2022, 1, 1),
        valid_to=date(2026, 12, 31),
    )


def _rule(schedule: tuple[StatutoryCapAmount, ...], **overrides: object) -> ProportionalityRule:
    payload: dict[str, object] = {
        "kind": ProportionalityKind.STATUTORY_CAP,
        "statutory_cap_period": StatutoryCapPeriod.YEAR_PER_PERSON,
        "statutory_cap_schedule": schedule,
        "citations": (_citation(),),
        "notes": tr("Regla de prueba."),
    }
    payload.update(overrides)
    return ProportionalityRule.model_validate(payload)


def _amount(value: str, year: int) -> StatutoryCapAmount:
    return StatutoryCapAmount(
        value=Decimal(value),
        valid_from=date(year, 1, 1),
        valid_to=date(year, 12, 31),
    )


def test_a_scheduled_cap_answers_the_year_asked_for() -> None:
    rule = _rule((_amount("14057.40", 2022), _amount("16672.66", 2025)))

    assert rule.cap_amount_for_year(2022) == Decimal("14057.40")
    assert rule.cap_amount_for_year(2025) == Decimal("16672.66")


def test_a_year_the_schedule_does_not_cover_yields_no_amount() -> None:
    """No nearest-year fallback: an ungrounded year has no cap, it does not borrow one."""
    assert _rule((_amount("16672.66", 2025),)).cap_amount_for_year(2019) is None


def test_a_law_fixed_cap_still_answers_without_a_schedule() -> None:
    """The 500 euro seguro limit is genuinely constant and must stay expressible."""
    rule = _rule((), statutory_cap_eur=Decimal("500"))

    assert rule.cap_amount_for_year(2022) == Decimal("500")
    assert rule.cap_amount_for_year(2026) == Decimal("500")


def test_a_cap_may_not_be_both_law_fixed_and_year_referenced() -> None:
    """DISCRIMINATING: two cap modes is the ambiguity the schedule exists to remove."""
    with pytest.raises(ValidationError, match="one cap mode"):
        _rule((_amount("16672.66", 2025),), statutory_cap_eur=Decimal("15000"))


def test_two_different_amounts_for_one_year_are_refused() -> None:
    """Order-dependent answers are a contradiction, not a preference."""
    with pytest.raises(ValidationError, match="two different amounts for 2025"):
        _rule((_amount("16672.66", 2025), _amount("15000", 2025)))


def test_a_scheduled_cap_requires_the_period_it_applies_over() -> None:
    with pytest.raises(ValidationError, match="statutory_cap_schedule requires statutory_cap_period"):
        ProportionalityRule.model_validate(
            {
                "kind": ProportionalityKind.STATUTORY_CAP,
                "statutory_cap_schedule": (_amount("16672.66", 2025),),
                "citations": (_citation(),),
                "notes": tr("Regla de prueba."),
            },
        )


def test_a_schedule_is_refused_outside_a_statutory_cap_rule() -> None:
    with pytest.raises(ValidationError, match="only valid for statutory_cap rules"):
        ProportionalityRule.model_validate(
            {
                "kind": ProportionalityKind.FULL_DEDUCTIBLE,
                "statutory_cap_schedule": (_amount("16672.66", 2025),),
                "citations": (_citation(),),
                "notes": tr("Regla de prueba."),
            },
        )


def test_the_shipped_mutualidad_cap_matches_the_figures_aeat_publishes() -> None:
    """GROUNDED against external authority, not against the registry's own formula.

    Each expected amount is the figure AEAT prints in the Manual practico Renta
    for that ejercicio (2026 derived from the cotizacion orden by AEAT's own
    method). If the registry drifts from what AEAT publishes, this reds.
    """
    rule = load_category_profiles()[SpendingCategory.MUTUALIDAD_ALTERNATIVA].proportionality

    assert rule.statutory_cap_schedule, "the shipped mutualidad cap carries no schedule; it regressed to a constant"
    assert rule.statutory_cap_eur is None, "a year-referenced cap must not also carry a flat amount"

    for year, expected in _AEAT_PUBLISHED_CUOTA_MAXIMA.items():
        assert rule.cap_amount_for_year(year) == expected, f"ejercicio {year} diverges from the AEAT figure"


def test_the_retired_flat_fifteen_thousand_is_not_the_figure_for_any_ejercicio() -> None:
    """ANTI-REGRESSION on the specific defect: 15000 was never anybody's cap.

    Pinned deliberately as a literal. If someone reinstates it -- as a constant
    or as a schedule row -- this names exactly what is wrong with it.
    """
    assert Decimal("15000") not in set(_AEAT_PUBLISHED_CUOTA_MAXIMA.values())

    rule = load_category_profiles()[SpendingCategory.MUTUALIDAD_ALTERNATIVA].proportionality
    shipped = {amount.value for amount in rule.statutory_cap_schedule}

    assert Decimal("15000") not in shipped


def test_resolving_a_year_materialises_that_years_cap_and_drops_the_schedule() -> None:
    """Consumers read one cap and cannot reach past the resolver for another year's."""
    for year in sorted(category_profile_years()):
        rule = resolve_category_profiles(year)[SpendingCategory.MUTUALIDAD_ALTERNATIVA].proportionality

        assert rule.statutory_cap_schedule == ()
        assert rule.statutory_cap_eur == _AEAT_PUBLISHED_CUOTA_MAXIMA[year]


def test_a_year_without_a_cap_amount_is_not_reported_as_covered() -> None:
    """The corpus may not claim a year it can cite but cannot compute.

    Coverage intersects citation evidence with cap availability, so a profile
    whose schedule stops early stops the corpus rather than resolving to a rule
    with no cap at all.
    """
    grounded = category_profile_years()
    rule = load_category_profiles()[SpendingCategory.MUTUALIDAD_ALTERNATIVA].proportionality

    for year in grounded:
        assert rule.cap_amount_for_year(year) is not None, (
            f"year {year} is reported as grounded but the mutualidad cap has no amount for it"
        )
