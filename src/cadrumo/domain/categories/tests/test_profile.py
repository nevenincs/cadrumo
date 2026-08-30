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

from ....core.citation_grounding import CitationGrounding
from ....core.i18n import Translatable as tr
from ....tests.aeat_literal_fixtures import CITATION_MANUAL_PDF_URL_FIXTURE
from ..profile import CategoryProfile
from ..proportionality import (
    CategoryCitation,
    CategoryCitationSource,
    ProportionalityKind,
    ProportionalityRule,
    parse_http_url,
)
from ..spending_category import SpendingCategory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _citation() -> CategoryCitation:
    return CategoryCitation(
        source=CategoryCitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="test",
        url=parse_http_url(CITATION_MANUAL_PDF_URL_FIXTURE),
        quote="Texto de prueba suficientemente concreto.",
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )


def test_category_citation_rejects_blank_quote_at_schema_boundary() -> None:
    """A citation claiming VERIFIED must carry the text that verifies it.

    The constraint is unchanged; what changed is that it can now fire. While
    ``quote`` was a translation key the loader resolved it through a fallback
    that never yields an empty string, so this check inspected the literal word
    "Quote" for all eighty-three shipped citations and passed every time.
    """
    with pytest.raises(ValidationError, match="must carry its verbatim quotation"):
        CategoryCitation(
            source=CategoryCitationSource.MANUAL_RENTA,
            reference="Manual práctico Renta 2025",
            locator="test",
            url=parse_http_url(CITATION_MANUAL_PDF_URL_FIXTURE),
            quote="   ",
            valid_from=date(2025, 1, 1),
            valid_to=date(2025, 12, 31),
        )


def test_category_citation_accepts_a_missing_quote_only_with_a_stated_reason() -> None:
    """The other half: an absent quotation is legitimate when the record says why.

    An AEAT Manual práctico edition is authoritative but is not among the
    bundled consolidated texts, so no verbatim excerpt can be transcribed from
    anything the repository holds. Refusing that citation outright would push an
    author toward inventing text; accepting it silently would let the absence
    pass as evidence. It is accepted only against a stated reason.
    """
    citation = CategoryCitation(
        source=CategoryCitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="test",
        url=parse_http_url(CITATION_MANUAL_PDF_URL_FIXTURE),
        quote="",
        grounding=CitationGrounding.SOURCE_NOT_BUNDLED,
        grounding_reason="El Manual práctico no está en el corpus consolidado empaquetado.",
        valid_from=date(2025, 1, 1),
        valid_to=date(2025, 12, 31),
    )

    assert citation.grounding is CitationGrounding.SOURCE_NOT_BUNDLED

    with pytest.raises(ValidationError, match="must record WHY"):
        CategoryCitation(
            source=CategoryCitationSource.MANUAL_RENTA,
            reference="Manual práctico Renta 2025",
            locator="test",
            url=parse_http_url(CITATION_MANUAL_PDF_URL_FIXTURE),
            quote="",
            grounding=CitationGrounding.SOURCE_NOT_BUNDLED,
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
