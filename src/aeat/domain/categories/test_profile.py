"""Unit tests for :class:`~aeat.domain.categories.CategoryProfile` validation.

Exercises the profile-level invariants: authoritative Spanish label
required on the display label, casilla-mapping cadence rules, and
the no-duplicate-mapping invariant. The factory helpers
(:func:`_citation`, :func:`_mapping`, :func:`_rule`) build minimal
valid stand-ins so each test can focus on the failure mode it
covers.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from ..casillas import ModeloCode, PeriodType
from . import (
    CasillaMapping,
    CasillaMappingSign,
    CategoryCitation,
    CategoryCitationSource,
    CategoryProfile,
    ProportionalityKind,
    ProportionalityRule,
    SpendingCategory,
    parse_http_url,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _citation() -> CategoryCitation:
    return CategoryCitation(
        source=CategoryCitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="test",
        url=parse_http_url("https://example.com/manual.pdf"),
        quote_es="Texto de prueba suficientemente concreto.",
    )


def _mapping() -> CasillaMapping:
    return CasillaMapping(
        modelo=ModeloCode.MODELO_130,
        period_type=PeriodType.QUARTERLY,
        casilla_code="01",
        sign=CasillaMappingSign.CREDIT,
    )


def test_casilla_mapping_period_type_accepts_string_variants() -> None:
    lower = CasillaMapping.model_validate(
        {
            "modelo": ModeloCode.MODELO_130,
            "period_type": "quarterly",
            "casilla_code": "01",
            "sign": CasillaMappingSign.CREDIT,
        }
    )
    upper = CasillaMapping.model_validate(
        {
            "modelo": ModeloCode.MODELO_390,
            "period_type": "ANNUAL",
            "casilla_code": "95",
            "sign": CasillaMappingSign.CREDIT,
        }
    )
    assert lower.period_type is PeriodType.QUARTERLY
    assert upper.period_type is PeriodType.ANNUAL


def _rule() -> ProportionalityRule:
    return ProportionalityRule(
        kind=ProportionalityKind.FULL_DEDUCTIBLE,
        citations=(_citation(),),
        notes_es="Regla de prueba.",
    )


def test_category_profile_requires_authoritative_spanish_label() -> None:
    """Profiles must reject labels missing the authoritative Spanish string."""

    with pytest.raises(ValidationError):
        CategoryProfile(
            category=SpendingCategory.MATERIAL_OFICINA,
            display_label={"en": "Office supplies"},
            proportionality=_rule(),
            casilla_mappings=(_mapping(),),
            vat_hint=None,
        )


def test_category_profile_rejects_duplicate_mappings() -> None:
    """Profiles must reject duplicate modelo/period/casilla combinations."""

    with pytest.raises(ValidationError):
        CategoryProfile(
            category=SpendingCategory.MATERIAL_OFICINA,
            display_label={"es": "Material", "en": "Supplies", "hu": "Anyag"},
            proportionality=ProportionalityRule(
                kind=ProportionalityKind.FIXED_PERCENTAGE,
                fixed_pct=Decimal("1.00"),
                citations=(_citation(),),
                notes_es="Duplicado de prueba.",
            ),
            casilla_mappings=(_mapping(), _mapping()),
            vat_hint=None,
        )
