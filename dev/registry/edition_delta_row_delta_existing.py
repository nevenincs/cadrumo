"""Choose removals and overrides already represented in authored delta storage."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from cadrumo.domain.calculations.registry.lineage_attestation import LineageAttestation

from . import edition_delta_errors as _edition_delta_errors
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


def preserve_inherited_rows(
    *,
    revision_id: str,
    predecessor: str,
    inherited: Sequence[_edition_delta_source._Placed],
    full_rows: Sequence[_edition_delta_source._Row],
    source: _edition_delta_source._EditionSource,
    defaults: _edition_delta_source._Defaults,
    current_output: Sequence[_edition_delta_source._Placed],
) -> tuple[tuple[_edition_delta_source._Row, ...], tuple[_edition_delta_source._Row, ...]]:
    """Patch inherited rows whose planned raw predecessor would pick up a different edition default."""
    by_lineage, by_storage_id = _edition_delta_row_delta_common.candidate_indexes(inherited)
    authored_ids = {_edition_delta_source._row_id(row) for row in source.stated_rows()}
    authored_overrides = _edition_delta_row_delta_common.manifest_operations(source.manifest, "casilla_overrides")
    claimed = _edition_delta_row_delta_common.authored_override_selectors(source.manifest)
    current_by_id = {_edition_delta_source._row_id(placed.row): placed for placed in current_output}
    new_overrides: list[_edition_delta_source._Row] = []
    replacements: list[_edition_delta_source._Row] = []
    context = f"edition {revision_id!r} against predecessor {predecessor!r}"
    for target in full_rows:
        row_id = _edition_delta_source._row_id(target)
        if row_id in authored_ids:
            continue
        candidate = _candidate_for_authored(target, by_lineage, by_storage_id, frozenset())
        if candidate is None:
            continue
        selector_id = _edition_delta_source._row_id(candidate.row)
        raw_baseline = _edition_delta_source._as_row(without_lineage_claims(candidate.row))
        current = current_by_id.get(row_id)
        if current is None:
            current = current_by_id.get(selector_id)
        if current is None:
            if selector_id in claimed:
                raise _edition_delta_errors.MigrationRefusedError(
                    f"{context}: authored operation removes or relocates inherited casilla {row_id!r} "
                    "that the target edition retains"
                )
            continue
        effective = _edition_delta_source._effective(
            current.row,
            origin=current.origin,
            revision_id=revision_id,
            defaults=defaults,
            declarations=source.declarations,
        )
        if effective is None:
            raise _edition_delta_errors.MigrationRefusedError(
                f"{context}: inherited casilla {row_id!r} references do not resolve in the planned successor"
            )
        target_payload = _edition_delta_source._as_row(without_lineage_claims(target))
        if effective == target_payload:
            continue
        selector = {"revision": predecessor, "id": selector_id}
        existing = [operation for operation in authored_overrides if operation.get("selector") == selector]
        if existing:
            if len(existing) != 1:
                raise _edition_delta_errors.MigrationRefusedError(
                    f"{context}: multiple authored overrides claim predecessor casilla {selector_id!r}"
                )
            replacements.append(
                _compose_preserving_override(
                    revision_id=revision_id,
                    candidate=candidate,
                    target=target_payload,
                    validated_target=target,
                    defaults=defaults,
                    existing=existing[0],
                )
            )
            continue
        if selector_id in claimed:
            raise _edition_delta_errors.MigrationRefusedError(
                f"{context}: an authored removal claims predecessor casilla {selector_id!r} "
                "that the target edition retains"
            )
        override = _preserving_override(
            revision_id=revision_id,
            predecessor=predecessor,
            candidate=candidate,
            effective_baseline=effective,
            raw_baseline=raw_baseline,
            target=target_payload,
            defaults=defaults,
        )
        if override is not None:
            new_overrides.append(override)
    return tuple(new_overrides), tuple(replacements)


def normalize_authored_override_removals(
    *,
    revision_id: str,
    predecessor: str,
    inherited: Sequence[_edition_delta_source._Placed],
    full_rows: Sequence[_edition_delta_source._Row],
    source: _edition_delta_source._EditionSource,
    defaults: _edition_delta_source._Defaults,
) -> tuple[_edition_delta_source._Row, ...]:
    """Recompose retained overrides whose removals no longer address planned predecessor storage."""
    by_storage_id = _edition_delta_row_delta_common.candidate_indexes(inherited)[1]
    targets = {_edition_delta_source._row_id(row): row for row in full_rows}
    authored_ids = {_edition_delta_source._row_id(row) for row in source.stated_rows()}
    replacements: list[_edition_delta_source._Row] = []
    for operation in _edition_delta_row_delta_common.manifest_operations(source.manifest, "casilla_overrides"):
        selector = operation.get("selector")
        if not isinstance(selector, Mapping) or str(selector.get("revision")) != predecessor:
            continue
        selector_id = str(selector.get("id"))
        fields = operation.get("fields", {})
        if not isinstance(fields, Mapping):
            continue
        target_id = str(fields.get("id", selector_id))
        if target_id in authored_ids or target_id not in targets:
            continue
        candidates = by_storage_id.get(selector_id, ())
        if len(candidates) != 1:
            continue
        baseline = _edition_delta_source._as_row(without_lineage_claims(candidates[0].row))
        removed = operation.get("removed_fields", ())
        if not isinstance(removed, list | tuple):
            continue
        valid_removals = _edition_delta_payload._existing_storage_removals(
            baseline, tuple(str(path) for path in removed)
        )
        normalized = _edition_delta_row_delta_common.reconcile_source_removals(fields, valid_removals, baseline)
        if tuple(removed) == normalized:
            continue
        replacements.append(
            _compose_preserving_override(
                revision_id=revision_id,
                candidate=candidates[0],
                target=_edition_delta_source._as_row(without_lineage_claims(targets[target_id])),
                validated_target=targets[target_id],
                defaults=defaults,
                existing=operation,
            )
        )
    return tuple(replacements)


def _compose_preserving_override(
    *,
    revision_id: str,
    candidate: _edition_delta_source._Placed,
    target: _edition_delta_source._Row,
    validated_target: _edition_delta_source._Row,
    defaults: _edition_delta_source._Defaults,
    existing: _edition_delta_source._Row,
) -> _edition_delta_source._Row:
    """Amend a claimed selector to produce the exact target storage row."""
    raw_baseline = _edition_delta_source._as_row(without_lineage_claims(candidate.row))
    target_storage = _edition_delta_source._lift(target, source_default=defaults.source_refs, orden=defaults.orden).row
    fields, removed_fields = _edition_delta_payload._storage_difference(raw_baseline, target_storage)
    removed_fields = _edition_delta_payload._existing_storage_removals(raw_baseline, removed_fields)
    removed_fields = _edition_delta_row_delta_common.reconcile_source_removals(
        fields, tuple(removed_fields), raw_baseline
    )
    unsupported = _edition_delta_row_delta_common.unsupported_nested_removals(removed_fields)
    if unsupported:
        raise _edition_delta_errors.MigrationRefusedError(
            f"edition {revision_id!r}: inherited row {_edition_delta_source._row_id(candidate.row)!r} "
            "needs unrepresentable nested removals: " + ", ".join(unsupported)
        )
    existing_fields = existing.get("fields", {})
    if not isinstance(existing_fields, Mapping):
        raise _edition_delta_errors.MigrationRefusedError(
            f"edition {revision_id!r}: authored override for "
            f"{_edition_delta_source._row_id(candidate.row)!r} has invalid fields"
        )
    for claim_field in sorted(LINEAGE_CLAIM_FIELDS):
        if claim_field not in existing_fields:
            continue
        claim_value = existing_fields[claim_field]
        if validated_target.get(claim_field) != claim_value:
            raise _edition_delta_errors.MigrationRefusedError(
                f"edition {revision_id!r}: authored override for "
                f"{_edition_delta_source._row_id(candidate.row)!r} has a {claim_field!r} claim "
                "that differs from its validated effective target"
            )
        fields[claim_field] = claim_value
    replacement = dict(existing)
    replacement["fields"] = fields
    replacement["removed_fields"] = list(removed_fields)
    return replacement


def _preserving_override(
    *,
    revision_id: str,
    predecessor: str,
    candidate: _edition_delta_source._Placed,
    effective_baseline: _edition_delta_source._Row,
    raw_baseline: _edition_delta_source._Row,
    target: _edition_delta_source._Row,
    defaults: _edition_delta_source._Defaults,
) -> _edition_delta_source._Row | None:
    comparison = _edition_delta_source._lift(
        effective_baseline, source_default=defaults.source_refs, orden=defaults.orden
    ).row
    target_storage = _edition_delta_source._lift(target, source_default=defaults.source_refs, orden=defaults.orden).row
    fields, removed_fields = _edition_delta_payload._storage_difference(comparison, target_storage)
    removed_fields = _edition_delta_payload._existing_storage_removals(raw_baseline, removed_fields)
    removed_fields = _edition_delta_row_delta_common.reconcile_source_removals(
        fields, tuple(removed_fields), raw_baseline
    )
    unsupported = _edition_delta_row_delta_common.unsupported_nested_removals(removed_fields)
    if unsupported:
        raise _edition_delta_errors.MigrationRefusedError(
            f"edition {revision_id!r}: inherited row {_edition_delta_source._row_id(candidate.row)!r} "
            "needs unrepresentable nested removals: " + ", ".join(unsupported)
        )
    if not fields and not removed_fields:
        raise _edition_delta_errors.MigrationRefusedError(
            f"edition {revision_id!r}: inherited row {_edition_delta_source._row_id(candidate.row)!r} "
            "differs after defaults but has no representable preserving patch"
        )
    return {
        "selector": {"revision": predecessor, "id": _edition_delta_source._row_id(candidate.row)},
        "fields": fields,
        "removed_fields": list(removed_fields),
    }
