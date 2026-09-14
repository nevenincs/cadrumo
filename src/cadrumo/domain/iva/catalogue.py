"""Read-only IVA regulation catalogue projection.

:func:`bundled_iva_catalogue` adapts the published authority into an
:class:`IvaCatalogue` whose entries are keyed by :class:`IvaCategory` and stored
as :class:`IvaRegulation`. :func:`iva_catalogue_years` derives the resolvable
filing years from the citation windows, and :func:`resolve_catalogue` projects
the catalogue onto one of them, keeping only the citations asserted over it and
refusing a year the catalogue cannot ground.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import TYPE_CHECKING, cast

from ...core.citation_grounding import CitationGrounding
from ...core.validity_window import years_covered_by_every_group
from ..calculations.registry.iva_category_catalogue import require_iva_category
from .errors import IvaCatalogueError
from .schema import IvaCatalogue, IvaCategory, IvaCitation, IvaRegulation

if TYPE_CHECKING:
    from ..calculations.registry.authority import PinnedAuthorityOperation


def bundled_iva_catalogue(*, operation: PinnedAuthorityOperation) -> IvaCatalogue:
    """Adapt one selected IVA runtime component into the operational catalogue.

    ``operation`` addresses only the IVA regulation component already pinned by
    the caller.
    """
    from ..calculations.registry.runtime_catalogues import PublishedIvaRegulation

    loaded = operation.runtime_catalogue("iva_regulations")
    if not isinstance(loaded, Mapping):
        raise IvaCatalogueError("indexed authority IVA regulation component has an invalid shape")
    loaded_values = tuple(cast(Mapping[object, object], loaded).values())
    if not all(isinstance(value, PublishedIvaRegulation) for value in loaded_values):
        raise IvaCatalogueError("indexed authority IVA regulation component has an invalid shape")
    published_values = tuple(value for value in loaded_values if isinstance(value, PublishedIvaRegulation))

    regulations: dict[IvaCategory, IvaRegulation] = {}
    for published in published_values:
        category = require_iva_category(published.category, authority=operation)
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


def iva_catalogue_years(*, operation: PinnedAuthorityOperation) -> frozenset[int]:
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
        for regulation in bundled_iva_catalogue(operation=operation)
        if not regulation.legal_basis_exempt
    )


def resolve_catalogue(
    *,
    on: date,
    operation: PinnedAuthorityOperation,
    projected_year: int | None = None,
) -> IvaCatalogue:
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
    if projected_year is None:
        raise IvaCatalogueError("IVA catalogue resolution requires the caller's projected filing year")
    return _resolve_catalogue(
        projected_year,
        tuple(sorted(iva_catalogue_years(operation=operation))),
        operation=operation,
    )


def _resolve_catalogue(
    year: int,
    grounded: tuple[int, ...],
    *,
    operation: PinnedAuthorityOperation,
) -> IvaCatalogue:
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
        for category, regulation in bundled_iva_catalogue(operation=operation).regulations.items()
    }
    return IvaCatalogue(regulations=projected)


__all__ = [
    "bundled_iva_catalogue",
    "iva_catalogue_years",
    "resolve_catalogue",
]
