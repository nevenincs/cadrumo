"""Lookup helpers for VAT registry data."""

from __future__ import annotations

from datetime import date

from ._catalogue import resolve_catalogue
from ._rates import load_vat_rate_table
from ._schema import EUMemberState, VATCatalogue, VATCategory, VATRate, VATRateKind
from .errors import VatCatalogueError, VatCategoryNotFoundError, VatRateNotFoundError


def lookup_rate(
    member_state: EUMemberState,
    kind: VATRateKind,
    on_date: date,
) -> VATRate:
    """Return the :class:`aeat.domain.vat.VATRate` matching the supplied query.

    Iterates the rates registered for ``member_state`` in
    :data:`aeat.domain.vat.VAT_RATE_TABLE` and returns the first record whose
    :attr:`aeat.domain.vat.VATRate.kind` matches ``kind`` and whose
    effective window covers ``on_date``.

    Args:
        member_state: The EU member state whose rate is requested.
        kind: The rate tier (general / reduced / ...).
        on_date: The effective date for the lookup.

    Returns:
        The matching :class:`aeat.domain.vat.VATRate`.

    Raises:
        :exc:`aeat.domain.vat.VatRateNotFoundError`: If no registered rate
            satisfies the query.
    """
    rates = load_vat_rate_table().get(member_state)
    if not rates:
        raise VatRateNotFoundError(f"no rates registered for member_state={member_state.value!r}")
    for rate in rates:
        if rate.kind is not kind:
            continue
        if rate.effective_from > on_date:
            continue
        if rate.effective_until is not None and on_date > rate.effective_until:
            continue
        return rate
    raise VatRateNotFoundError(
        f"no rate for member_state={member_state.value!r} kind={kind.value!r} on_date={on_date.isoformat()}"
    )


def cite(
    category: VATCategory,
    *,
    on: date | None = None,
    catalogue: VATCatalogue | None = None,
) -> str:
    """Return the canonical citation string for ``category``.

    Uses the first :class:`aeat.domain.vat.VatCitation` on the matching
    regulation as the canonical reference. The result includes a
    human-readable source label and the article reference so it is
    self-identifying when written to a log line.

    Args:
        category: The VAT category whose canonical citation is requested.
        on: Effective date used to resolve the committed catalogue.
        catalogue: Optional catalogue override.

    Returns:
        A canonical citation string such as
        ``"Ley 37/1992, Art. 90.Uno — <quoted_text>"``.

    Raises:
        :exc:`aeat.domain.vat.VatCategoryNotFoundError`: If ``category`` is
            absent from the catalogue.
    """
    if catalogue is None and on is None:
        raise VatCatalogueError("cite requires either an explicit catalogue or an effective date")
    if on is None:
        assert catalogue is not None
        return _render_citation(category, catalogue)
    return _render_citation(category, catalogue if catalogue is not None else resolve_catalogue(on=on))


def _render_citation(category: VATCategory, catalogue: VATCatalogue) -> str:
    regulation = catalogue.get(category)
    if regulation is None:
        raise VatCategoryNotFoundError(f"VAT category {category.value!r} not found in catalogue")
    citation = regulation.citations[0]
    source_label = _SOURCE_LABELS.get(citation.source.value, citation.source.value)
    return f"{source_label}, {citation.article}: {citation.quoted_text}"


_SOURCE_LABELS: dict[str, str] = {
    "ley-37-1992": "Ley 37/1992",
    "manual-iva-2025": "Manual práctico IVA 2025",
    "directive-2006-112-ec": "Directive 2006/112/EC",
    "other": "other",
}
"""Human-readable labels for each :class:`aeat.domain.vat.VatCitationSource`."""


__all__ = ["cite", "lookup_rate"]
