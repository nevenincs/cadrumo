"""Unit tests for proportionality rule validation."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from . import (
    Citation,
    CitationSource,
    ProportionalityKind,
    ProportionalityRule,
    StatutoryCapPeriod,
    parse_http_url,
)


def _citation() -> Citation:
    return Citation(
        source=CitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 30",
        url=parse_http_url("https://example.com/ley"),
        quote_es="Texto de prueba.",
    )


@pytest.mark.unit
def test_fixed_percentage_requires_percentage() -> None:
    """Fixed-percentage rules must provide the percentage field."""

    with pytest.raises(ValidationError):
        ProportionalityRule(
            kind=ProportionalityKind.FIXED_PERCENTAGE,
            citations=(_citation(),),
            notes_es="Falta el porcentaje.",
        )


@pytest.mark.unit
def test_statutory_cap_requires_cap() -> None:
    """Statutory-cap rules must provide the cap field."""

    with pytest.raises(ValidationError):
        ProportionalityRule(
            kind=ProportionalityKind.STATUTORY_CAP,
            citations=(_citation(),),
            notes_es="Falta el tope.",
        )


@pytest.mark.unit
def test_full_deductible_rejects_default_ratio() -> None:
    """Default ratios are only valid for usage-ratio rules."""

    with pytest.raises(ValidationError):
        ProportionalityRule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            default_ratio=Decimal("0.30"),
            citations=(_citation(),),
            notes_es="Valor incompatible.",
        )


@pytest.mark.unit
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


@pytest.mark.unit
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
