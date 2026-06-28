"""Lookup helpers for :class:`NormativeCatalogue`."""

from __future__ import annotations

from ._errors import NormativeNotFoundError
from ._schema import Articulo, NormativeCatalogue, NormativeReference


def find_reference(catalogue: NormativeCatalogue, ref_id: str) -> NormativeReference:
    """Return the :class:`NormativeReference` keyed by ``ref_id``.

    Args:
        catalogue: The loaded catalogue to search.
        ref_id: Stable kebab-case id, e.g. ``"ley-35-2006"``.

    Returns:
        The matching reference.

    Raises:
        NormativeNotFoundError: If no reference with that id exists.
    """
    reference = catalogue.get(ref_id)
    if reference is None:
        raise NormativeNotFoundError(f"normative not found: {ref_id!r}")
    return reference


def find_articulo(
    catalogue: NormativeCatalogue,
    ref_id: str,
    numero: str,
) -> Articulo:
    """Return the :class:`Articulo` identified by ``(ref_id, numero)``.

    Args:
        catalogue: The loaded catalogue to search.
        ref_id: Stable kebab-case id of the parent reference.
        numero: Article number, e.g. ``"32"`` or ``"32.1.a"``.

    Returns:
        The matching :class:`Articulo`.

    Raises:
        NormativeNotFoundError: If the reference is missing or does not
            contain an article with that ``numero``.
    """
    reference = find_reference(catalogue, ref_id)
    for articulo in reference.articulos:
        if articulo.numero == numero:
            return articulo
    raise NormativeNotFoundError(f"normative {ref_id!r} does not codify articulo {numero!r}")
