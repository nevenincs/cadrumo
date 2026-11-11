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

from ....core.i18n.translatable import Translatable as tr
from ...calculations.registry.authority import PinnedAuthorityOperation
from ...calculations.registry.tests.authored_editions import filing_year_envelope, manual_edition_matches
from ..proportionality import (
    CategoryCitation,
    CategoryCitationSource,
    ProportionalityRule,
    StatutoryCapAmount,
    parse_http_url,
)
from ..proportionality_catalogue import require_proportionality_kind, require_statutory_cap_period
from ..registry import category_profile_years, load_category_profiles, resolve_category_profiles
from ..spending_category_catalogue import require_spending_category

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("operation")]

_ENVELOPE = filing_year_envelope()

#: The sentence each Manual practico Renta edition prints for its ejercicio, in the
#: normalised corpus text: the cuota maxima, then AEAT's own method -- the
#: contingencias comunes rate times twelve monthly maximum bases.
_MANUAL_CUOTA_MAXIMA = (
    r"la cuota maxima por contingencias comunes en (?P<ejercicio>\d{4}) es de (?P<cuota>[\d.]+,\d{2}) euros "
    r"\[(?P<tipo>\d+,\d+) x \((?P<base>[\d.]+,\d{2}) x 12\)\]"
)

#: The monthly maximum contribution base Orden PJC/297/2026 fixes for the RETA. No
#: bundled manual edition prints that ejercicio yet, so its cuota maxima is derived
#: from this base by the method the newest manual prints.
_ORDEN_PJC_297_2026_MONTHLY_MAXIMUM_BASE = Decimal("5101.20")


def _printed_amount(text: str) -> Decimal:
    """Read an amount the manual prints with Spanish grouping and decimal comma."""
    return Decimal(text.replace(".", "").replace(",", "."))


def _cuota_by_method(rate: Decimal, monthly_base: Decimal) -> Decimal:
    return (rate * monthly_base * 12).quantize(Decimal("0.01"))


def _manual_published_cuota_maxima() -> tuple[dict[int, Decimal], Decimal]:
    """The cuota maxima each bundled manual edition prints, and the rate the newest prints.

    Each edition prints the figure for its own ejercicio together with the
    computation that yields it, so the figure is checked against that printed
    method before it is trusted as the oracle.
    """
    printed: dict[int, Decimal] = {}
    rate = Decimal(0)
    for edition, match in manual_edition_matches("renta", _MANUAL_CUOTA_MAXIMA).items():
        assert int(match["ejercicio"]) == edition, f"manual edition {edition} prints another ejercicio's cuota"
        rate = _printed_amount(match["tipo"])
        cuota = _printed_amount(match["cuota"])
        assert cuota == _cuota_by_method(rate, _printed_amount(match["base"])), f"edition {edition} misprints"
        printed[edition] = cuota
    assert printed, "no bundled Manual practico Renta edition prints the cuota maxima"
    return printed, rate


def _aeat_published_cuota_maxima(rule: ProportionalityRule) -> dict[int, Decimal]:
    """The figure AEAT publishes for each ejercicio the shipped schedule carries.

    A year a bundled manual edition prints takes the manual's figure. The one
    schedule year after the newest printing edition takes the figure derived from
    Orden PJC/297/2026 by the method that edition prints. Any other schedule year
    has no published figure here, and is reported rather than borrowing one.
    """
    printed, rate = _manual_published_cuota_maxima()
    newest_printed = max(printed)
    published = {year: cuota for year, cuota in printed.items() if year in _ENVELOPE.years}
    unprinted = sorted(
        amount.valid_from.year for amount in rule.statutory_cap_schedule if amount.valid_from.year not in printed
    )
    assert unprinted in ([], [newest_printed + 1]), (
        f"schedule years {unprinted} have neither a manual figure nor the Orden PJC/297/2026 derivation"
    )
    for year in unprinted:
        published[year] = _cuota_by_method(rate, _ORDEN_PJC_297_2026_MONTHLY_MAXIMUM_BASE)
    return published


def _shipped_mutualidad_rule(operation: PinnedAuthorityOperation) -> ProportionalityRule:
    return load_category_profiles(operation=operation)[
        require_spending_category("mutualidad_alternativa")
    ].proportionality


def _citation() -> CategoryCitation:
    return CategoryCitation(
        source=CategoryCitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 30.2.1.a",
        url=parse_http_url("https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764"),
        quote=tr("Texto autoritativo de prueba."),
        legal_ref="ley-35-2006:art-30",
        valid_from=date(_ENVELOPE.floor, 1, 1),
        valid_to=date(_ENVELOPE.horizon, 12, 31),
    )


