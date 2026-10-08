"""Apply edition-declared source and legal reference defaults to revision rows."""

from __future__ import annotations

from collections.abc import Mapping

from cadrumo.domain.calculations.registry.errors import (
    RegistryLoadError,
)
from cadrumo.domain.calculations.registry.keyed_families import (
    family_source_default_fields,
)
from cadrumo.domain.calculations.registry.modelo_localization import (
    as_toml_array,
)

from . import casilla_identity as _casilla_identity
from ._toml_helpers import as_toml_table as _as_toml_table
from .loader_fields import (
    _EDITION_ORDEN_FIELD,
    _EDITION_SOURCE_DEFAULT_FIELD,
    _INHERITED_SECTION,
    _ROW_CONSTRAINTS_FIELD,
    _ROW_LEGAL_FIELD,
    _ROW_SOURCE_ADDITIONS_FIELD,
    _ROW_SOURCE_FIELD,
)


def _apply_edition_reference_defaults(context: str, table: Mapping[str, object]) -> Mapping[str, object]:
    """Fill the edition's declared reference defaults into the casilla rows that state none.

    Three families, each defaulted from its own manifest key: ``casillas``
    from ``casilla_source_refs``, ``bindings`` from ``binding_source_refs``, and
    ``formulas`` from ``formula_source_refs``. The member-side rule is one rule
    for all three; only the casilla family also defaults a ``constraints``
    table and a ``legal_refs``.

    Two defaults for the casilla family, both declared once on the edition's
    manifest:

    - ``casilla_source_refs`` becomes the ``source_refs`` of every casilla row,
      and of every row's ``constraints`` table, that states no ``source_refs``.
      A row or constraints table stating ``additional_source_refs`` instead
      takes the default followed by its additions, duplicates removed and the
      default first, and the additions key is consumed;
    - ``orden_aplicabilidad``, the edition's approving ordenes, becomes the
      ``legal_refs`` of every casilla row and ``constraints`` table that states
      no ``legal_refs``.

    A stated ``source_refs`` or ``legal_refs`` is kept whole, including a stated
    empty array, which typed construction then refuses. A default is never
    merged into a stated value; only additions extend one.

    It runs on the materialised edition, so an inherited CASILLA is defaulted
    from the edition it now sits in: a casilla carries its own lineage and the
    edition it lands in grounds it. Additions are the row's own and so extend
    the default of the edition the row now sits in.

    A keyed-family member is the other case, and :func:`_pin_family_source_default`
    has already bound it to the default effective where it was stated, so it
    arrives here carrying ``source_refs`` and is left alone. Re-grounding it
    would make the successor's source attest a row that source never saw.

    Returns the identical table when it fills nothing, so an edition declaring
    no default and no additions reaches typed construction exactly as authored.
    A default that is absent, empty or not an array fills nothing and is left to
    typed construction, as is a casilla section or row that is not the shape it
    should be.

    Raises:
        RegistryLoadError: When a row or constraints table states both
            ``source_refs`` and ``additional_source_refs``, states additions that
            are not a non-empty array of reference ids, or states additions in
            an edition declaring no ``casilla_source_refs`` for them to extend.
    """
    source_default = as_toml_array(table.get(_EDITION_SOURCE_DEFAULT_FIELD)) or ()
    orden_default = as_toml_array(table.get(_EDITION_ORDEN_FIELD)) or ()
    filled = _default_casilla_section(context, table, source_default, orden_default)
    filled.update(_default_keyed_family_sections(context, table))
    return {**table, **filled} if filled else table


def _default_casilla_section(
    context: str,
    table: Mapping[str, object],
    source_default: tuple[object, ...],
    orden_default: tuple[object, ...],
) -> dict[str, object]:
    filled: dict[str, object] = {}
    rows = as_toml_array(table.get(_INHERITED_SECTION, ()))
    if rows:
        defaulted = tuple(
            default_row_references(context, row, source_default=source_default, orden_default=orden_default)
            for row in rows
        )
        if any(new is not old for new, old in zip(defaulted, rows, strict=True)):
            filled[_INHERITED_SECTION] = defaulted
    return filled


def _default_keyed_family_sections(context: str, table: Mapping[str, object]) -> dict[str, object]:
    filled: dict[str, object] = {}
    for section, default_field in family_source_default_fields():
        section_rows = as_toml_array(table.get(section, ()))
        if not section_rows:
            continue
        family_default = as_toml_array(table.get(default_field)) or ()
        defaulted = tuple(
            _default_family_row_references(
                f"{context}: {section}", row, source_default=family_default, default_field=default_field
            )
            for row in section_rows
        )
        if any(new is not old for new, old in zip(defaulted, section_rows, strict=True)):
            filled[section] = defaulted
    return filled


