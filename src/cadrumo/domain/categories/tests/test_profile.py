"""Unit tests for :class:`~cadrumo.domain.categories.CategoryProfile` validation.

Exercises the profile-level invariants: authoritative Spanish label
required on the display label and proportionality citations. The factory
helpers build minimal valid stand-ins so each test can focus on the
failure mode it covers.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ....core.i18n import Translatable as tr
from ....tests.aeat_literal_fixtures import CITATION_MANUAL_PDF_URL_FIXTURE
from .. import (
    CategoryCitation,
    CategoryCitationSource,
    CategoryProfile,
    ProportionalityKind,
    ProportionalityRule,
    SpendingCategory,
    parse_http_url,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _citation() -> CategoryCitation:
    return CategoryCitation(
        source=CategoryCitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="test",
        url=parse_http_url(CITATION_MANUAL_PDF_URL_FIXTURE),
        quote=tr("Texto de prueba suficientemente concreto."),
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )


def test_category_citation_rejects_blank_quote_at_schema_boundary() -> None:
    with pytest.raises(ValidationError, match="authoritative Spanish text"):
        CategoryCitation(
            source=CategoryCitationSource.MANUAL_RENTA,
            reference="Manual práctico Renta 2025",
            locator="test",
            url=parse_http_url(CITATION_MANUAL_PDF_URL_FIXTURE),
            quote=tr("   "),
            valid_from=date(2025, 1, 1),
            valid_to=date(2025, 12, 31),
        )


def test_category_profile_rejects_blank_display_label_at_schema_boundary() -> None:
    with pytest.raises(ValidationError, match="display_label"):
        CategoryProfile(
            category=SpendingCategory.MATERIAL_OFICINA,
            display_label=tr("   "),
            proportionality=_rule(),
            iva_hint=None,
        )


def _rule() -> ProportionalityRule:
    return ProportionalityRule(
        kind=ProportionalityKind.FULL_DEDUCTIBLE,
        citations=(_citation(),),
        notes=tr("Regla de prueba."),
    )


def test_category_profile_accepts_profile_without_casilla_projection() -> None:
    """Profiles carry category semantics, not filing-layout projection."""

    profile = CategoryProfile(
        category=SpendingCategory.MATERIAL_OFICINA,
        display_label=tr("categories.test_profile.display_label_851219"),
        proportionality=ProportionalityRule(
            kind=ProportionalityKind.FIXED_PERCENTAGE,
            fixed_pct=Decimal("1.00"),
            citations=(_citation(),),
            notes=tr("Perfil sin proyección a casillas."),
        ),
        iva_hint=None,
    )
    assert profile.category is SpendingCategory.MATERIAL_OFICINA


def test_category_profile_rejects_stale_casilla_projection_payload() -> None:
    """Deleted projection fields must fail validation instead of being dropped."""

    with pytest.raises(ValidationError, match=r"Extra inputs are not permitted|projection"):
        CategoryProfile.model_validate(
            {
                "category": SpendingCategory.MATERIAL_OFICINA,
                "display_label": {"es": "Material"},
                "proportionality": {
                    "kind": ProportionalityKind.FULL_DEDUCTIBLE,
                    "citations": [_citation().model_dump(mode="json")],
                    "notes": "Perfil sin proyección a casillas.",
                },
                "casilla_mappings": [],
            },
        )
