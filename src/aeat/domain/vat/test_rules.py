"""Unit tests for the :data:`aeat.domain.vat.VAT_CATALOGUE_2025` catalogue.

Pins coverage of every :class:`aeat.domain.vat.VATCategory`, the minimum
citation count, the multilingual-Spanish invariant and the rendered citation
output produced by :func:`aeat.domain.vat.cite`.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ...core.i18n import Translatable
from . import (
    VAT_CATALOGUE_2025,
    VatCitation,
    VatCitationSource,
    VATCategory,
    VATRegulation,
    cite,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_catalogue_covers_every_vat_category() -> None:
    """Every :class:`VATCategory` must have a :class:`VATRegulation` in the catalogue.

    The catalogue ships 17 entries — one per VATCategory member, including
    ``DOMESTIC_REVERSE_CHARGE``.
    """
    assert set(VAT_CATALOGUE_2025.regulations.keys()) == set(VATCategory)
    assert len(VAT_CATALOGUE_2025) == 17


def test_catalogue_has_at_least_32_citations() -> None:
    """The catalogue must ship at least 32 citations across all regulations."""
    total = sum(len(regulation.citations) for regulation in VAT_CATALOGUE_2025)
    assert total >= 32


def test_every_citation_has_non_empty_quoted_text_es() -> None:
    """Every shipped citation must carry real Spanish text."""
    for regulation in VAT_CATALOGUE_2025:
        for citation in regulation.citations:
            assert citation.quoted_text_es.strip()


def test_cite_domestic_general_mentions_ley_37_1992() -> None:
    """:func:`cite` against ``DOMESTIC_GENERAL_21`` surfaces the Ley 37/1992 label."""
    rendered = cite(VATCategory.DOMESTIC_GENERAL_21)
    assert rendered
    assert "Ley 37/1992" in rendered


def test_regulation_without_citation_raises() -> None:
    """Constructing a :class:`VATRegulation` with zero citations must fail."""
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


def test_regulation_missing_spanish_raises() -> None:
    """The multilingual invariant rejects missing 'es' keys."""
    translatable_es_ok: Translatable = {"es": "x", "en": "x", "hu": "x"}
    missing_es: Translatable = {"en": "x", "hu": "x"}
    citation = VatCitation(
        source=VatCitationSource.LEY_37_1992,
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
