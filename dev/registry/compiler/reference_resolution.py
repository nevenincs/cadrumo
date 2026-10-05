"""Resolve inherited casilla references against declarations in the materialised edition."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from cadrumo.domain.calculations.registry.errors import (
    RegistryLoadError,
)
from cadrumo.domain.calculations.registry.modelo_localization import (
    as_toml_array,
)
from dev.registry.compiler.identifier_lineage import identifier_lineage

from . import casilla_identity as _casilla_identity
from . import revision_materialisation as _revision_materialisation
from ._toml_helpers import as_toml_table as _as_toml_table
from .casilla_inheritance import _LabelOrigins
from .loader_fields import (
    _INHERITED_SECTION,
    _REFERENCE_SECTIONS,
)


def _resolve_inherited_references(
    source_path: Path,
    *,
    revision_id: str,
    table: Mapping[str, object],
    label_origins: _LabelOrigins,
) -> Mapping[str, object]:
    """Point every inherited casilla's formula and binding references at this edition's own declarations.

    An inherited row arrives with the references its stating edition authored,
    which name that edition's formulas and bindings. Each reference is replaced
    by the declaration of this edition carrying the same lineage, as
    :func:`~dev.registry.compiler.identifier_lineage.identifier_lineage`
    defines it: the reference's lineage is taken against the stating edition,
    each declaration's against this one. A reference whose lineage no
    declaration of this edition carries is refused rather than kept, since the
    pointer it holds names another edition's declaration.

    Stated rows are returned untouched; their references are this edition's
    own, and reference validation checks them as authored. A field or row that
    is not the shape it should be is left for typed construction to refuse.

    Returns the identical table when no reference changes, which is always the
    case once identifiers stop embedding an edition key and every inherited
    reference resolves to itself.
    """
    context = f"{source_path}: revision {revision_id!r}"
    rows = _revision_materialisation._raw_casilla_rows(source_path, revision_id, table)
    if len(rows) != len(label_origins):
        raise RegistryLoadError(
            f"{context}: label origins cover {len(label_origins)} of the edition's {len(rows)} casillas",
        )
    declarations = edition_reference_declarations(table, revision_id)
    resolved = tuple(
        row
        if origin is None
        else resolve_row_references(context, row, origin=origin, revision_id=revision_id, declarations=declarations)
        for row, origin in zip(rows, label_origins, strict=True)
    )
    if all(new is old for new, old in zip(resolved, rows, strict=True)):
        return table
    return {**table, _INHERITED_SECTION: resolved}


def edition_reference_declarations(
    table: Mapping[str, object],
    revision_id: str,
) -> Mapping[str, Mapping[str, tuple[str, ...]]]:
    """Group the edition's declarations of every section a casilla reference names, each by lineage.

    This is the candidate set :func:`resolve_row_references` resolves an
    inherited row's references against. ``table`` is the frozen materialised
    edition.
    """
    return {section: _declarations_by_lineage(table, section, revision_id) for section in _REFERENCE_SECTIONS.values()}


def _declarations_by_lineage(
    table: Mapping[str, object],
    section: str,
    revision_id: str,
) -> Mapping[str, tuple[str, ...]]:
    """Group the edition's declared identifiers of one section by lineage."""
    by_lineage: dict[str, dict[str, None]] = {}
    for raw in as_toml_array(table.get(section, ())) or ():
        declaration_id = _casilla_identity._row_id(raw)
        if declaration_id is not None:
            by_lineage.setdefault(identifier_lineage(declaration_id, revision_id), {})[declaration_id] = None
    return {lineage: tuple(ids) for lineage, ids in by_lineage.items()}


def resolve_row_references(
    context: str,
    row: object,
    *,
    origin: str,
    revision_id: str,
    declarations: Mapping[str, Mapping[str, tuple[str, ...]]],
) -> object:
    """Return ``row`` with its references resolved, or ``row`` itself when each already names its target.

    ``row`` is frozen TOML: a reference array is a tuple, and a list is left unresolved.
    """
    table = _as_toml_table(row)
    if table is None:
        return row
    casilla_id = _casilla_identity._row_id(table)
    updates: dict[str, object] = {}
    for field, section in _REFERENCE_SECTIONS.items():
        value = table.get(field)

        def resolve(reference: str, *, field: str = field, section: str = section) -> str:
            return _resolve_reference(
                context,
                casilla_id=casilla_id,
                field=field,
                reference=reference,
                origin=origin,
                revision_id=revision_id,
                section=section,
                declarations=declarations[section],
            )

        if isinstance(value, str):
            resolved: object = resolve(value)
        elif (items := as_toml_array(value)) is not None:
            resolved = tuple(resolve(item) if isinstance(item, str) else item for item in items)
        else:
            continue
        if resolved != value:
            updates[field] = resolved
    if not updates:
        return row
    return {**table, **updates}


def _resolve_reference(
    context: str,
    *,
    casilla_id: str | None,
    field: str,
    reference: str,
    origin: str,
    revision_id: str,
    section: str,
    declarations: Mapping[str, tuple[str, ...]],
) -> str:
    lineage = identifier_lineage(reference, origin)
    candidates = declarations.get(lineage, ())
    if len(candidates) == 1:
        return candidates[0]
    found = (
        f"{len(candidates)} {section} declarations {list(candidates)!r}" if candidates else f"no {section} declaration"
    )
    raise RegistryLoadError(
        f"{context}: inherited casilla {casilla_id!r} {field} reference {reference!r}, stated in revision "
        f"{origin!r}, has lineage {lineage!r}, and revision {revision_id!r} carries {found} of that lineage; "
        "an inherited reference must resolve to exactly one of this edition's own declarations, so declare it "
        "here or state the row in this edition",
    )
