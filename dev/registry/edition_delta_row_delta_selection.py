"""Select row drops and storage overrides using unique lineage/storage matches."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from cadrumo.domain.calculations.registry.lineage_attestation import LineageAttestation

from . import (
    edition_delta_lineage_attestation,
    edition_delta_payload,
    edition_delta_row_delta_common,
    edition_delta_source,
    edition_delta_types,
)
from .compiler.casilla_identity import LINEAGE_CLAIM_FIELDS
from .compiler.casilla_inheritance import without_lineage_claims


@dataclass(frozen=True)
class _SelectionContext:
    revision_id: str
    predecessor: str
    inherited: Sequence[edition_delta_source.Placed]
    lifts: Mapping[str, edition_delta_source.Lift]
    source: edition_delta_source.EditionSource
    defaults: edition_delta_source.Defaults
    storage_only: bool


@dataclass
class DropSelection:
    """Dropped row ids, kept-row reasons, generated overrides and attestations chosen for one edition."""

    drops: set[str] = field(default_factory=set)
    kept: Counter[edition_delta_types.KeptReason] = field(default_factory=Counter)
    not_exact: list[str] = field(default_factory=list)
    overrides: list[edition_delta_source.Row] = field(default_factory=list)
    attestations: list[LineageAttestation] = field(default_factory=list)
    matched_storage_ids: set[str] = field(default_factory=set)


def _candidate_for_row(
    row: edition_delta_source.Row,
    by_lineage: Mapping[str, list[edition_delta_source.Placed]],
    by_storage_id: Mapping[str, list[edition_delta_source.Placed]],
    claimed: frozenset[str],
) -> edition_delta_source.Placed | None:
    row_id, lineage = edition_delta_source.row_id(row), edition_delta_source.lineage(row)
    lineage_candidates = by_lineage.get(lineage, []) if lineage is not None else []
    storage_candidates = by_storage_id.get(row_id, []) if lineage is None else []
    candidates = lineage_candidates or storage_candidates
    if len(candidates) != 1:
        return None
    candidate = candidates[0]
    candidate_id = edition_delta_source.row_id(candidate.row)
    if candidate_id in claimed and candidate_id != row_id:
        return None
    if not lineage_candidates and lineage is None and edition_delta_source.lineage(candidate.row) is not None:
        return None
    return candidate


def _override_difference(
    context: _SelectionContext,
    candidate: edition_delta_source.Placed,
    materialised: edition_delta_source.Row,
    target: edition_delta_source.Row,
) -> tuple[Mapping[str, object], tuple[str, ...], tuple[str, ...]]:
    baseline = edition_delta_source.edition_delta_source_lift(
        materialised,
        source_default=context.defaults.source_refs,
        orden=context.defaults.orden,
    ).row
    raw_baseline = edition_delta_source.as_row(without_lineage_claims(candidate.row))
    fields, removed_fields = edition_delta_payload.storage_difference(baseline, target)
    removed_fields = edition_delta_payload.existing_storage_removals(raw_baseline, removed_fields)
    removed_fields = edition_delta_row_delta_common.reconcile_source_removals(fields, removed_fields, raw_baseline)
    return fields, removed_fields, edition_delta_row_delta_common.unsupported_nested_removals(removed_fields)


def _record_changed_row(
    context: _SelectionContext,
    result: DropSelection,
    row_id: str,
    row: edition_delta_source.Row,
    candidate: edition_delta_source.Placed,
    materialised: edition_delta_source.Row,
) -> None:
    target = context.lifts[row_id].row
    lineage = edition_delta_source.lineage(row)
    pending = edition_delta_row_delta_common.pending_lineage_attestation(
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
        result.kept[edition_delta_types.KeptReason.DIFFERS] += 1
        return
    if pending is not None:
        target = edition_delta_source.as_row(without_lineage_claims(target))
    fields, removed_fields, unsupported = _override_difference(context, candidate, materialised, target)
    if unsupported:
        result.kept[edition_delta_types.KeptReason.NOT_EXACT] += 1
        result.not_exact.append(
            f"{row_id}: nested removals are not representable by CasillaFieldOverride: " + ", ".join(unsupported)
        )
        return
    _append_changed_override(context, result, row_id, row, candidate, fields, removed_fields, target, pending)


def _append_changed_override(
    context: _SelectionContext,
    result: DropSelection,
    row_id: str,
    row: edition_delta_source.Row,
    candidate: edition_delta_source.Placed,
    fields: Mapping[str, object],
    removed_fields: Sequence[str],
    target: edition_delta_source.Row,
    pending: LineageAttestation | None,
) -> None:
    if pending is not None:
        result.attestations.append(pending)
    override: edition_delta_source.Row = {
        "selector": {"revision": context.predecessor, "id": edition_delta_source.row_id(candidate.row)},
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
    candidate: edition_delta_source.Placed,
) -> None:
    target = context.lifts[row_id].row
    raw_baseline = edition_delta_source.as_row(without_lineage_claims(candidate.row))
    fields, removed_fields = edition_delta_payload.storage_difference(raw_baseline, target)
    removed_fields = edition_delta_payload.existing_storage_removals(raw_baseline, removed_fields)
    result.overrides.append(
        {
            "selector": {"revision": context.predecessor, "id": edition_delta_source.row_id(candidate.row)},
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
    row: edition_delta_source.Row,
) -> None:
    if not any(claim in row for claim in LINEAGE_CLAIM_FIELDS):
        result.drops.add(row_id)
        return
    attestation = edition_delta_lineage_attestation.lineage_attestation(
        member=row,
        manifest=context.source.manifest,
        predecessor_revision_id=context.predecessor,
        revision_id=context.revision_id,
    )
    if attestation is None:
        result.kept[edition_delta_types.KeptReason.DIFFERS] += 1
        return
    result.attestations.append(attestation)
    result.drops.add(row_id)


def _process_row(
    context: _SelectionContext,
    result: DropSelection,
    row: edition_delta_source.Row,
    by_lineage: Mapping[str, list[edition_delta_source.Placed]],
    by_storage_id: Mapping[str, list[edition_delta_source.Placed]],
    claimed: frozenset[str],
) -> None:
    row_id = edition_delta_source.row_id(row)
    candidate = _candidate_for_row(row, by_lineage, by_storage_id, claimed)
    if candidate is None:
        result.kept[edition_delta_types.KeptReason.NEW_LINEAGE] += 1
        return
    result.matched_storage_ids.add(edition_delta_source.row_id(candidate.row))
    baseline = edition_delta_source.as_row(without_lineage_claims(candidate.row))
    payload_row = edition_delta_source.as_row(without_lineage_claims(row))
    materialised = edition_delta_source.edition_delta_source_effective_restating_references(
        baseline,
        payload_row,
        origin=candidate.origin,
        revision_id=context.revision_id,
        defaults=context.defaults,
        declarations=context.source.declarations,
    )
    if materialised is None:
        result.kept[edition_delta_types.KeptReason.NOT_EXACT] += 1
        result.not_exact.append(f"{row_id}: inherited references do not resolve in the successor")
        return
    if materialised != payload_row:
        _record_changed_row(context, result, row_id, row, candidate, materialised)
        return
    if context.storage_only and any(claim in context.lifts[row_id].row for claim in LINEAGE_CLAIM_FIELDS):
        _append_storage_only_override(context, result, row_id, candidate)
        return
    _append_equal_row_attestation(context, result, row_id, row)


def select_drops(context: _SelectionContext, full_rows: Sequence[edition_delta_source.Row]) -> DropSelection:
    """Match each successor row to a unique predecessor row and decide whether it drops, overrides or stays stated."""
    indexes = edition_delta_row_delta_common.candidate_indexes(context.inherited)
    claimed = edition_delta_row_delta_common.authored_override_selectors(context.source.manifest)
    result = DropSelection()
    for row in full_rows:
        _process_row(context, result, row, indexes[0], indexes[1], claimed)
    return result


def selection_context(
    revision_id: str,
    predecessor: str,
    inherited: Sequence[edition_delta_source.Placed],
    lifts: Mapping[str, edition_delta_source.Lift],
    source: edition_delta_source.EditionSource,
    defaults: edition_delta_source.Defaults,
    storage_only: bool,
) -> _SelectionContext:
    """Bundle one edition's predecessor rows, lifts and defaults for :func:`select_drops`."""
    return _SelectionContext(revision_id, predecessor, inherited, lifts, source, defaults, storage_only)
