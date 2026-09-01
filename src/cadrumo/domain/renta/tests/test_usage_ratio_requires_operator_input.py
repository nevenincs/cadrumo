"""A usage-ratio deduction needs the taxpayer's own proportion, never a stand-in.

LIRPF art. 30.2.5.b, verbatim from the bundled consolidated corpus:

    b) En los casos en que el contribuyente afecte parcialmente su vivienda habitual
    al desarrollo de la actividad económica, los gastos de suministros de dicha
    vivienda, tales como agua, gas, electricidad, telefonía e Internet, en el
    porcentaje resultante de aplicar el 30 por ciento a la proporción existente entre
    los metros cuadrados de la vivienda destinados a la actividad respecto a su
    superficie total, salvo que se pruebe un porcentaje superior o inferior.

The deductible percentage is a PRODUCT of two factors: the statutory 30 per cent and
the taxpayer's own measured area proportion. The article supplies the first and
nothing supplies the second -- it is a fact about one dwelling, which is why the
sentence ends by inviting proof of a different figure rather than naming a fallback.

Five categories shipped ``default_ratio = "0.30"`` alongside their
``statutory_multiplier = "0.30"``. The evaluator reads ``default_ratio`` in the same
slot as a STORED ratio, and stored ratios are already effective -- the censo
derivation multiplies the raw area proportion by the statutory factor before saving.
So the default asserted an EFFECTIVE thirty per cent, which under this article is
reachable only at a raw afectación of 1.00: the entire dwelling as office. A taxpayer
who had declared nothing at all deducted the maximum the article can ever allow.

Direction of error: OVER-deduction, and therefore under-declared tax. A room of
15 m² in a 90 m² flat is a 16.7 per cent proportion, so the lawful figure is about
5 per cent of the utility bill against the 30 per cent that shipped -- roughly six
times over, silently, on a return the taxpayer signs.

The same stray ``default_ratio`` was already removed from the HOME_OFFICE_OWNERSHIP
siblings for the same reason: "not a legally established default, just an arbitrary
guess". These tests hold the whole usage-ratio family to that ruling.

No mocks: the real shipped registry and the real evaluator.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ...categories.proportionality import ProportionalityKind
from ...categories.registry import resolve_category_profiles
from ...categories.spending_category import SpendingCategory
from ..ledger_expenses import (
    RentaDeductibilityContext,
    RentaDeductibilityStatus,
    RentaDeductibleExpenseFact,
    RentaExpenseDirection,
    evaluate_renta_deductibility,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEAR = 2025
_USAGE_RATIO_KINDS = frozenset(
    {ProportionalityKind.USAGE_RATIO_HOME_AREA, ProportionalityKind.USAGE_RATIO_PERSONAL},
)


def _usage_ratio_categories() -> list[SpendingCategory]:
    """Return every shipped category whose deduction is a proportion of use."""
    profiles = resolve_category_profiles(_YEAR)
    return [
        category
        for category, profile in profiles.items()
        if profile.proportionality is not None and profile.proportionality.kind in _USAGE_RATIO_KINDS
    ]


def _fact(category: SpendingCategory) -> RentaDeductibleExpenseFact:
    return RentaDeductibleExpenseFact(
        transaction_id="a" * 64,
        invoice_id="inv-1",
        invoice_issue_date=date(_YEAR, 3, 8),
        catalogue_id="ledger-2025",
        operation_date=date(_YEAR, 3, 8),
        category=category,
        direction=RentaExpenseDirection.OUTGOING_EXPENSE,
        gross_amount=Decimal("100.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("0.00"),
    )


def test_the_family_is_not_empty() -> None:
    """SUPPORTING. Without this the assertions below would pass vacuously."""
    assert _usage_ratio_categories()


def test_no_usage_ratio_rule_ships_a_stand_in_proportion() -> None:
    """DISCRIMINATING. The defect in its data shape.

    Asserted as a property of every usage-ratio rule rather than as a list of the
    five that carried it: a sixth category added tomorrow with the same stand-in
    is the same defect, and a pinned list would not see it.
    """
    profiles = resolve_category_profiles(_YEAR)
    with_default = [
        category
        for category in _usage_ratio_categories()
        if profiles[category].proportionality.default_ratio is not None
    ]

    assert not with_default, (
        "these usage-ratio categories supply a proportion the taxpayer did not declare. "
        "The percentage is a fact about one dwelling or one device; no provision defaults "
        f"it, so a registry value here is deducted on the operator's behalf: {with_default}"
    )


def test_every_usage_ratio_category_is_ineligible_until_the_operator_declares() -> None:
    """DISCRIMINATING, and the behavioural half.

    The data property above could be satisfied while some other fallback supplied a
    ratio downstream, so this asserts the outcome the taxpayer actually gets.
    """
    profiles = resolve_category_profiles(_YEAR)
    deducted_anyway: list[tuple[str, Decimal]] = []
    for category in _usage_ratio_categories():
        result = evaluate_renta_deductibility(
            _fact(category),
            profiles[category],
            RentaDeductibilityContext(profile_year=_YEAR, usage_ratios={}),
        )
        if result.status is not RentaDeductibilityStatus.INELIGIBLE or result.deductible_amount:
            deducted_anyway.append((category.value, result.deductible_amount))

    assert not deducted_anyway, (
        f"these categories deducted something with no operator-declared proportion: {deducted_anyway}"
    )


def test_a_declared_proportion_is_still_deducted() -> None:
    """SUPPORTING, and the anti-overreach half.

    Refusing without operator input must not become refusing full stop. A category
    that reports INELIGIBLE for every input would satisfy the test above while
    denying every legitimate deduction, which is the opposite error and just as wrong.
    """
    profiles = resolve_category_profiles(_YEAR)
    for category in _usage_ratio_categories():
        result = evaluate_renta_deductibility(
            _fact(category),
            profiles[category],
            RentaDeductibilityContext(
                profile_year=_YEAR,
                usage_ratios={category: Decimal("0.05")},
            ),
        )

        assert result.status is RentaDeductibilityStatus.ELIGIBLE, (
            f"{category.value} refused a declared proportion: {result.reason}"
        )
        assert result.deductible_amount == Decimal("5.0000"), (
            f"{category.value} deducted {result.deductible_amount} for a declared 5 per cent"
        )


def test_the_statutory_multiplier_survives_on_the_suministros_family() -> None:
    """DISCRIMINATING. Removing the stand-in must not remove the real factor.

    The 30 per cent IS statutory for suministros, and the censo derivation applies
    it to convert a raw area proportion into the effective one it stores. Dropping
    it alongside the fabricated default would swing the error the other way, so the
    two are asserted apart.
    """
    profiles = resolve_category_profiles(_YEAR)
    suministros = [
        category
        for category in _usage_ratio_categories()
        if profiles[category].proportionality.statutory_multiplier is not None
    ]

    assert suministros, "no category carries the art. 30.2.5.b statutory factor any more"
    for category in suministros:
        assert profiles[category].proportionality.statutory_multiplier == Decimal("0.30"), (
            f"{category.value} no longer applies the 30 per cent art. 30.2.5.b establishes"
        )
