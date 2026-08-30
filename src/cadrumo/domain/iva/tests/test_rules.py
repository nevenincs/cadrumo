"""IVA catalogue runtime tests."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ....core.citation_grounding import CitationGrounding
from ..catalogue import resolve_catalogue
from ..lookup import cite
from ..schema import IvaCategory, IvaCitation

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CATALOGUE = resolve_catalogue(on=date(2025, 1, 1))


def test_catalogue_covers_every_iva_category() -> None:
    assert set(_CATALOGUE.regulations.keys()) == set(IvaCategory)


def test_catalogue_has_at_least_33_citations() -> None:
    total = sum(len(regulation.citations) for regulation in _CATALOGUE)
    assert total >= 33


def test_every_citation_states_its_grounding_and_carries_the_evidence_for_it() -> None:
    """A citation must either quote the corpus or say why it could not.

    This replaces an assertion that every citation carried non-empty text.
    That check passed for all of them and verified nothing: quoted_text was a
    translation key, the loader resolved it before the assertion ran, and the
    fallback never yields an empty string -- so the test was reading the word
    "Quoted text" and finding it non-empty.

    Both branches below can fail, which is the point.
    """
    for regulation in _CATALOGUE:
        for citation in regulation.citations:
            if citation.grounding is CitationGrounding.VERIFIED:
                assert citation.quoted_text.strip(), (
                    f"{regulation.category.value}/{citation.legal_reference} claims verified grounding "
                    "but carries no quotation"
                )
                assert not citation.unresolved_reason.strip()
            else:
                assert citation.unresolved_reason.strip(), (
                    f"{regulation.category.value}/{citation.legal_reference} is unresolved but records no reason, "
                    "so it reads as unchecked rather than as examined and refused"
                )


def test_iva_citation_rejects_a_verified_claim_with_no_quotation() -> None:
    with pytest.raises(ValidationError, match="must carry its verbatim quotation"):
        IvaCitation.model_validate(
            {
                "legal_reference": "ley-37-1992:art-90",
                "quoted_text": "   ",
                "valid_from": date(2022, 1, 1),
                "valid_to": date(2026, 12, 31),
            },
        )


def test_iva_citation_rejects_an_unresolved_claim_with_no_reason() -> None:
    """Unresolved without a reason is indistinguishable from unchecked."""
    with pytest.raises(ValidationError, match="must record WHY"):
        IvaCitation.model_validate(
            {
                "legal_reference": "ley-37-1992:art-90",
                "quoted_text": "",
                "grounding": CitationGrounding.UNRESOLVED,
                "unresolved_reason": "   ",
                "valid_from": date(2022, 1, 1),
                "valid_to": date(2026, 12, 31),
            },
        )


def test_iva_citation_rejects_an_unresolved_claim_that_carries_a_quotation() -> None:
    """Text parked under unresolved grounding is never read against the corpus.

    ``verify_catalogue`` skips the empty-quotation check for this state by
    design, so a candidate quotation stored here would read as evidence to
    anyone printing the field while the record itself says it has none.
    """
    with pytest.raises(ValidationError, match="must not carry a quotation"):
        IvaCitation.model_validate(
            {
                "legal_reference": "ley-37-1992:art-90",
                "quoted_text": "El tipo impositivo sera el 21 por ciento",
                "grounding": CitationGrounding.UNRESOLVED,
                "unresolved_reason": "candidate text that did not match the bundled corpus",
                "valid_from": date(2022, 1, 1),
                "valid_to": date(2026, 12, 31),
            },
        )


def test_cite_domestic_general_renders_its_registry_legal_reference() -> None:
    rendered = cite(IvaCategory.DOMESTIC_GENERAL, on=date(2025, 6, 15))
    assert rendered
    assert "BOE-A-1992-28740" in rendered
    assert "Art. 90" in rendered


def test_reagp_compensation_is_grounded_in_its_exact_statutory_compensation_article() -> None:
    regulation = _CATALOGUE.regulations[IvaCategory.REAGP_COMPENSATION]

    assert [citation.legal_reference for citation in regulation.citations] == ["ley-37-1992:art-130"]
    assert "compensación a tanto alzado" in regulation.citations[0].quoted_text


def test_every_committed_regulation_has_citations_unless_legal_basis_exempt() -> None:
    """Every regulation is grounded, except a declared classifier sentinel.

    ``IvaCategory.UNKNOWN`` codifies no tax treatment -- it is an
    application-level "could not classify" state -- so it carries no
    citations and is the sole carve-out, declared via
    ``legal_basis_exempt`` rather than merely absent.
    """
    assert len(_CATALOGUE) > 0, "IVA regulation catalogue must be non-empty for citation check to mean anything"
    checked = 0
    for regulation in _CATALOGUE:
        if regulation.legal_basis_exempt:
            assert not regulation.citations, regulation.category.value
        else:
            assert regulation.citations, regulation.category.value
        checked += 1
    assert checked == len(_CATALOGUE), "every regulation in the catalogue must be checked"


def test_unknown_category_is_the_sole_legal_basis_exempt_regulation() -> None:
    exempt = [regulation.category for regulation in _CATALOGUE if regulation.legal_basis_exempt]
    assert exempt == [IvaCategory.UNKNOWN]
