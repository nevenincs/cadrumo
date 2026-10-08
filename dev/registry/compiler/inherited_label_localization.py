"""Apply inherited casilla localization and loader-owned inheritance markers."""

from __future__ import annotations

from cadrumo.domain.calculations.registry.errors import (
    RegistryLoadError,
)
from cadrumo.domain.calculations.registry.modelo_localization import (
    ModeloLocalizationFieldKind,
    as_toml_array,
    casilla_occurrence_locale_key,
)

from ._toml_helpers import as_toml_table as _as_toml_table
from .casilla_inheritance import _LabelOrigins
from .loader_fields import (
    _INHERITED_SECTION,
    _ROW_INHERITED_FROM_FIELD,
)


def _enroll_inherited_label_fallbacks(
    context: str,
    *,
    modelo_id: str,
    payload: dict[str, object],
    label_origins: _LabelOrigins,
) -> dict[str, object]:
    """Give every inherited casilla the occurrence key of the edition that last stated it.

    Enrolment keys an inherited row to the edition it now sits in, which is the
    right identity, but the label catalogue is authored per edition and holds
    the row's text only under the key of the edition that stated it. That key
    joins the row's resolution chain directly after its own occurrence key and
    ahead of its continuity key: an entry the successor authors for the row
    still wins, the stated edition's exact text comes next, and the lineage-wide
    text stays the last tier. A row whose chain resolves nowhere still raises on
    lookup, exactly as before.

    An alias resolves through one key with no chain, so an inherited row that
    carries aliases is refused here instead of loading with alias labels that
    raise on first read.
    """
    casillas = as_toml_array(payload.get(_INHERITED_SECTION))
    if casillas is None or len(casillas) != len(label_origins):
        raise RegistryLoadError(
            f"{context}: label origins cover {len(label_origins)} casillas but enrolment produced "
            f"{'no casilla array' if casillas is None else len(casillas)}",
        )
    enrolled = tuple(
        _enroll_label_fallback(context, modelo_id, casilla, origin)
        for casilla, origin in zip(casillas, label_origins, strict=True)
    )
    return {**payload, _INHERITED_SECTION: enrolled}


def _enroll_label_fallback(
    context: str,
    modelo_id: str,
    casilla: object,
    origin: str | None,
) -> object:
    table = None if origin is None else _as_toml_table(casilla)
    if table is None or origin is None:
        return casilla
    keys = table.get("localization_keys")
    casilla_id = table.get("id")
    # A row enrolment could not key is left for typed construction to refuse.
    if not isinstance(casilla_id, str) or not isinstance(keys, tuple):
        return casilla
    if table.get("aliases"):
        raise RegistryLoadError(
            f"{context}: inherited casilla {casilla_id!r} carries aliases, whose labels resolve only under "
            f"this edition's key and have no fallback to {origin!r}; state the row in this edition",
        )
    fallback = casilla_occurrence_locale_key(modelo_id, origin, casilla_id, ModeloLocalizationFieldKind.LABEL)
    return {**table, "localization_keys": (*keys[:1], fallback, *keys[1:])}


def _mark_inherited_casillas(
    context: str,
    *,
    payload: dict[str, object],
    label_origins: _LabelOrigins | None,
) -> dict[str, object]:
    """Give every inherited casilla the ``inherited_from`` marker naming the edition that last stated it.

    The marker is the label origins, the one record of where each row is
    stated, carried onto the typed row so a consumer can tell a stated row from
    an inherited one without re-deriving it. A row stated in this edition keeps
    the marker unset.

    Raises:
        RegistryLoadError: When any casilla row authors the marker, since only
            materialisation knows where a row is stated.
    """
    casillas = as_toml_array(payload.get(_INHERITED_SECTION)) or ()
    authored = _authored_inheritance_markers(casillas)
    if authored:
        raise RegistryLoadError(
            f"{context}: casillas {authored!r} author {_ROW_INHERITED_FROM_FIELD}, which the loader sets on the "
            "rows an edition inherits from its declared predecessor; remove it",
        )
    if label_origins is None:
        return payload
    if len(casillas) != len(label_origins):
        raise RegistryLoadError(
            f"{context}: label origins cover {len(label_origins)} of the edition's {len(casillas)} casillas",
        )
    marked = _marked_casillas(casillas, label_origins)
    return {**payload, _INHERITED_SECTION: marked}


def _authored_inheritance_markers(casillas: tuple[object, ...]) -> list[str]:
    return sorted(
        str(table.get("id"))
        for row in casillas
        if (table := _as_toml_table(row)) is not None and _ROW_INHERITED_FROM_FIELD in table
    )


def _marked_casillas(casillas: tuple[object, ...], origins: _LabelOrigins) -> tuple[object, ...]:
    marked: list[object] = []
    for casilla, origin in zip(casillas, origins, strict=True):
        table = None if origin is None else _as_toml_table(casilla)
        marked.append(casilla if table is None else {**table, _ROW_INHERITED_FROM_FIELD: origin})
    return tuple(marked)
