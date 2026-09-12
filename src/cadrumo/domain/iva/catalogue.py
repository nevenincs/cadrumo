"""Read-only IVA regulation catalogue projection.

:func:`bundled_iva_catalogue` adapts the published authority into an
:class:`IvaCatalogue` whose entries are keyed by :class:`IvaCategory` and stored
as :class:`IvaRegulation`. :func:`iva_catalogue_years` derives the resolvable
filing years from the citation windows, and :func:`resolve_catalogue` projects
the catalogue onto one of them, keeping only the citations asserted over it and
refusing a year the catalogue cannot ground.
"""

from __future__ import annotations

from datetime import date

from ...core.citation_grounding import CitationGrounding
from ...core.validity_window import years_covered_by_every_group
from .errors import IvaCatalogueError
from .schema import IvaCatalogue, IvaCategory, IvaCitation, IvaRegulation


def bundled_iva_catalogue() -> IvaCatalogue:
    """Adapt the published runtime projection into the operational catalogue."""
    from ..calculations.registry.authority import bundled_authority

    regulations: dict[IvaCategory, IvaRegulation] = {}
    for published in bundled_authority().catalogues.runtime.iva_regulations.values():
        category = IvaCategory(published.category)
        regulations[category] = IvaRegulation.model_validate(
            {
                "category": category,
                "requires_reverse_charge": published.requires_reverse_charge,
                "requires_supplier_iva_id": published.requires_supplier_iva_id,
                "manual_references": published.manual_references,
                "citations": tuple(
                    IvaCitation.model_validate(
                        {
                            "legal_reference": citation.legal_reference,
                            "quoted_text": citation.quoted_text,
                            "grounding": CitationGrounding(citation.grounding),
                            "unresolved_reason": citation.unresolved_reason,
                            "valid_from": citation.valid_from,
                            "valid_to": citation.valid_to,
                        }
                    )
                    for citation in published.citations
                ),
                "notes": published.notes,
                "legal_basis_exempt": published.legal_basis_exempt,
            }
        )
    return IvaCatalogue(regulations=regulations)


def iva_catalogue_years() -> frozenset[int]:
    """Return every filing year the catalogue can be resolved for.

    A year counts only when EVERY grounded regulation has at least one citation
    asserted over it. A legal-basis-exempt regulation codifies no treatment and
    carries no citations, so it grounds nothing and is excluded rather than
    emptying the result.

    Returns:
        The derived set of resolvable filing years.
    """
    return years_covered_by_every_group(
        [citation.window for citation in regulation.citations]
        for regulation in bundled_iva_catalogue()
        if not regulation.legal_basis_exempt
    )


def resolve_catalogue(*, on: date) -> IvaCatalogue:
    """Return the IVA catalogue as grounded for the filing year of ``on``.

    Every regulation is projected onto the year: citations asserted over another
    span are dropped, so what the caller receives cites only evidence that
    speaks to the year asked for.

    Returns:
        The :class:`IvaCatalogue` for the year of ``on``.

    Raises:
        IvaCatalogueError: When the catalogue grounds no such year. There is no
            fallback to an adjacent year.
    """
    from ..calculations.registry.authority import bundled_authority

    projected_year = bundled_authority().project_filing_year(on.year)
    return _resolve_catalogue(projected_year, tuple(sorted(iva_catalogue_years())))


def _resolve_catalogue(year: int, grounded: tuple[int, ...]) -> IvaCatalogue:
    if year not in grounded:
        raise IvaCatalogueError(
            f"no IVA catalogue grounded for year={year}; the catalogue grounds {list(grounded)}. "
            "Ground the year against BOE or AEAT and add its citations -- never widen an existing "
            "citation's window to admit it.",
        )
    projected = {
        category: regulation.model_copy(
            update={
                "citations": tuple(citation for citation in regulation.citations if citation.window.covers_year(year)),
            },
        )
        for category, regulation in bundled_iva_catalogue().regulations.items()
    }
    return IvaCatalogue(regulations=projected)


__all__ = [
    "bundled_iva_catalogue",
    "iva_catalogue_years",
    "resolve_catalogue",
]
