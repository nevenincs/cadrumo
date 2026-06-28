"""Canonical citation renderer for :class:`NormativeReference`.

Provides :func:`short_title` for the prefix-and-number form
(``"Ley 35/2006"``) and :func:`cite` for the full citation including
the cited :class:`aeat.domain.normatives._schema.Articulo` and the
parent :attr:`aeat.domain.normatives._schema.NormativeReference.boe_id`.
The output strings are stable across releases and are the only
project-sanctioned form for embedding normative references in error
messages, reports, and audit logs.
"""

from __future__ import annotations

from ._schema import Articulo, NormativeKind, NormativeReference

_KIND_PREFIX: dict[NormativeKind, str] = {
    NormativeKind.LEY: "Ley",
    NormativeKind.REAL_DECRETO: "Real Decreto",
    NormativeKind.ORDEN_MINISTERIAL: "Orden",
    NormativeKind.REAL_DECRETO_LEY: "Real Decreto-ley",
}


def short_title(reference: NormativeReference) -> str:
    """Return the canonical short title for a reference.

    The short title is formed as ``"{prefix} {number}"`` per the
    Spanish-authoritative naming convention, e.g. ``"Ley 35/2006"`` or
    ``"Orden HAC/242/2025"``. It is the citation-ready form the rest
    of the project emits into error messages and reports.

    Args:
        reference: The :class:`aeat.domain.normatives._schema.NormativeReference`
            whose short title is wanted.

    Returns:
        A short citation string, e.g. ``"Ley 35/2006"``.
    """
    prefix = _KIND_PREFIX[reference.kind]
    return f"{prefix} {reference.number}"


def cite(reference: NormativeReference, articulo: Articulo) -> str:
    """Produce a canonical citation string for ``(reference, articulo)``.

    Example:
        >>> cite(ley_35_2006, articulo_32)
        'Ley 35/2006, art. 32 (BOE-A-2006-20764)'

    Args:
        reference: The parent normative.
        articulo: The cited article (must belong to ``reference``).

    Returns:
        A canonical citation string stable across releases.
    """
    return f"{short_title(reference)}, art. {articulo.numero} ({reference.boe_id})"
