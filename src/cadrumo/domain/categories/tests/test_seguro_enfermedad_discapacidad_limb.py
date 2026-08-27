"""LIRPF art. 30.2.5.a states two limits, and the registry must carry both.

Verbatim from the bundled consolidated corpus:

    a) Las primas de seguro de enfermedad satisfechas por el contribuyente en la parte
    correspondiente a su propia cobertura y a la de su conyuge e hijos menores de
    veinticinco anos que convivan con el. El limite maximo de deduccion sera de 500
    euros por cada una de las personas senaladas anteriormente O DE 1.500 EUROS POR
    CADA UNA DE ELLAS CON DISCAPACIDAD.

Only the 500 shipped. The direction of that omission is over-payment: a filer insuring
a spouse or an under-25 child with discapacidad was held to 500 where the article
allows 1.500, deducting 1.000 euros less per such person per year. The return stays
valid, nothing refuses, and nothing warns -- the axis `no-silent-under-declaration`
names as unwatched.

Both figures are literals in the article and neither is year-referenced, so they are
VARIANTS rather than a dated schedule. RIRPF art. 72 fixes who qualifies: *tendran la
consideracion de persona con discapacidad aquellos contribuyentes con un grado de
minusvalia igual o superior al 33 por ciento*.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from cadrumo.core.i18n import Translatable as tr

from .._proportionality import (
    ProportionalityKind,
    ProportionalityRule,
    StatutoryCapPeriod,
    StatutoryCapVariant,
)
from .._registry import load_category_profiles
from .._spending_category import SpendingCategory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_ART_30_2_5_A_GENERAL = Decimal("500")
_ART_30_2_5_A_DISCAPACIDAD = Decimal("1500")


def _shipped_rule() -> ProportionalityRule:
    return load_category_profiles()[SpendingCategory.SEGUROS_SALUD_AUTONOMO].proportionality


def test_the_shipped_rule_carries_both_limits_the_article_states() -> None:
    """GROUNDED against the article, not against the registry's own prior value."""
    rule = _shipped_rule()
    amounts = {variant.id: variant.statutory_cap_eur for variant in rule.statutory_cap_variants}

    assert amounts == {
        "general": _ART_30_2_5_A_GENERAL,
        "discapacidad": _ART_30_2_5_A_DISCAPACIDAD,
    }


def test_the_higher_limb_is_three_times_the_lower_as_the_article_sets_them() -> None:
    """A property of the two figures, so a typo in either is caught rather than copied."""
    rule = _shipped_rule()
    amounts = {variant.id: variant.statutory_cap_eur for variant in rule.statutory_cap_variants}

    assert amounts["discapacidad"] == amounts["general"] * 3


def test_the_rule_no_longer_carries_a_single_flat_limit() -> None:
    """ANTI-REGRESSION: a lone statutory_cap_eur is the shape that lost the higher limb.

    If someone collapses the variants back to one amount, every person is capped at
    that amount and the discapacidad population silently loses a third of its
    allowance again.
    """
    rule = _shipped_rule()

    assert rule.statutory_cap_eur is None
    assert rule.statutory_cap_variants, "the two limbs regressed to a single flat cap"


def test_the_variants_are_annual_per_person_not_daily() -> None:
    """The article caps per person per year; a daily reading would be a different rule."""
    rule = _shipped_rule()

    assert rule.statutory_cap_period is StatutoryCapPeriod.YEAR_PER_PERSON
    assert all(not variant.is_per_day for variant in rule.statutory_cap_variants)
    assert all(variant.statutory_cap_eur_per_day is None for variant in rule.statutory_cap_variants)


def _variant(variant_id: str, **amounts: Decimal | None) -> dict[str, object]:
    return {"id": variant_id, "label": tr("Etiqueta de prueba."), **amounts}


def _rule_with(*variants: dict[str, object], period: StatutoryCapPeriod | None = None) -> ProportionalityRule:
    return ProportionalityRule.model_validate(
        {
            "kind": ProportionalityKind.STATUTORY_CAP,
            "statutory_cap_period": period,
            "statutory_cap_variants": tuple(variants),
            "citations": _shipped_rule().citations,
            "notes": tr("Regla de prueba."),
        },
    )


def test_a_variant_must_declare_exactly_one_unit() -> None:
    """DISCRIMINATING: neither amount caps nothing; both leave the unit to the caller."""
    with pytest.raises(ValidationError, match="declares no amount"):
        StatutoryCapVariant.model_validate(_variant("empty"))

    with pytest.raises(ValidationError, match="both a daily and an annual amount"):
        StatutoryCapVariant.model_validate(
            _variant("both", statutory_cap_eur_per_day=Decimal("26.67"), statutory_cap_eur=Decimal("500")),
        )


def test_variants_inside_one_rule_must_agree_on_the_unit() -> None:
    """Mixing units leaves the resolver guessing what the rule is capped in."""
    with pytest.raises(ValidationError, match="must agree on their unit"):
        _rule_with(
            _variant("annual", statutory_cap_eur=Decimal("500")),
            _variant("daily", statutory_cap_eur_per_day=Decimal("26.67")),
            period=StatutoryCapPeriod.YEAR_PER_PERSON,
        )


def test_an_annual_variant_set_requires_the_period_it_applies_over() -> None:
    """ "500 per person" is not a rule until the period the person is counted over is fixed."""
    with pytest.raises(ValidationError, match="annual statutory cap variants require statutory_cap_period"):
        _rule_with(_variant("general", statutory_cap_eur=Decimal("500")), period=None)


def test_the_daily_dietas_shape_still_loads_unchanged() -> None:
    """The variant concept was widened, not repurposed; RIRPF art. 9's shape is intact."""
    dietas = load_category_profiles()[SpendingCategory.MANUTENCION_DIETAS_NACIONAL].proportionality

    assert dietas.statutory_cap_variants
    assert all(variant.is_per_day for variant in dietas.statutory_cap_variants)
    assert all(variant.statutory_cap_eur is None for variant in dietas.statutory_cap_variants)
