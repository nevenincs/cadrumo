"""Select row drops and storage overrides using unique lineage/storage matches."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from cadrumo.domain.calculations.registry.lineage_attestation import LineageAttestation

from . import edition_delta_lineage_attestation as _edition_delta_lineage_attestation
from . import edition_delta_payload as _edition_delta_payload
from . import edition_delta_row_delta_common as _edition_delta_row_delta_common
from . import edition_delta_source as _edition_delta_source
from . import edition_delta_types as _edition_delta_types
from .compiler.casilla_identity import LINEAGE_CLAIM_FIELDS
from .compiler.casilla_inheritance import without_lineage_claims


@dataclass(frozen=True)
class _SelectionContext:
    revision_id: str
    predecessor: str
    inherited: Sequence[_edition_delta_source._Placed]
    lifts: Mapping[str, _edition_delta_source._Lift]
    source: _edition_delta_source._EditionSource
    defaults: _edition_delta_source._Defaults
    storage_only: bool


@dataclass
class DropSelection:
    """Dropped row ids, kept-row reasons, generated overrides and attestations chosen for one edition."""

    drops: set[str] = field(default_factory=set)
    kept: Counter[_edition_delta_types.KeptReason] = field(default_factory=Counter)
    not_exact: list[str] = field(default_factory=list)
    overrides: list[_edition_delta_source._Row] = field(default_factory=list)
    attestations: list[LineageAttestation] = field(default_factory=list)
    matched_storage_ids: set[str] = field(default_factory=set)


def _candidate_for_row(
    row: _edition_delta_source._Row,
    by_lineage: Mapping[str, list[_edition_delta_source._Placed]],
    by_storage_id: Mapping[str, list[_edition_delta_source._Placed]],
    claimed: frozenset[str],
) -> _edition_delta_source._Placed | None:
    row_id, lineage = _edition_delta_source._row_id(row), _edition_delta_source._lineage(row)
    lineage_candidates = by_lineage.get(lineage, []) if lineage is not None else []
    storage_candidates = by_storage_id.get(row_id, []) if lineage is None else []
    candidates = lineage_candidates or storage_candidates
    if len(candidates) != 1:
        return None
    candidate = candidates[0]
    candidate_id = _edition_delta_source._row_id(candidate.row)
    if candidate_id in claimed and candidate_id != row_id:
        return None
    if not lineage_candidates and lineage is None and _edition_delta_source._lineage(candidate.row) is not None:
        return None
    return candidate


def _override_difference(
    context: _SelectionContext,
    candidate: _edition_delta_source._Placed,
    materialised: _edition_delta_source._Row,
    target: _edition_delta_source._Row,
) -> tuple[Mapping[str, object], tuple[str, ...], tuple[str, ...]]:
    baseline = _edition_delta_source._lift(
        materialised,
        source_default=context.defaults.source_refs,
        orden=context.defaults.orden,
    ).row
    raw_baseline = _edition_delta_source._as_row(without_lineage_claims(candidate.row))
    fields, removed_fields = _edition_delta_payload._storage_difference(baseline, target)
    removed_fields = _edition_delta_payload._existing_storage_removals(raw_baseline, removed_fields)
    removed_fields = _edition_delta_row_delta_common.reconcile_source_removals(fields, removed_fields, raw_baseline)
    return fields, removed_fields, _edition_delta_row_delta_common.unsupported_nested_removals(removed_fields)


def _record_changed_row(
    context: _SelectionContext,
    result: DropSelection,
    row_id: str,
    row: _edition_delta_source._Row,
    candidate: _edition_delta_source._Placed,
    materialised: _edition_delta_source._Row,
) -> None:
    target = context.lifts[row_id].row
    lineage = _edition_delta_source._lineage(row)
    pending = _edition_delta_row_delta_common.pending_lineage_attestation(
        row=row,
        lineage=lineage,
        target=target,
        manifest=context.source.manifest,
        predecessor=context.predecessor,
        revision_id=context.revision_id,
        storage_only=context.storage_only,
    )
    requires_attestation = (
        not context.storage_only and lineage is not None and any(claim in target for claim in LINEAGE_CLAIM_FIELDS)
    )
    if requires_attestation and pending is None:
        result.kept[_edition_delta_types.KeptReason.DIFFERS] += 1
        return
    if pending is not None:
        target = _edition_delta_source._as_row(without_lineage_claims(target))
    fields, removed_fields, unsupported = _override_difference(context, candidate, materialised, target)
    if unsupported:
        result.kept[_edition_delta_types.KeptReason.NOT_EXACT] += 1
        result.not_exact.append(
            f"{row_id}: nested removals are not representable by CasillaFieldOverride: " + ", ".join(unsupported)
        )
        return
    _append_changed_override(context, result, row_id, row, candidate, fields, removed_fields, target, pending)


def _append_changed_override(
    context: _SelectionContext,
    result: DropSelection,
    row_id: str,
    row: _edition_delta_source._Row,
    candidate: _edition_delta_source._Placed,
    fields: Mapping[str, object],
    removed_fields: Sequence[str],
    target: _edition_delta_source._Row,
    pending: LineageAttestation | None,
) -> None:
    if pending is not None:
        result.attestations.append(pending)
    override: _edition_delta_source._Row = {
        "selector": {"revision": context.predecessor, "id": _edition_delta_source._row_id(candidate.row)},
        "fields": fields,
        "removed_fields": list(removed_fields),
    }
    if any(claim in target for claim in LINEAGE_CLAIM_FIELDS):
        override["restate_provenance"] = True
    result.overrides.append(override)
    result.drops.add(row_id)


def _append_storage_only_override(
    context: _SelectionContext,
    result: DropSelection,
    row_id: str,
    candidate: _edition_delta_source._Placed,
) -> None:
    target = context.lifts[row_id].row
    raw_baseline = _edition_delta_source._as_row(without_lineage_claims(candidate.row))
    fields, removed_fields = _edition_delta_payload._storage_difference(raw_baseline, target)
    removed_fields = _edition_delta_payload._existing_storage_removals(raw_baseline, removed_fields)
    result.overrides.append(
        {
            "selector": {"revision": context.predecessor, "id": _edition_delta_source._row_id(candidate.row)},
            "fields": fields,
            "removed_fields": list(removed_fields),
            "restate_provenance": True,
        }
    )
    result.drops.add(row_id)


def _append_equal_row_attestation(
    context: _SelectionContext,
    result: DropSelection,
    row_id: str,
    row: _edition_delta_source._Row,
) -> None:
    if not any(claim in row for claim in LINEAGE_CLAIM_FIELDS):
        result.drops.add(row_id)
        return
    attestation = _edition_delta_lineage_attestation._lineage_attestation(
        member=row,
        manifest=context.source.manifest,
        predecessor_revision_id=context.predecessor,
        revision_id=context.revision_id,
    )
    if attestation is None:
        result.kept[_edition_delta_types.KeptReason.DIFFERS] += 1
        return
    result.attestations.append(attestation)
    result.drops.add(row_id)


def _process_row(
    context: _SelectionContext,
    result: DropSelection,
    row: _edition_delta_source._Row,
    by_lineage: Mapping[str, list[_edition_delta_source._Placed]],
    by_storage_id: Mapping[str, list[_edition_delta_source._Placed]],
    claimed: frozenset[str],
) -> None:
    row_id = _edition_delta_source._row_id(row)
    candidate = _candidate_for_row(row, by_lineage, by_storage_id, claimed)
    if candidate is None:
        result.kept[_edition_delta_types.KeptReason.NEW_LINEAGE] += 1
        return
    result.matched_storage_ids.add(_edition_delta_source._row_id(candidate.row))
    baseline = _edition_delta_source._as_row(without_lineage_claims(candidate.row))
    materialised = _edition_delta_source._effective(
        baseline,
        origin=candidate.origin,
        revision_id=context.revision_id,
        defaults=context.defaults,
        declarations=context.source.declarations,
    )
    payload_row = _edition_delta_source._as_row(without_lineage_claims(row))
    if materialised is None:
        result.kept[_edition_delta_types.KeptReason.NOT_EXACT] += 1
        result.not_exact.append(f"{row_id}: inherited references do not resolve in the successor")
        return
    if materialised != payload_row:
        _record_changed_row(context, result, row_id, row, candidate, materialised)
        return
    if context.storage_only and any(claim in context.lifts[row_id].row for claim in LINEAGE_CLAIM_FIELDS):
        _append_storage_only_override(context, result, row_id, candidate)
        return
    _append_equal_row_attestation(context, result, row_id, row)


def select_drops(context: _SelectionContext, full_rows: Sequence[_edition_delta_source._Row]) -> DropSelection:
    """Match each successor row to a unique predecessor row and decide whether it drops, overrides or stays stated."""
    indexes = _edition_delta_row_delta_common.candidate_indexes(context.inherited)
    claimed = _edition_delta_row_delta_common.authored_override_selectors(context.source.manifest)
    result = DropSelection()
    for row in full_rows:
        _process_row(context, result, row, indexes[0], indexes[1], claimed)
    return result


def selection_context(
    revision_id: str,
    predecessor: str,
    inherited: Sequence[_edition_delta_source._Placed],
    lifts: Mapping[str, _edition_delta_source._Lift],
    source: _edition_delta_source._EditionSource,
    defaults: _edition_delta_source._Defaults,
    storage_only: bool,
) -> _SelectionContext:
    """Bundle one edition's predecessor rows, lifts and defaults for :func:`select_drops`."""
    return _SelectionContext(revision_id, predecessor, inherited, lifts, source, defaults, storage_only)
