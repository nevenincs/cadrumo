"""IVA catalogue runtime tests."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import date

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.authority import (
    PinnedAuthorityOperation,
)
from cadrumo.domain.calculations.registry.authority import (
    bundled_indexed_authority as _indexed_authority_for_test,
)

from ....core.citation_grounding import CitationGrounding
from ...calculations.registry.iva_category_catalogue import resolve_iva_category_catalogue
from ..catalogue import resolve_catalogue
from ..schema import IvaCatalogue, IvaCategory, IvaCitation

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def operation() -> Iterator[PinnedAuthorityOperation]:
    """Pin one canonical authority generation for the catalogue projections."""
    with _indexed_authority_for_test().operation() as pinned:
        yield pinned


@pytest.fixture(scope="module")
def catalogue(operation: PinnedAuthorityOperation) -> IvaCatalogue:
    """Resolve the IVA rules against the registry's explicit filing-year projection."""
    return resolve_catalogue(on=date(2025, 1, 1), operation=operation, projected_year=2025)


def test_catalogue_covers_every_iva_category(
    catalogue: IvaCatalogue,
    operation: PinnedAuthorityOperation,
) -> None:
    categories = resolve_iva_category_catalogue(effective_date=date(2025, 1, 1), authority=operation).all_categories
    assert set(catalogue.regulations.keys()) == set(categories)


def test_catalogue_has_at_least_33_citations(catalogue: IvaCatalogue) -> None:
    total = sum(len(regulation.citations) for regulation in catalogue)
    assert total >= 33


def test_every_citation_states_its_grounding_and_carries_the_evidence_for_it(catalogue: IvaCatalogue) -> None:
    """A citation must either quote the corpus or say why it could not.

    This replaces an assertion that every citation carried non-empty text.
    That check passed for all of them and verified nothing: quoted_text was a
    translation key, the loader resolved it before the assertion ran, and the
    fallback never yields an empty string -- so the test was reading the word
    "Quoted text" and finding it non-empty.

    Both branches below can fail, which is the point.
    """
    for regulation in catalogue:
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

    A candidate quotation stored here would read as evidence to anyone printing
    the field while the record itself says it has none.
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


def test_reagp_compensation_is_grounded_in_its_exact_statutory_compensation_article(
    catalogue: IvaCatalogue,
) -> None:
    regulation = catalogue.regulations[IvaCategory("reagp_compensation")]

    assert [citation.legal_reference for citation in regulation.citations] == ["ley-37-1992:art-130"]
    assert "compensación a tanto alzado" in regulation.citations[0].quoted_text


def test_every_committed_regulation_has_citations_unless_legal_basis_exempt(catalogue: IvaCatalogue) -> None:
    """Every regulation is grounded, except a declared classifier sentinel.

    ``IvaCategory("unknown")`` codifies no tax treatment -- it is an
    application-level "could not classify" state -- so it carries no
    citations and is the sole carve-out, declared via
    ``legal_basis_exempt`` rather than merely absent.
    """
    assert len(catalogue) > 0, "IVA regulation catalogue must be non-empty for citation check to mean anything"
    checked = 0
    for regulation in catalogue:
        if regulation.legal_basis_exempt:
            assert not regulation.citations, regulation.category.value
        else:
            assert regulation.citations, regulation.category.value
        checked += 1
    assert checked == len(catalogue), "every regulation in the catalogue must be checked"


def test_unknown_category_is_the_sole_legal_basis_exempt_regulation(catalogue: IvaCatalogue) -> None:
    exempt = [regulation.category for regulation in catalogue if regulation.legal_basis_exempt]
    assert exempt == [IvaCategory("unknown")]
