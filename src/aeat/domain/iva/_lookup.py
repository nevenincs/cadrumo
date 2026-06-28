"""Lookup helpers for IVA registry data.

:func:`lookup_rate` resolves :class:`EUMemberState` and :class:`IvaRateKind`
queries into :class:`IvaRateRecord` records loaded by
:func:`aeat.domain.iva.load_iva_rate_table`; :func:`cite` renders
:class:`IvaCategory` catalogue citations from an :class:`IvaCatalogue`.
"""

from __future__ import annotations

from datetime import date

from ._catalogue import resolve_catalogue
from ._errors import IvaCatalogueError, IvaCategoryNotFoundError, IvaRateNotFoundError
from ._rates import load_iva_rate_table
from ._schema import EUMemberState, IvaCatalogue, IvaCategory, IvaRateKind, IvaRateRecord


def lookup_rate(
    member_state: EUMemberState,
    kind: IvaRateKind,
    on_date: date,
) -> IvaRateRecord:
    """Return the :class:`aeat.domain.iva.IvaRateRecord` matching the supplied query.

    Iterates the rates registered for ``member_state`` in
    :data:`aeat.domain.iva.IVA_RATE_TABLE` and returns the first record whose
    :attr:`aeat.domain.iva.IvaRateRecord.kind` matches ``kind`` and whose
    effective window covers ``on_date``.

    Args:
        member_state: The EU member state whose rate is requested.
        kind: The rate tier (general / reduced / ...).
        on_date: The effective date for the lookup.

    Returns:
        The matching :class:`aeat.domain.iva.IvaRateRecord`.

    Raises:
        IvaRateNotFoundError: If no registered rate satisfies the query.
    """
    rates = load_iva_rate_table().get(member_state)
    if not rates:
        raise IvaRateNotFoundError(f"no rates registered for member_state={member_state.value!r}")
    for rate in rates:
        if rate.kind is not kind:
            continue
        if rate.effective_from > on_date:
            continue
        if rate.effective_until is not None and on_date > rate.effective_until:
            continue
        return rate
    raise IvaRateNotFoundError(
        f"no rate for member_state={member_state.value!r} kind={kind.value!r} on_date={on_date.isoformat()}",
    )


def cite(
    category: IvaCategory,
    *,
    on: date | None = None,
    catalogue: IvaCatalogue | None = None,
) -> str:
    """Return the canonical citation string for ``category``.

    Uses the first :class:`aeat.domain.iva.IvaCitation` on the matching
    regulation as the canonical reference. The result includes a
    human-readable source label and the article reference so it is
    self-identifying when written to a log line.

    Args:
        category: The IVA category whose canonical citation is requested.
        on: Effective date used to resolve the committed catalogue.
        catalogue: Optional catalogue override.

    Returns:
        A canonical citation string such as
        ``"Ley 37/1992, Art. 90.Uno — <quoted_text>"``.

    Raises:
        IvaCatalogueError: If both ``catalogue`` and ``on`` are ``None``.
    """
    if catalogue is None and on is None:
        raise IvaCatalogueError("cite requires either an explicit catalogue or an effective date")
    if on is None:
        assert catalogue is not None
        return _render_citation(category, catalogue)
    return _render_citation(category, catalogue if catalogue is not None else resolve_catalogue(on=on))


def _render_citation(category: IvaCategory, catalogue: IvaCatalogue) -> str:
    regulation = catalogue.get(category)
    if regulation is None:
        raise IvaCategoryNotFoundError(f"IVA category {category.value!r} not found in catalogue")
    citation = regulation.citations[0]
    source_label = _SOURCE_LABELS.get(citation.source.value, citation.source.value)
    return f"{source_label}, {citation.article}: {citation.quoted_text}"


_SOURCE_LABELS: dict[str, str] = {
    "ley-37-1992": "Ley 37/1992",
    "manual-iva-2025": "Manual práctico IVA 2025",
    "directive-2006-112-ec": "Directive 2006/112/EC",
    "other": "other",
}
"""Human-readable labels for each :class:`aeat.domain.iva.IvaCitationSource`."""


__all__ = ["cite", "lookup_rate"]