def _rule(schedule: tuple[StatutoryCapAmount, ...], **overrides: object) -> ProportionalityRule:
    payload: dict[str, object] = {
        "kind": require_proportionality_kind("statutory_cap"),
        "statutory_cap_period": require_statutory_cap_period("year_per_person"),
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
    rule = _rule((_amount("14057.40", _ENVELOPE.floor), _amount("16672.66", _ENVELOPE.horizon)))

    assert rule.cap_amount_for_year(_ENVELOPE.floor) == Decimal("14057.40")
    assert rule.cap_amount_for_year(_ENVELOPE.horizon) == Decimal("16672.66")


def test_a_year_the_schedule_does_not_cover_yields_no_amount() -> None:
    """No nearest-year fallback: an ungrounded year has no cap, it does not borrow one."""
    assert _rule((_amount("16672.66", _ENVELOPE.horizon),)).cap_amount_for_year(_ENVELOPE.floor - 1) is None


def test_a_law_fixed_cap_still_answers_without_a_schedule() -> None:
    """The 500 euro seguro limit is genuinely constant and must stay expressible."""
    rule = _rule((), statutory_cap_eur=Decimal("500"))

    assert rule.cap_amount_for_year(_ENVELOPE.floor) == Decimal("500")
    assert rule.cap_amount_for_year(_ENVELOPE.horizon) == Decimal("500")


def test_a_cap_may_not_be_both_law_fixed_and_year_referenced() -> None:
    """DISCRIMINATING: two cap modes is the ambiguity the schedule exists to remove."""
    with pytest.raises(ValidationError, match="one cap mode"):
        _rule((_amount("16672.66", _ENVELOPE.horizon),), statutory_cap_eur=Decimal("15000"))


def test_two_different_amounts_for_one_year_are_refused() -> None:
    """Order-dependent answers are a contradiction, not a preference."""
    with pytest.raises(ValidationError, match=f"two different amounts for {_ENVELOPE.horizon}"):
        _rule((_amount("16672.66", _ENVELOPE.horizon), _amount("15000", _ENVELOPE.horizon)))


def test_a_scheduled_cap_requires_the_period_it_applies_over() -> None:
    with pytest.raises(ValidationError, match="statutory_cap_schedule requires statutory_cap_period"):
        ProportionalityRule.model_validate(
            {
                "kind": require_proportionality_kind("statutory_cap"),
                "statutory_cap_schedule": (_amount("16672.66", _ENVELOPE.horizon),),
                "citations": (_citation(),),
                "notes": tr("Regla de prueba."),
            },
        )


def test_a_schedule_is_refused_outside_a_statutory_cap_rule() -> None:
    with pytest.raises(ValidationError, match="only valid for statutory_cap rules"):
        ProportionalityRule.model_validate(
            {
                "kind": require_proportionality_kind("full_deductible"),
                "statutory_cap_schedule": (_amount("16672.66", _ENVELOPE.horizon),),
                "citations": (_citation(),),
                "notes": tr("Regla de prueba."),
            },
        )


def test_the_shipped_mutualidad_cap_matches_the_figures_aeat_publishes(
    operation: PinnedAuthorityOperation,
) -> None:
    """GROUNDED against external authority, not against the registry's own formula.

    Each expected amount is the figure AEAT prints in the bundled Manual practico
    Renta for that ejercicio (the year no edition prints yet derived from the
    cotizacion orden by AEAT's own method). Every ejercicio of the filing envelope
    a manual prints must be scheduled. If the registry drifts from what AEAT
    publishes, this reds.
    """
    rule = _shipped_mutualidad_rule(operation)

    assert rule.statutory_cap_schedule, "the shipped mutualidad cap carries no schedule; it regressed to a constant"
    assert rule.statutory_cap_eur is None, "a year-referenced cap must not also carry a flat amount"

    published = _aeat_published_cuota_maxima(rule)
    scheduled = {amount.valid_from.year for amount in rule.statutory_cap_schedule}
    assert scheduled <= set(published), f"schedule years {sorted(scheduled - set(published))} are ungrounded"
    for year, expected in published.items():
        assert rule.cap_amount_for_year(year) == expected, f"ejercicio {year} diverges from the AEAT figure"


def test_the_retired_flat_fifteen_thousand_is_not_the_figure_for_any_ejercicio(
    operation: PinnedAuthorityOperation,
) -> None:
    """ANTI-REGRESSION on the specific defect: 15000 was never anybody's cap.

    Pinned deliberately as a literal. If someone reinstates it -- as a constant
    or as a schedule row -- this names exactly what is wrong with it.
    """
    rule = _shipped_mutualidad_rule(operation)
    assert Decimal("15000") not in set(_aeat_published_cuota_maxima(rule).values())

    shipped = {amount.value for amount in rule.statutory_cap_schedule}

    assert Decimal("15000") not in shipped


def test_resolving_a_year_materialises_that_years_cap_and_drops_the_schedule(
    operation: PinnedAuthorityOperation,
) -> None:
    """Consumers read one cap and cannot reach past the resolver for another year's."""
    published = _aeat_published_cuota_maxima(_shipped_mutualidad_rule(operation))
    for year in sorted(category_profile_years(operation=operation)):
        rule = resolve_category_profiles(year, operation=operation)[
            require_spending_category("mutualidad_alternativa")
        ].proportionality

        assert rule.statutory_cap_schedule == ()
        assert rule.statutory_cap_eur == published[year]


def test_a_year_without_a_cap_amount_is_not_reported_as_covered(
    operation: PinnedAuthorityOperation,
) -> None:
    """The corpus may not claim a year it can cite but cannot compute.

    Coverage intersects citation evidence with cap availability, so a profile
    whose schedule stops early stops the corpus rather than resolving to a rule
    with no cap at all.
    """
    grounded = category_profile_years(operation=operation)
    rule = _shipped_mutualidad_rule(operation)

    for year in grounded:
        assert rule.cap_amount_for_year(year) is not None, (
            f"year {year} is reported as grounded but the mutualidad cap has no amount for it"
        )
