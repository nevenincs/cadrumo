"""IVA catalogue runtime tests."""

from __future__ import annotations

from datetime import date

import pytest

from .. import IvaCategory, cite, resolve_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CATALOGUE = resolve_catalogue(on=date(2025, 1, 1))


def test_catalogue_covers_every_iva_category() -> None:
    assert set(_CATALOGUE.regulations.keys()) == set(IvaCategory)
    assert len(_CATALOGUE) == 17


def test_catalogue_has_at_least_32_citations() -> None:
    total = sum(len(regulation.citations) for regulation in _CATALOGUE)
    assert total >= 32


def test_every_citation_has_non_empty_quoted_text() -> None:
    for regulation in _CATALOGUE:
        for citation in regulation.citations:
            assert citation.quoted_text.strip()


def test_cite_domestic_general_mentions_ley_37_1992() -> None:
    rendered = cite(IvaCategory.DOMESTIC_GENERAL_21, on=date(2025, 6, 15))
    assert rendered
    assert "Ley 37/1992" in rendered


def test_every_committed_regulation_has_citations() -> None:
    assert len(_CATALOGUE) > 0, "IVA regulation catalogue must be non-empty for citation check to mean anything"
    checked = 0
    for regulation in _CATALOGUE:
        assert regulation.citations, regulation.category.value
        checked += 1
    assert checked == len(_CATALOGUE), "every regulation in the catalogue must be checked"
