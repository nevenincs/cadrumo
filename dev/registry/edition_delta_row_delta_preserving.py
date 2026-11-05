"""Preserve effective inherited rows when edition defaults or storage change."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from . import edition_delta_errors, edition_delta_payload, edition_delta_row_delta_common, edition_delta_source
from .compiler.casilla_identity import LINEAGE_CLAIM_FIELDS
from .compiler.casilla_inheritance import without_lineage_claims


def preserve_inherited_rows(
    *,
    revision_id: str,
    predecessor: str,
    inherited: Sequence[edition_delta_source.Placed],
    full_rows: Sequence[edition_delta_source.Row],
    source: edition_delta_source.EditionSource,
    defaults: edition_delta_source.Defaults,
    current_output: Sequence[edition_delta_source.Placed],
) -> tuple[tuple[edition_delta_source.Row, ...], tuple[edition_delta_source.Row, ...]]:
    """Patch inherited rows whose planned raw predecessor would pick up a different edition default."""
    by_lineage, by_storage_id = edition_delta_row_delta_common.candidate_indexes(inherited)
    authored_ids = {edition_delta_source.row_id(row) for row in source.stated_rows()}
    authored_overrides = edition_delta_row_delta_common.manifest_operations(source.manifest, "casilla_overrides")
    claimed = edition_delta_row_delta_common.authored_override_selectors(source.manifest)
    current_by_id = {edition_delta_source.row_id(placed.row): placed for placed in current_output}
    new_overrides: list[edition_delta_source.Row] = []
    replacements: list[edition_delta_source.Row] = []
    context = f"edition {revision_id!r} against predecessor {predecessor!r}"
    inputs = _PreservationInputs(
        revision_id,
        predecessor,
        source,
        defaults,
        by_lineage,
        by_storage_id,
        authored_ids,
        authored_overrides,
        claimed,
        current_by_id,
        context,
    )
    for target in full_rows:
        _preserve_target(inputs, target, new_overrides, replacements)
    return tuple(new_overrides), tuple(replacements)


@dataclass(frozen=True)
class _PreservationInputs:
    revision_id: str
    predecessor: str
    source: edition_delta_source.EditionSource
    defaults: edition_delta_source.Defaults
    by_lineage: Mapping[str, list[edition_delta_source.Placed]]
    by_storage_id: Mapping[str, list[edition_delta_source.Placed]]
    authored_ids: set[str]
    authored_overrides: tuple[edition_delta_source.Row, ...]
    claimed: frozenset[str]
    current_by_id: Mapping[str, edition_delta_source.Placed]
    context: str


def _preserve_target(
    inputs: _PreservationInputs,
    target: edition_delta_source.Row,
    new_overrides: list[edition_delta_source.Row],
    replacements: list[edition_delta_source.Row],
) -> None:
    row_id = edition_delta_source.row_id(target)
    if row_id in inputs.authored_ids:
        return
    candidate = edition_delta_row_delta_common.candidate_for_authored(
        target, inputs.by_lineage, inputs.by_storage_id, frozenset()
    )
    if candidate is None:
        return
    selector_id = edition_delta_source.row_id(candidate.row)
    raw_baseline = edition_delta_source.as_row(without_lineage_claims(candidate.row))
    current = inputs.current_by_id.get(row_id)
    if current is None:
        current = inputs.current_by_id.get(selector_id)
    if current is None:
        _refuse_missing_current(inputs, selector_id, row_id)
        return
    effective = edition_delta_source.edition_delta_source_effective(
        current.row,
        origin=current.origin,
        revision_id=inputs.revision_id,
        defaults=inputs.defaults,
        declarations=inputs.source.declarations,
    )
    if effective is None:
        raise edition_delta_errors.MigrationRefusedError(
            f"{inputs.context}: inherited casilla {row_id!r} references do not resolve in the planned successor"
        )
    target_payload = edition_delta_source.as_row(without_lineage_claims(target))
    if effective in (target, target_payload):
        return
    selector = {"revision": inputs.predecessor, "id": selector_id}
    existing = _matching_overrides(inputs.authored_overrides, selector)
    if existing:
        _preserve_existing_override(inputs, candidate, target, target_payload, selector_id, existing, replacements)
        return
    if selector_id in inputs.claimed:
        raise edition_delta_errors.MigrationRefusedError(
            f"{inputs.context}: an authored removal claims predecessor casilla {selector_id!r} "
            "that the target edition retains"
        )
    override = _preserving_override(
        revision_id=inputs.revision_id,
        predecessor=inputs.predecessor,
        candidate=candidate,
        effective_baseline=effective,
        raw_baseline=raw_baseline,
        target=target_payload,
        defaults=inputs.defaults,
    )
    if override is not None:
        new_overrides.append(override)


def _matching_overrides(
    operations: tuple[edition_delta_source.Row, ...], selector: dict[str, str]
) -> list[edition_delta_source.Row]:
    return [operation for operation in operations if operation.get("selector") == selector]


def _preserve_existing_override(
    inputs: _PreservationInputs,
    candidate: edition_delta_source.Placed,
    target: edition_delta_source.Row,
    target_payload: edition_delta_source.Row,
    selector_id: str,
    existing: list[edition_delta_source.Row],
    replacements: list[edition_delta_source.Row],
) -> None:
    if len(existing) != 1:
        raise edition_delta_errors.MigrationRefusedError(
            f"{inputs.context}: multiple authored overrides claim predecessor casilla {selector_id!r}"
        )
    replacements.append(
        _compose_preserving_override(
            revision_id=inputs.revision_id,
            candidate=candidate,
            target=target_payload,
            validated_target=target,
            defaults=inputs.defaults,
            existing=existing[0],
        )
    )


def _refuse_missing_current(inputs: _PreservationInputs, selector_id: str, row_id: str) -> None:
    if selector_id in inputs.claimed:
        raise edition_delta_errors.MigrationRefusedError(
            f"{inputs.context}: authored operation removes or relocates inherited casilla {row_id!r} "
            "that the target edition retains"
        )


def normalize_authored_override_removals(
    *,
    revision_id: str,
    predecessor: str,
    inherited: Sequence[edition_delta_source.Placed],
    full_rows: Sequence[edition_delta_source.Row],
    source: edition_delta_source.EditionSource,
    defaults: edition_delta_source.Defaults,
) -> tuple[edition_delta_source.Row, ...]:
    """Recompose retained overrides whose removals no longer address planned predecessor storage."""
    by_storage_id = edition_delta_row_delta_common.candidate_indexes(inherited)[1]
    targets = {edition_delta_source.row_id(row): row for row in full_rows}
    authored_ids = {edition_delta_source.row_id(row) for row in source.stated_rows()}
    replacements: list[edition_delta_source.Row] = []
    for operation in edition_delta_row_delta_common.manifest_operations(source.manifest, "casilla_overrides"):
        target = _override_target(operation, predecessor, authored_ids, targets)
        if target is None:
            continue
        selector_id, target_id, fields = target
        candidates = by_storage_id.get(selector_id, ())
        if len(candidates) != 1:
            continue
        baseline = edition_delta_source.as_row(without_lineage_claims(candidates[0].row))
        removed = operation.get("removed_fields", ())
        if not isinstance(removed, list | tuple):
            continue
        removed = cast("list[object] | tuple[object, ...]", removed)
        valid_removals = edition_delta_payload.existing_storage_removals(baseline, tuple(str(path) for path in removed))
        normalized = edition_delta_row_delta_common.reconcile_source_removals(fields, valid_removals, baseline)
        if tuple(removed) == normalized:
            continue
        replacements.append(
            _compose_preserving_override(
                revision_id=revision_id,
                candidate=candidates[0],
                target=edition_delta_source.as_row(without_lineage_claims(targets[target_id])),
                validated_target=targets[target_id],
                defaults=defaults,
                existing=operation,
            )
        )
    return tuple(replacements)


def _override_target(
    operation: edition_delta_source.Row,
    predecessor: str,
    authored_ids: set[str],
    targets: Mapping[str, edition_delta_source.Row],
) -> tuple[str, str, Mapping[str, object]] | None:
    selector = operation.get("selector")
    if not isinstance(selector, Mapping):
        return None
    selector = cast("Mapping[str, object]", selector)
    if str(selector.get("revision")) != predecessor:
        return None
    selector_id = str(selector.get("id"))
    fields = operation.get("fields", {})
    if not isinstance(fields, Mapping):
        return None
    fields = cast("Mapping[str, object]", fields)
    target_id = str(fields.get("id", selector_id))
    if target_id in authored_ids or target_id not in targets:
        return None
    return selector_id, target_id, fields


def _compose_preserving_override(
    *,
    revision_id: str,
    candidate: edition_delta_source.Placed,
    target: edition_delta_source.Row,
    validated_target: edition_delta_source.Row,
    defaults: edition_delta_source.Defaults,
    existing: edition_delta_source.Row,
) -> edition_delta_source.Row:
    """Amend a claimed selector to produce the exact target storage row."""
    raw_baseline = edition_delta_source.as_row(without_lineage_claims(candidate.row))
    target_storage = edition_delta_source.edition_delta_source_lift(
        target, source_default=defaults.source_refs, orden=defaults.orden
    ).row
    fields, removed_fields = edition_delta_payload.storage_difference(raw_baseline, target_storage)
    removed_fields = edition_delta_payload.existing_storage_removals(raw_baseline, removed_fields)
    removed_fields = edition_delta_row_delta_common.reconcile_source_removals(
        fields, tuple(removed_fields), raw_baseline
    )
    unsupported = edition_delta_row_delta_common.unsupported_nested_removals(removed_fields)
    if unsupported:
        raise edition_delta_errors.MigrationRefusedError(
            f"edition {revision_id!r}: inherited row {edition_delta_source.row_id(candidate.row)!r} "
            "needs unrepresentable nested removals: " + ", ".join(unsupported)
        )
    existing_fields = existing.get("fields", {})
    if not isinstance(existing_fields, Mapping):
        raise edition_delta_errors.MigrationRefusedError(
            f"edition {revision_id!r}: authored override for "
            f"{edition_delta_source.row_id(candidate.row)!r} has invalid fields"
        )
    existing_fields = cast("Mapping[str, object]", existing_fields)
    for claim_field in sorted(LINEAGE_CLAIM_FIELDS):
        if claim_field not in existing_fields:
            continue
        claim_value = existing_fields[claim_field]
        if validated_target.get(claim_field) != claim_value:
            raise edition_delta_errors.MigrationRefusedError(
                f"edition {revision_id!r}: authored override for "
                f"{edition_delta_source.row_id(candidate.row)!r} has a {claim_field!r} claim "
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
    candidate: edition_delta_source.Placed,
    effective_baseline: edition_delta_source.Row,
    raw_baseline: edition_delta_source.Row,
    target: edition_delta_source.Row,
    defaults: edition_delta_source.Defaults,
) -> edition_delta_source.Row | None:
    comparison = edition_delta_source.edition_delta_source_lift(
        effective_baseline, source_default=defaults.source_refs, orden=defaults.orden
    ).row
    target_storage = edition_delta_source.edition_delta_source_lift(
        target, source_default=defaults.source_refs, orden=defaults.orden
    ).row
    fields, removed_fields = edition_delta_payload.storage_difference(comparison, target_storage)
    removed_fields = edition_delta_payload.existing_storage_removals(raw_baseline, removed_fields)
    removed_fields = edition_delta_row_delta_common.reconcile_source_removals(
        fields, tuple(removed_fields), raw_baseline
    )
    unsupported = edition_delta_row_delta_common.unsupported_nested_removals(removed_fields)
    if unsupported:
        raise edition_delta_errors.MigrationRefusedError(
            f"edition {revision_id!r}: inherited row {edition_delta_source.row_id(candidate.row)!r} "
            "needs unrepresentable nested removals: " + ", ".join(unsupported)
        )
    if not fields and not removed_fields:
        raise edition_delta_errors.MigrationRefusedError(
            f"edition {revision_id!r}: inherited row {edition_delta_source.row_id(candidate.row)!r} "
            "differs after defaults but has no representable preserving patch"
        )
    return {
        "selector": {"revision": predecessor, "id": edition_delta_source.row_id(candidate.row)},
        "fields": fields,
        "removed_fields": list(removed_fields),
    }
