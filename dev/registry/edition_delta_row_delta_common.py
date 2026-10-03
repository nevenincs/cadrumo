"""Shared predecessor matching, authored-storage selectors and exact source-default reconciliation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from cadrumo.domain.calculations.registry.lineage_attestation import LineageAttestation

from . import edition_delta_fields as _edition_delta_fields
from . import edition_delta_lineage_attestation as _edition_delta_lineage_attestation
from . import edition_delta_source as _edition_delta_source
from .compiler.casilla_identity import LINEAGE_CLAIM_FIELDS


def candidate_indexes(
    inherited: Sequence[_edition_delta_source._Placed],
) -> tuple[dict[str, list[_edition_delta_source._Placed]], dict[str, list[_edition_delta_source._Placed]]]:
    """Index inherited predecessor rows by continuity lineage and by storage id."""
    by_lineage: dict[str, list[_edition_delta_source._Placed]] = {}
    by_storage_id: dict[str, list[_edition_delta_source._Placed]] = {}
    for placed in inherited:
        if (lineage := _edition_delta_source._lineage(placed.row)) is not None:
            by_lineage.setdefault(lineage, []).append(placed)
        by_storage_id.setdefault(_edition_delta_source._row_id(placed.row), []).append(placed)
    return by_lineage, by_storage_id


def pending_lineage_attestation(
    *,
    row: _edition_delta_source._Row,
    lineage: str | None,
    target: _edition_delta_source._Row,
    manifest: Mapping[str, object],
    predecessor: str,
    revision_id: str,
    storage_only: bool,
) -> LineageAttestation | None:
    """The attestation that carries ``target``'s continuity claim once its row is relocated, if one is needed."""
    if storage_only or lineage is None:
        return None
    if not any(claim in target for claim in LINEAGE_CLAIM_FIELDS):
        return None
    return _edition_delta_lineage_attestation._lineage_attestation(
        member=row,
        manifest=manifest,
        predecessor_revision_id=predecessor,
        revision_id=revision_id,
    )


def unsupported_nested_removals(removed_fields: Sequence[str]) -> tuple[str, ...]:
    """Removed field paths a casilla field override cannot express (anything nested beyond ``constraints.*``)."""
    return tuple(
        field
        for field in removed_fields
        if "." in field and not (field.startswith("constraints.") and field.count(".") == 1)
    )


def storage_rows(source: _edition_delta_source._EditionSource) -> Mapping[str, _edition_delta_source._Row]:
    """The edition's casilla rows as the loader stores them before lifting."""
    raw = source.table.get(_edition_delta_fields._CASILLAS, ())
    rows: dict[str, _edition_delta_source._Row] = {}
    if not isinstance(raw, list | tuple):
        return rows
    for row in raw:
        if isinstance(row, Mapping):
            stored = _edition_delta_source._as_row(row)
            rows[_edition_delta_source._row_id(stored)] = stored
    return rows


def reconcile_source_removals(
    fields: Mapping[str, object], removed_fields: tuple[str, ...], raw_baseline: Mapping[str, object]
) -> tuple[str, ...]:
    """Keep patched source references valid for the storage form the loader applies."""
    reconciled: list[str] = list(removed_fields)
    if _edition_delta_fields._ROW_SOURCE in fields:
        reconciled = [field for field in reconciled if field != _edition_delta_fields._ROW_SOURCE_ADDITIONS]
    elif (
        _edition_delta_fields._ROW_SOURCE_ADDITIONS in fields
        and _edition_delta_fields._ROW_SOURCE in raw_baseline
        and _edition_delta_fields._ROW_SOURCE not in reconciled
    ):
        reconciled.append(_edition_delta_fields._ROW_SOURCE)
    _reconcile_constraint_source_spellings(fields, raw_baseline, reconciled)
    return tuple(reconciled)


def _reconcile_constraint_source_spellings(
    fields: Mapping[str, object], raw_baseline: Mapping[str, object], reconciled: list[str]
) -> None:
    constraint_fields = fields.get(_edition_delta_fields._CONSTRAINTS)
    stored_constraints = raw_baseline.get(_edition_delta_fields._CONSTRAINTS)
    if not isinstance(constraint_fields, Mapping) or not isinstance(stored_constraints, Mapping):
        return
    for stated, displaced in (
        (_edition_delta_fields._ROW_SOURCE, _edition_delta_fields._ROW_SOURCE_ADDITIONS),
        (_edition_delta_fields._ROW_SOURCE_ADDITIONS, _edition_delta_fields._ROW_SOURCE),
    ):
        removal = f"{_edition_delta_fields._CONSTRAINTS}.{displaced}"
        if stated in constraint_fields and displaced in stored_constraints and removal not in reconciled:
            reconciled.append(removal)


def authored_override_selectors(manifest: Mapping[str, object]) -> frozenset[str]:
    """Predecessor row ids already claimed by authored overrides or removals."""
    claimed: set[str] = set()
    for operation_name in ("casilla_overrides", "casilla_removals"):
        raw = manifest.get(operation_name, ())
        if not isinstance(raw, list | tuple):
            continue
        claimed.update(
            str(selector.get("id"))
            for operation in raw
            if isinstance(operation, Mapping) and isinstance((selector := operation.get("selector")), Mapping)
        )
    return frozenset(claimed)