def _default_family_row_references(
    context: str,
    row: object,
    *,
    source_default: tuple[object, ...],
    default_field: str,
) -> object:
    """Return one binding or formula row with the edition's family default filled in.

    The casilla rule without the parts casillas alone have: these families carry
    no ``constraints`` table to default alongside the row, and no
    ``orden_aplicabilidad`` default -- the approving ordenes ground a box's
    existence, not a binding's record position -- so a family row's
    ``legal_refs`` stays exactly as authored.
    """
    table = _as_toml_table(row)
    if table is None:
        return row
    filled = _defaulted_references(
        f"{context} {_casilla_identity._row_id(table)!r}",
        table,
        source_default=source_default,
        orden_default=(),
        default_field=default_field,
    )
    return row if filled is table else filled


def default_row_references(
    context: str,
    row: object,
    *,
    source_default: tuple[object, ...],
    orden_default: tuple[object, ...],
) -> object:
    """Return ``row`` with its references and its constraints' defaulted, or ``row`` itself when nothing changes.

    ``row`` is frozen TOML: an array is a tuple, and a list is not read as one.
    """
    table = _as_toml_table(row)
    if table is None:
        return row
    subject = f"{context}: casilla {_casilla_identity._row_id(table)!r}"
    filled = _defaulted_references(subject, table, source_default=source_default, orden_default=orden_default)
    constraints = _as_toml_table(table.get(_ROW_CONSTRAINTS_FIELD))
    if constraints is not None:
        filled_constraints = _defaulted_references(
            f"{subject} constraints", constraints, source_default=source_default, orden_default=orden_default
        )
        if filled_constraints is not constraints:
            filled = {**filled, _ROW_CONSTRAINTS_FIELD: filled_constraints}
    return row if filled is table else filled


def _defaulted_references(
    subject: str,
    table: Mapping[str, object],
    *,
    source_default: tuple[object, ...],
    orden_default: tuple[object, ...],
    default_field: str = _EDITION_SOURCE_DEFAULT_FIELD,
) -> Mapping[str, object]:
    """Return one row or constraints table with its references resolved, or ``table`` itself when nothing changes."""
    updates: dict[str, object] = {}
    if _ROW_SOURCE_ADDITIONS_FIELD in table:
        updates[_ROW_SOURCE_FIELD] = _extended_source_default(subject, table, source_default, default_field)
    elif source_default and _ROW_SOURCE_FIELD not in table:
        updates[_ROW_SOURCE_FIELD] = source_default
    if orden_default and _ROW_LEGAL_FIELD not in table:
        updates[_ROW_LEGAL_FIELD] = orden_default
    if not updates:
        return table
    kept = {key: value for key, value in table.items() if key != _ROW_SOURCE_ADDITIONS_FIELD}
    return {**kept, **updates}


def _extended_source_default(
    subject: str,
    table: Mapping[str, object],
    source_default: tuple[object, ...],
    default_field: str = _EDITION_SOURCE_DEFAULT_FIELD,
) -> tuple[object, ...]:
    """Return the edition default followed by the table's additions, each reference once, the default first.

    A default holding anything but reference ids is concatenated unchanged and
    left to typed construction, which refuses it with the field's own error.
    """
    if _ROW_SOURCE_FIELD in table:
        raise RegistryLoadError(
            f"{subject} states both {_ROW_SOURCE_FIELD} and {_ROW_SOURCE_ADDITIONS_FIELD}; {_ROW_SOURCE_FIELD} "
            f"replaces the edition's {default_field} whole while {_ROW_SOURCE_ADDITIONS_FIELD} "
            "extends it, so state one of them",
        )
    if not source_default:
        raise RegistryLoadError(
            f"{subject} states {_ROW_SOURCE_ADDITIONS_FIELD}, but the edition declares no "
            f"{default_field} for them to extend; state {_ROW_SOURCE_FIELD} instead",
        )
    additions = as_toml_array(table.get(_ROW_SOURCE_ADDITIONS_FIELD))
    if not additions or not all(isinstance(item, str) for item in additions):
        raise RegistryLoadError(
            f"{subject} {_ROW_SOURCE_ADDITIONS_FIELD} must be a non-empty array of source reference ids; "
            "omit the key to take the edition default alone",
        )
    if not all(isinstance(item, str) for item in source_default):
        return (*source_default, *additions)
    return tuple(dict.fromkeys((*source_default, *additions)))
