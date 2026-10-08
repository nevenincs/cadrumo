"""Merge casilla rows and their lineage attestations across registry editions."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping

from cadrumo.domain.calculations.registry.errors import RegistryLoadError
from cadrumo.domain.calculations.registry.modelo_localization import as_toml_array
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaEvolutionKind
from dev.registry.compiler._toml_helpers import as_toml_table as _as_toml_table

from . import casilla_identity as _casilla_identity
from .casilla_identity import LINEAGE_CLAIM_FIELDS
from .casilla_storage_delta import _apply_casilla_positions, _apply_casilla_storage_delta
from .loader_fields import _INHERITED_SECTION, _RETIREMENT_SECTION

type _LabelOrigins = tuple[str | None, ...]


def inherit_casillas(
    context: str,
    *,
    revision_id: str,
    predecessor_id: str,
    inherited: tuple[object, ...],
    inherited_label_origins: _LabelOrigins | None,
    inherited_text_origins: _LabelOrigins | None,
    successor: Mapping[str, object],
) -> tuple[tuple[object, ...], _LabelOrigins, _LabelOrigins]:
    """Merge inherited casillas, retaining row and text origins beside their data."""
    _validate_origin_count(context, inherited, inherited_label_origins)
    stated = as_toml_array(successor.get(_INHERITED_SECTION, ()))
    if stated is None:
        raise RegistryLoadError(f"{context}: casillas must be an array")
    carried = _carried_origins(inherited, inherited_label_origins, inherited_text_origins)
    inherited, carried, overridden, relabelled = _apply_casilla_storage_delta(
        context,
        predecessor_id=predecessor_id,
        inherited=inherited,
        origins=carried,
        successor=successor,
    )
    retired = retired_lineages(successor, revision_id)
    superseders = _stated_rows_by_lineage(context, stated, retired)
    _refuse_ambiguous_lineages(context, inherited, superseders)
    rows, origins, kept_lineage_by_id, superseded = _merge_inherited_rows(
        context,
        predecessor_id,
        inherited,
        carried,
        retired,
        superseders,
        overridden,
        relabelled,
    )
    _append_stated_rows(context, stated, rows, origins, kept_lineage_by_id, superseded)
    rows, origins = _apply_casilla_positions(context, rows, origins, successor)
    return (
        tuple(rows),
        tuple(statement for statement, _text in origins),
        tuple(text for _statement, text in origins),
    )


def _validate_origin_count(
    context: str,
    inherited: tuple[object, ...],
    label_origins: _LabelOrigins | None,
) -> None:
    if label_origins is not None and len(label_origins) != len(inherited):
        raise RegistryLoadError(
            f"{context}: the predecessor's label origins cover {len(label_origins)} of its {len(inherited)} casillas"
        )


def _carried_origins(
    inherited: tuple[object, ...],
    label_origins: _LabelOrigins | None,
    text_origins: _LabelOrigins | None,
) -> list[tuple[str | None, str | None]]:
    return [
        (
            None if label_origins is None else label_origins[index],
            None if text_origins is None else text_origins[index],
        )
        for index in range(len(inherited))
    ]


def _refuse_ambiguous_lineages(
    context: str,
    inherited: tuple[object, ...],
    superseders: Mapping[str, object],
) -> None:
    counts = Counter(lineage for row in inherited if (lineage := _casilla_identity._row_lineage(row)) is not None)
    ambiguous = sorted(lineage for lineage in superseders if counts[lineage] > 1)
    if ambiguous:
        raise RegistryLoadError(
            f"{context}: the predecessor carries lineage {ambiguous!r} on more than one row, so a stated row "
            "carrying it cannot say which one supersedes"
        )


def _merge_inherited_rows(
    context: str,
    predecessor_id: str,
    inherited: tuple[object, ...],
    carried: list[tuple[str | None, str | None]],
    retired: frozenset[str],
    superseders: Mapping[str, object],
    storage_overridden: frozenset[str],
    storage_relabelled: frozenset[str],
) -> tuple[list[object], list[tuple[str | None, str | None]], dict[str, str | None], set[str]]:
    rows: list[object] = []
    origins: list[tuple[str | None, str | None]] = []
    kept_lineage_by_id: dict[str, str | None] = {}
    superseded: set[str] = set()
    for index, row in enumerate(inherited):
        include, effective, origin, replaced, kept = _merge_inherited_row(
            context,
            predecessor_id,
            row,
            carried[index],
            retired,
            superseders,
            storage_overridden,
            storage_relabelled,
        )
        if include:
            rows.append(effective)
            origins.append(origin)
        if replaced is not None:
            superseded.add(replaced)
        if kept is not None:
            row_id, lineage = kept
            kept_lineage_by_id[row_id] = lineage
    return rows, origins, kept_lineage_by_id, superseded


def _merge_inherited_row(
    context: str,
    predecessor_id: str,
    row: object,
    carried: tuple[str | None, str | None],
    retired: frozenset[str],
    superseders: Mapping[str, object],
    storage_overridden: frozenset[str],
    storage_relabelled: frozenset[str],
) -> tuple[bool, object, tuple[str | None, str | None], str | None, tuple[str, str | None] | None]:
    lineage = _casilla_identity._row_lineage(row)
    if _is_retired_lineage(lineage, retired):
        return False, row, (None, None), None, None
    has_superseder, superseder = _superseding_row(lineage, superseders)
    if has_superseder:
        return True, superseder, (None, None), lineage, None
    row_id = _casilla_identity._row_id(row)
    effective = row if row_id in storage_overridden else without_lineage_claims(row)
    statement, text = carried
    origin = (
        None if row_id in storage_overridden else statement or predecessor_id,
        None if row_id in storage_relabelled else text or statement or predecessor_id,
    )
    kept = None if row_id is None else (row_id, lineage)
    return True, effective, origin, None, kept


def _is_retired_lineage(lineage: str | None, retired: frozenset[str]) -> bool:
    return lineage is not None and lineage in retired


def _superseding_row(lineage: str | None, superseders: Mapping[str, object]) -> tuple[bool, object]:
    if lineage is None or lineage not in superseders:
        return False, None
    return True, superseders[lineage]


def _append_stated_rows(
    context: str,
    stated: tuple[object, ...],
    rows: list[object],
    origins: list[tuple[str | None, str | None]],
    kept_lineage_by_id: Mapping[str, str | None],
    superseded: set[str],
) -> None:
    for row in stated:
        lineage = _casilla_identity._row_lineage(row)
        row_id = _casilla_identity._row_id(row)
        if row_id is not None and row_id in kept_lineage_by_id:
            raise RegistryLoadError(
                f"{context}: stated casilla {row_id!r} of lineage {_lineage_label(lineage)} collides with the "
                f"inherited casilla {row_id!r} of lineage {_lineage_label(kept_lineage_by_id[row_id])}; a stated "
                "row supersedes only the inherited row carrying its own lineage, so declare the repurpose by "
                "keeping the lineage, or retire the inherited lineage"
            )
        if lineage is None or lineage not in superseded:
            rows.append(row)
            origins.append((None, None))


def without_lineage_claims(row: object) -> object:
    """Return ``row`` without its claims about its predecessor, or ``row`` itself when it states none."""
    table = _as_toml_table(row)

    if table is None or not any(field in table for field in LINEAGE_CLAIM_FIELDS):
        return row

    return {key: value for key, value in table.items() if key not in LINEAGE_CLAIM_FIELDS}


def _stated_rows_by_lineage(
    context: str,
    stated: tuple[object, ...],
    retired: frozenset[str],
) -> dict[str, object]:

    by_lineage: dict[str, object] = {}

    for row in stated:
        lineage = _casilla_identity._row_lineage(row)

        if lineage is None:
            continue

        if lineage in retired:
            raise RegistryLoadError(
                f"{context}: states a casilla of lineage {lineage!r}, which the same edition retires",
            )

        if lineage in by_lineage:
            raise RegistryLoadError(
                f"{context}: states more than one casilla of lineage {lineage!r}, so neither can supersede "
                "the inherited row",
            )

        by_lineage[lineage] = row

    return by_lineage


def retired_lineages(successor: Mapping[str, object], revision_id: str) -> frozenset[str]:
    """Return the lineages the successor withdraws from what it inherits.

    A lineage is withdrawn by a ``retired`` evolution into the successor, or as

    a source of a structural succession into it, which is that withdrawal's

    single declaration.

    """
    evolutions = as_toml_array(successor.get(_RETIREMENT_SECTION, ())) or ()

    retired: set[str] = set()

    for raw_evolution in evolutions:
        evolution = _as_toml_table(raw_evolution)

        if evolution is None or evolution.get("to_revision") != revision_id:
            continue

        lineage = evolution.get("continuidad_id")

        if evolution.get("evolution_kind") == CasillaEvolutionKind.RETIRED and isinstance(lineage, str):
            retired.add(lineage)

    from cadrumo.domain.calculations.registry.casilla_structural_succession import CasillaStructuralSuccession

    for raw_relation in as_toml_array(successor.get("casilla_structural_successions", ())) or ():
        relation = CasillaStructuralSuccession.model_validate(raw_relation)

        if relation.to_revision == revision_id:
            retired.update(relation.source_lineages)

    return frozenset(retired)


def _lineage_label(lineage: str | None) -> str:

    return repr(lineage) if lineage is not None else "(none declared)"
