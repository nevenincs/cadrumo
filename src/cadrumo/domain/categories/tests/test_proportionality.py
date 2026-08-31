"""Unit tests for :class:`~cadrumo.domain.categories.ProportionalityRule` validation.

Verifies the cross-field invariants on the rule shape: fixed-percentage
rules require ``fixed_pct``; statutory-cap rules require a cap value
and reject the daily / generic mix; usage-ratio rules reject
statutory-cap fields; and full-deductible rules reject
``default_ratio``.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.i18n import Translatable as tr
from ..proportionality import (
    CategoryCitation,
    CategoryCitationSource,
    ProportionalityKind,
    ProportionalityRule,
    StatutoryCapPeriod,
    StatutoryCapVariant,
    parse_http_url,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _citation() -> CategoryCitation:
    return CategoryCitation(
        source=CategoryCitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 30",
        url=parse_http_url("https://www.boe.es/ley"),
        quote=tr("Texto de prueba."),
        legal_ref="ley-35-2006:art-30",
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )


def test_fixed_percentage_requires_percentage() -> None:
    """Fixed-percentage rules must provide the percentage field."""

    with pytest.raises(ValidationError, match=r"fixed_percentage rules require fixed_pct"):
        ProportionalityRule(
            kind=ProportionalityKind.FIXED_PERCENTAGE,
            citations=(_citation(),),
            notes=tr("Falta el porcentaje."),
        )


def test_statutory_cap_requires_cap() -> None:
    """Statutory-cap rules must provide the cap field."""

    with pytest.raises(ValidationError, match=r"statutory_cap rules require a cap amount"):
        ProportionalityRule(
            kind=ProportionalityKind.STATUTORY_CAP,
            citations=(_citation(),),
            notes=tr("Falta el tope."),
        )


def test_full_deductible_rejects_default_ratio() -> None:
    """Default ratios are only valid for usage-ratio rules."""

    with pytest.raises(ValidationError, match=r"default_ratio is only valid for usage_ratio rules"):
        ProportionalityRule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            default_ratio=Decimal("0.30"),
            citations=(_citation(),),
            notes=tr("Valor incompatible."),
        )


def test_usage_ratio_rejects_statutory_cap_fields() -> None:
    """Usage-ratio rules must reject statutory-cap fields."""

    with pytest.raises(ValidationError, match=r"statutory_cap_eur_per_day is only valid for statutory_cap rules"):
        ProportionalityRule(
            kind=ProportionalityKind.USAGE_RATIO_PERSONAL,
            default_ratio=Decimal("0.30"),
            statutory_cap_eur_per_day=Decimal("50"),
            citations=(_citation(),),
            notes=tr("Forma incompatible."),
        )


def test_statutory_cap_accepts_generic_annual_caps() -> None:
    """Generic cap fields support non-daily legal limits."""

    rule = ProportionalityRule(
        kind=ProportionalityKind.STATUTORY_CAP,
        statutory_cap_eur=Decimal("500"),
        statutory_cap_period=StatutoryCapPeriod.YEAR_PER_PERSON,
        citations=(_citation(),),
        notes=tr("Tope anual."),
    )

    assert rule.statutory_cap_eur == Decimal("500")
    assert rule.statutory_cap_period is StatutoryCapPeriod.YEAR_PER_PERSON


def test_statutory_cap_accepts_daily_cap_variants() -> None:
    """Daily statutory-cap variants preserve condition-specific legal limits."""

    rule = ProportionalityRule(
        kind=ProportionalityKind.STATUTORY_CAP,
        statutory_cap_variants=(
            StatutoryCapVariant(
                id="sin-pernocta",
                label=tr("Sin pernocta"),
                statutory_cap_eur_per_day=Decimal("26.67"),
            ),
            StatutoryCapVariant(
                id="con-pernocta",
                label=tr("Con pernocta"),
                statutory_cap_eur_per_day=Decimal("53.34"),
            ),
        ),
        citations=(_citation(),),
        notes=tr("Límites diarios por condición."),
    )

    assert {variant.id for variant in rule.statutory_cap_variants} == {"sin-pernocta", "con-pernocta"}


def test_statutory_cap_variant_rejects_blank_label_at_schema_boundary() -> None:
    with pytest.raises(ValidationError, match="statutory cap variant label"):
        StatutoryCapVariant(
            id="sin-pernocta",
            label=tr("   "),
            statutory_cap_eur_per_day=Decimal("26.67"),
        )


def test_statutory_cap_rejects_mixed_cap_modes() -> None:
    """A statutory-cap rule must not mix generic and variant cap modes."""

    with pytest.raises(ValidationError, match=r"statutory cap rules must use one cap mode"):
        ProportionalityRule(
            kind=ProportionalityKind.STATUTORY_CAP,
            statutory_cap_eur=Decimal("500"),
            statutory_cap_period=StatutoryCapPeriod.YEAR_PER_PERSON,
            statutory_cap_variants=(
                StatutoryCapVariant(
                    id="sin-pernocta",
                    label=tr("Sin pernocta"),
                    statutory_cap_eur_per_day=Decimal("26.67"),
                ),
            ),
            citations=(_citation(),),
            notes=tr("Modos incompatibles."),
        )


def test_statutory_multiplier_rejected_on_non_usage_ratio_kind() -> None:
    """statutory_multiplier is only valid for usage-ratio kinds; a
    full-deductible rule with a multiplier declared must refuse load.
    Backs the LIRPF legal-grounding contract for usage-ratio rules."""

    with pytest.raises(
        ValidationError,
        match=r"statutory_multiplier is only valid for usage_ratio rules",
    ):
        ProportionalityRule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            statutory_multiplier=Decimal("0.30"),
            citations=(_citation(),),
            notes=tr("Multiplicador estatutario incompatible."),
        )


def test_proportionality_rule_rejects_blank_notes_at_schema_boundary() -> None:
    with pytest.raises(ValidationError, match="proportionality rule notes"):
        ProportionalityRule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=(_citation(),),
            notes=tr("   "),
        )


def test_statutory_multiplier_accepts_home_area_suministros_legal_factor() -> None:
    """The LIRPF Art. 30.2 rule 5 0.30 suministros factor lands as a
    statutory_multiplier on a USAGE_RATIO_HOME_AREA rule."""

    rule = ProportionalityRule(
        kind=ProportionalityKind.USAGE_RATIO_HOME_AREA,
        default_ratio=Decimal("0.30"),
        statutory_multiplier=Decimal("0.30"),
        citations=(_citation(),),
        notes=tr("Suministros 0.30 multiplier per LIRPF Art. 30.2 rule 5"),
    )

    assert rule.statutory_multiplier == Decimal("0.30")
    assert rule.default_ratio == Decimal("0.30")


def test_effective_usage_ratio_applies_multiplier_to_chosen_ratio() -> None:
    """effective_usage_ratio = chosen_ratio * statutory_multiplier;
    rule.None multiplier means no factor (effective = chosen)."""

    from ..proportionality import effective_usage_ratio

    suministros = ProportionalityRule(
        kind=ProportionalityKind.USAGE_RATIO_HOME_AREA,
        statutory_multiplier=Decimal("0.30"),
        citations=(_citation(),),
        notes=tr("Suministros multiplier"),
    )
    ownership = ProportionalityRule(
        kind=ProportionalityKind.USAGE_RATIO_HOME_AREA,
        citations=(_citation(),),
        notes=tr("Ownership raw ratio"),
    )

    # 20% office area, suministros: 20% * 30% = 6% deductible.
    assert effective_usage_ratio(suministros, Decimal("0.20")) == Decimal("0.0600")
    # 20% office area, ownership: 20% deductible (raw ratio, no factor).
    assert effective_usage_ratio(ownership, Decimal("0.20")) == Decimal("0.20")


def test_effective_usage_ratio_refuses_non_usage_ratio_rules() -> None:
    """The helper refuses to evaluate against rules of non-usage-ratio
    kinds (caller is responsible for routing rules to the right
    evaluator)."""

    from ..errors import CategoryValidationError
    from ..proportionality import effective_usage_ratio

    rule = ProportionalityRule(
        kind=ProportionalityKind.FULL_DEDUCTIBLE,
        citations=(_citation(),),
        notes=tr("Sin proporcionalidad."),
    )
    with pytest.raises(
        CategoryValidationError,
        match=r"effective_usage_ratio is only valid for usage_ratio rules",
    ):
        effective_usage_ratio(rule, Decimal("0.50"))
