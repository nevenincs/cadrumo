"""Unit tests for the :data:`VAT_CATALOGUE_2025` catalogue."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ...i18n import Translatable
from . import (
    VAT_CATALOGUE_2025,
    Citation,
    CitationSource,
    VATCategory,
    VATRegulation,
    cite,
)


@pytest.mark.unit
def test_catalogue_covers_every_vat_category() -> None:
    """Every VATCategory must have a VATRegulation in the catalogue.

    Wave 2 (#183) added the 17th category ``DOMESTIC_REVERSE_CHARGE``.
    """
    assert set(VAT_CATALOGUE_2025.regulations.keys()) == set(VATCategory)
    assert len(VAT_CATALOGUE_2025) == 17


@pytest.mark.unit
def test_catalogue_has_at_least_32_citations() -> None:
    """The catalogue must ship ≥32 citations across all regulations."""
    total = sum(len(regulation.citations) for regulation in VAT_CATALOGUE_2025)
    assert total >= 32


@pytest.mark.unit
def test_every_citation_has_non_empty_quoted_text_es() -> None:
    """Every shipped citation must carry real Spanish text."""
    for regulation in VAT_CATALOGUE_2025:
        for citation in regulation.citations:
            assert citation.quoted_text_es.strip()


@pytest.mark.unit
def test_cite_domestic_general_mentions_ley_37_1992() -> None:
    """`cite(DOMESTIC_GENERAL_21)` surfaces the Ley 37/1992 label."""
    rendered = cite(VATCategory.DOMESTIC_GENERAL_21)
    assert rendered
    assert "Ley 37/1992" in rendered


@pytest.mark.unit
def test_regulation_without_citation_raises() -> None:
    """Constructing a VATRegulation with zero citations must fail."""
    translatable: Translatable = {"es": "x", "en": "x", "hu": "x"}
    with pytest.raises(ValidationError):
        VATRegulation(
            category=VATCategory.UNKNOWN,
            label=translatable,
            description=translatable,
            triggers_when=translatable,
            iva_treatment=translatable,
            declares_in_modelos=("303",),
            requires_reverse_charge=False,
            requires_supplier_vat_id=False,
            boe_references=("ley-37-1992",),
            manual_references=(),
            citations=(),
        )


@pytest.mark.unit
def test_regulation_missing_spanish_raises() -> None:
    """The trilingual invariant rejects missing 'es' keys."""
    translatable_es_ok: Translatable = {"es": "x", "en": "x", "hu": "x"}
    missing_es: Translatable = {"en": "x", "hu": "x"}
    citation = Citation(
        source=CitationSource.LEY_37_1992,
        article="Art. 90.Uno",
        url=None,
        quoted_text_es="prueba",
        retrieval_date=date(2026, 4, 13),
    )
    with pytest.raises(ValidationError):
        VATRegulation(
            category=VATCategory.UNKNOWN,
            label=missing_es,
            description=translatable_es_ok,
            triggers_when=translatable_es_ok,
            iva_treatment=translatable_es_ok,
            declares_in_modelos=("303",),
            requires_reverse_charge=False,
            requires_supplier_vat_id=False,
            boe_references=("ley-37-1992",),
            manual_references=(),
            citations=(citation,),
        )
