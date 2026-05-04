"""Unit tests for :class:`~aeat.domain.categories.ProportionalityRule` validation.

Verifies the cross-field invariants on the rule shape: fixed-percentage
rules require ``fixed_pct``; statutory-cap rules require a cap value
and reject the daily / generic mix; usage-ratio rules reject
statutory-cap fields; and full-deductible rules reject
``default_ratio``.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from . import (
    CategoryCitation,
    CategoryCitationSource,
    ProportionalityKind,
    ProportionalityRule,
    StatutoryCapPeriod,
    StatutoryCapVariant,
    parse_http_url,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _citation() -> CategoryCitation:
    return CategoryCitation(
        source=CategoryCitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 30",
        url=parse_http_url("https://example.com/ley"),
        quote_es="Texto de prueba.",
    )


def test_fixed_percentage_requires_percentage() -> None:
    """Fixed-percentage rules must provide the percentage field."""

    with pytest.raises(ValidationError):
        ProportionalityRule(
            kind=ProportionalityKind.FIXED_PERCENTAGE,
            citations=(_citation(),),
            notes_es="Falta el porcentaje.",
        )


def test_statutory_cap_requires_cap() -> None:
    """Statutory-cap rules must provide the cap field."""

    with pytest.raises(ValidationError):
        ProportionalityRule(
            kind=ProportionalityKind.STATUTORY_CAP,
            citations=(_citation(),),
            notes_es="Falta el tope.",
        )


def test_full_deductible_rejects_default_ratio() -> None:
    """Default ratios are only valid for usage-ratio rules."""

    with pytest.raises(ValidationError):
        ProportionalityRule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            default_ratio=Decimal("0.30"),
            citations=(_citation(),),
            notes_es="Valor incompatible.",
        )


def test_usage_ratio_rejects_statutory_cap_fields() -> None:
    """Usage-ratio rules must reject statutory-cap fields."""

    with pytest.raises(ValidationError):
        ProportionalityRule(
            kind=ProportionalityKind.USAGE_RATIO_PERSONAL,
            default_ratio=Decimal("0.30"),
            statutory_cap_eur_per_day=Decimal("50"),
            citations=(_citation(),),
            notes_es="Forma incompatible.",
        )


def test_statutory_cap_accepts_generic_annual_caps() -> None:
    """Generic cap fields support non-daily legal limits."""

    rule = ProportionalityRule(
        kind=ProportionalityKind.STATUTORY_CAP,
        statutory_cap_eur=Decimal("500"),
        statutory_cap_period=StatutoryCapPeriod.YEAR_PER_PERSON,
        citations=(_citation(),),
        notes_es="Tope anual.",
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
                label_es="Sin pernocta",
                statutory_cap_eur_per_day=Decimal("26.67"),
            ),
            StatutoryCapVariant(
                id="con-pernocta",
                label_es="Con pernocta",
                statutory_cap_eur_per_day=Decimal("53.34"),
            ),
        ),
        citations=(_citation(),),
        notes_es="Límites diarios por condición.",
    )

    assert {variant.id for variant in rule.statutory_cap_variants} == {"sin-pernocta", "con-pernocta"}


def test_statutory_cap_rejects_mixed_cap_modes() -> None:
    """A statutory-cap rule must not mix generic and variant cap modes."""

    with pytest.raises(ValidationError):
        ProportionalityRule(
            kind=ProportionalityKind.STATUTORY_CAP,
            statutory_cap_eur=Decimal("500"),
            statutory_cap_period=StatutoryCapPeriod.YEAR_PER_PERSON,
            statutory_cap_variants=(
                StatutoryCapVariant(
                    id="sin-pernocta",
                    label_es="Sin pernocta",
                    statutory_cap_eur_per_day=Decimal("26.67"),
                ),
            ),
            citations=(_citation(),),
            notes_es="Modos incompatibles.",
        )
