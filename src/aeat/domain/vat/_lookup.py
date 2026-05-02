"""Lookup helpers for the :mod:`aeat.domain.vat` substrate.

Exposes :func:`lookup_rate` for resolving a member-state / tier / date triple
against :data:`aeat.domain.vat.VAT_RATE_TABLE`, and :func:`cite` for rendering
the canonical citation string for a :class:`aeat.domain.vat.VATCategory`.
Both helpers are pure and side-effect free.
"""

from __future__ import annotations

from datetime import date

from ._catalogue import VAT_CATALOGUE_2025
from ._rates import VAT_RATE_TABLE
from ._schema import EUMemberState, VATCatalogue, VATCategory, VATRate, VATRateKind
from .errors import VatCategoryNotFoundError, VatRateNotFoundError


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
    rates = VAT_RATE_TABLE.get(member_state)
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
    catalogue: VATCatalogue | None = None,
) -> str:
    """Return the canonical citation string for ``category``.

    Uses the first :class:`aeat.domain.vat.VatCitation` on the matching
    regulation as the canonical reference. The result includes a
    human-readable source label and the article reference so it is
    self-identifying when written to a log line.

    Args:
        category: The VAT category whose canonical citation is requested.
        catalogue: Optional catalogue override; defaults to
            :data:`aeat.domain.vat.VAT_CATALOGUE_2025`.

    Returns:
        A canonical citation string such as
        ``"Ley 37/1992, Art. 90.Uno — <quoted_text_es>"``.

    Raises:
        :exc:`aeat.domain.vat.VatCategoryNotFoundError`: If ``category`` is
            absent from the catalogue.
    """
    cat = catalogue if catalogue is not None else VAT_CATALOGUE_2025
    regulation = cat.get(category)
    if regulation is None:
        raise VatCategoryNotFoundError(f"VAT category {category.value!r} not found in catalogue")
    citation = regulation.citations[0]
    source_label = _SOURCE_LABELS.get(citation.source.value, citation.source.value)
    return f"{source_label}, {citation.article} — {citation.quoted_text_es}"


_SOURCE_LABELS: dict[str, str] = {
    "ley-37-1992": "Ley 37/1992",
    "manual-iva-2025": "Manual práctico IVA 2025",
    "directive-2006-112-ec": "Directive 2006/112/EC",
    "other": "other",
}
"""Human-readable labels for each :class:`aeat.domain.vat.VatCitationSource`."""


__all__ = ["cite", "lookup_rate"]
