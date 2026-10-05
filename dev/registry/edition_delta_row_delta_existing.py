"""Choose removals and overrides already represented in authored delta storage."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from cadrumo.domain.calculations.registry.lineage_attestation import LineageAttestation

from . import edition_delta_payload as _edition_delta_payload
from . import edition_delta_row_delta_common as _edition_delta_row_delta_common
from . import edition_delta_source as _edition_delta_source
from . import edition_delta_types as _edition_delta_types
from .compiler.casilla_identity import LINEAGE_CLAIM_FIELDS
from .compiler.casilla_inheritance import without_lineage_claims


@dataclass(frozen=True)
class _ExistingContext:
    revision_id: str
    predecessor: str
    inherited: Sequence[_edition_delta_source._Placed]
    full_rows: Sequence[_edition_delta_source._Row]
    lifts: Mapping[str, _edition_delta_source._Lift]
    source: _edition_delta_source._EditionSource
    defaults: _edition_delta_source._Defaults
    storage_only: bool
    storage_rows: Mapping[str, _edition_delta_source._Row]


@dataclass
class _ExistingResult:
    drops: set[str] = field(default_factory=set)
    kept: Counter[_edition_delta_types.KeptReason] = field(default_factory=Counter)
    not_exact: list[str] = field(default_factory=list)
    overrides: list[_edition_delta_source._Row] = field(default_factory=list)
    attestations: list[LineageAttestation] = field(default_factory=list)


def _candidate_for_authored(
    authored: _edition_delta_source._Row,
    by_lineage: Mapping[str, list[_edition_delta_source._Placed]],
    by_storage_id: Mapping[str, list[_edition_delta_source._Placed]],
    claimed: frozenset[str],
) -> _edition_delta_source._Placed | None:
    row_id = _edition_delta_source._row_id(authored)
    lineage = _edition_delta_source._lineage(authored)
    lineage_candidates = by_lineage.get(lineage, []) if lineage is not None else []
    storage_candidates = by_storage_id.get(row_id, []) if lineage is None else []
    candidates = lineage_candidates or storage_candidates
    if len(candidates) != 1:
        return None
    candidate = candidates[0]
    if _edition_delta_source._row_id(candidate.row) in claimed:
        return None
    if not lineage_candidates and lineage is None and _edition_delta_source._lineage(candidate.row) is not None:
        return None
    return candidate


def _record_override(
    context: _ExistingContext,
    result: _ExistingResult,
    row_id: str,
    candidate: _edition_delta_source._Placed,
    effective_baseline: _edition_delta_source._Row,
    raw_baseline: _edition_delta_source._Row,
    target: _edition_delta_source._Row,
    pending_attestation: LineageAttestation | None,
) -> None:
    comparison = _edition_delta_source._lift(
        effective_baseline,
        source_default=context.defaults.source_refs,
        orden=context.defaults.orden,
    ).row
    fields, removed_fields = _edition_delta_payload._storage_difference(comparison, target)
    removed_fields = _edition_delta_payload._existing_storage_removals(raw_baseline, removed_fields)
    storage_baseline = context.storage_rows.get(_edition_delta_source._row_id(candidate.row), raw_baseline)
    removed_fields = _edition_delta_row_delta_common.reconcile_source_removals(fields, removed_fields, storage_baseline)
    unsupported = _edition_delta_row_delta_common.unsupported_nested_removals(removed_fields)
    if unsupported:
        result.kept[_edition_delta_types.KeptReason.NOT_EXACT] += 1
        result.not_exact.append(
            f"{row_id}: nested removals are not representable by CasillaFieldOverride: " + ", ".join(unsupported)
        )
        return
    if pending_attestation is not None:
        result.attestations.append(pending_attestation)
    override: _edition_delta_source._Row = {
        "selector": {"revision": context.predecessor, "id": _edition_delta_source._row_id(candidate.row)},
        "fields": fields,
        "removed_fields": list(removed_fields),
    }
    if context.storage_only and any(claim in target for claim in LINEAGE_CLAIM_FIELDS):
        override["restate_provenance"] = True
    result.overrides.append(override)
    result.drops.add(row_id)


def _process_authored_row(
    context: _ExistingContext,
    result: _ExistingResult,
    authored: _edition_delta_source._Row,
    effective_by_id: Mapping[str, _edition_delta_source._Row],
    by_lineage: Mapping[str, list[_edition_delta_source._Placed]],
    by_storage_id: Mapping[str, list[_edition_delta_source._Placed]],
    claimed: frozenset[str],
) -> None:
    row_id = _edition_delta_source._row_id(authored)
    row = effective_by_id[row_id]
    candidate = _candidate_for_authored(row, by_lineage, by_storage_id, claimed)
    if candidate is None:
        result.kept[_edition_delta_types.KeptReason.NEW_LINEAGE] += 1
        return
    baseline = _edition_delta_source._as_row(without_lineage_claims(candidate.row))
    effective = _edition_delta_source._effective(
        baseline,
        origin=candidate.origin,
        revision_id=context.revision_id,
        defaults=context.defaults,
        declarations=context.source.declarations,
    )
    effective = _available_baseline(result, row_id, effective)
    if effective is None:
        return
    target, pending = _authored_target(context, result, row_id, row)
    if target is None:
        return
    payload_row = _edition_delta_source._as_row(without_lineage_claims(row))
    if effective == payload_row and not _storage_only_lineage_requires_override(context, row_id):
        if pending is not None:
            result.attestations.append(pending)
        result.drops.add(row_id)
        return
    _record_override(context, result, row_id, candidate, effective, baseline, target, pending)


def _available_baseline(
    result: _ExistingResult, row_id: str, effective: _edition_delta_source._Row | None
) -> _edition_delta_source._Row | None:
    if effective is None:
        result.kept[_edition_delta_types.KeptReason.NOT_EXACT] += 1
        result.not_exact.append(f"{row_id}: inherited references do not resolve in the successor")
        return None
    return effective


def _authored_target(
    context: _ExistingContext,
    result: _ExistingResult,
    row_id: str,
    row: _edition_delta_source._Row,
) -> tuple[_edition_delta_source._Row | None, LineageAttestation | None]:
    target = context.lifts[row_id].row
    lineage = _edition_delta_source._lineage(row)
    has_lineage_claim = any(claim in target for claim in LINEAGE_CLAIM_FIELDS)
    pending = _edition_delta_row_delta_common.pending_lineage_attestation(
        row=row,
        lineage=lineage,
        target=target,
        manifest=context.source.manifest,
        predecessor=context.predecessor,
        revision_id=context.revision_id,
        storage_only=context.storage_only,
    )
    if pending is None and not context.storage_only and lineage is not None and has_lineage_claim:
        result.kept[_edition_delta_types.KeptReason.DIFFERS] += 1
        return None, None
    if pending is not None:
        target = _edition_delta_source._as_row(without_lineage_claims(target))
    return target, pending


def _storage_only_lineage_requires_override(context: _ExistingContext, row_id: str) -> bool:
    return context.storage_only and any(claim in context.lifts[row_id].row for claim in LINEAGE_CLAIM_FIELDS)


def choose_existing_drops(
    *,
    revision_id: str,
    predecessor: str,
    storage_rows: Mapping[str, _edition_delta_source._Row],
    inherited: Sequence[_edition_delta_source._Placed],
    full_rows: Sequence[_edition_delta_source._Row],
    lifts: Mapping[str, _edition_delta_source._Lift],
    source: _edition_delta_source._EditionSource,
    defaults: _edition_delta_source._Defaults,
    storage_only: bool,
) -> tuple[
    set[str],
    Counter[_edition_delta_types.KeptReason],
    list[str],
    tuple[_edition_delta_source._Row, ...],
    tuple[LineageAttestation, ...],
]:
    """Finish stated rows without replaying existing storage operations."""
    context = _ExistingContext(
        revision_id, predecessor, inherited, full_rows, lifts, source, defaults, storage_only, storage_rows
    )
    by_lineage, by_storage_id = _edition_delta_row_delta_common.candidate_indexes(inherited)
    effective_by_id = {_edition_delta_source._row_id(row): row for row in full_rows}
    claimed = _edition_delta_row_delta_common.authored_override_selectors(source.manifest)
    result = _ExistingResult()
    for authored in source.stated_rows():
        _process_authored_row(context, result, authored, effective_by_id, by_lineage, by_storage_id, claimed)
    return result.drops, result.kept, result.not_exact, tuple(result.overrides), tuple(result.attestations)
