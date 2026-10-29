"""Preserve effective inherited rows when edition defaults or storage change."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

from . import edition_delta_errors as _edition_delta_errors
from . import edition_delta_payload as _edition_delta_payload
from . import edition_delta_row_delta_common as _edition_delta_row_delta_common
from . import edition_delta_source as _edition_delta_source
from .compiler.casilla_identity import LINEAGE_CLAIM_FIELDS
from .compiler.casilla_inheritance import without_lineage_claims


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
    source: _edition_delta_source._EditionSource
    defaults: _edition_delta_source._Defaults
    by_lineage: Mapping[str, list[_edition_delta_source._Placed]]
    by_storage_id: Mapping[str, list[_edition_delta_source._Placed]]
    authored_ids: set[str]
    authored_overrides: tuple[_edition_delta_source._Row, ...]
    claimed: frozenset[str]
    current_by_id: Mapping[str, _edition_delta_source._Placed]
    context: str


def _preserve_target(
    inputs: _PreservationInputs,
    target: _edition_delta_source._Row,
    new_overrides: list[_edition_delta_source._Row],
    replacements: list[_edition_delta_source._Row],
) -> None:
    row_id = _edition_delta_source._row_id(target)
    if row_id in inputs.authored_ids:
        return
    candidate = _edition_delta_row_delta_common.candidate_for_authored(
        target, inputs.by_lineage, inputs.by_storage_id, frozenset()
    )
    if candidate is None:
        return
    selector_id = _edition_delta_source._row_id(candidate.row)
    raw_baseline = _edition_delta_source._as_row(without_lineage_claims(candidate.row))
    current = inputs.current_by_id.get(row_id)
    if current is None:
        current = inputs.current_by_id.get(selector_id)
    if current is None:
        _refuse_missing_current(inputs, selector_id, row_id)
        return
    effective = _edition_delta_source._effective(
        current.row,
        origin=current.origin,
        revision_id=inputs.revision_id,
        defaults=inputs.defaults,
        declarations=inputs.source.declarations,
    )
    if effective is None:
        raise _edition_delta_errors.MigrationRefusedError(
            f"{inputs.context}: inherited casilla {row_id!r} references do not resolve in the planned successor"
        )
    target_payload = _edition_delta_source._as_row(without_lineage_claims(target))
    if effective in (target, target_payload):
        return
    selector = {"revision": inputs.predecessor, "id": selector_id}
    existing = _matching_overrides(inputs.authored_overrides, selector)
    if existing:
        _preserve_existing_override(inputs, candidate, target, target_payload, selector_id, existing, replacements)
        return
    if selector_id in inputs.claimed:
        raise _edition_delta_errors.MigrationRefusedError(
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
    operations: tuple[_edition_delta_source._Row, ...], selector: dict[str, str]
) -> list[_edition_delta_source._Row]:
    return [operation for operation in operations if operation.get("selector") == selector]


def _preserve_existing_override(
    inputs: _PreservationInputs,
    candidate: _edition_delta_source._Placed,
    target: _edition_delta_source._Row,
    target_payload: _edition_delta_source._Row,
    selector_id: str,
    existing: list[_edition_delta_source._Row],
    replacements: list[_edition_delta_source._Row],
) -> None:
    if len(existing) != 1:
        raise _edition_delta_errors.MigrationRefusedError(
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
        raise _edition_delta_errors.MigrationRefusedError(
            f"{inputs.context}: authored operation removes or relocates inherited casilla {row_id!r} "
            "that the target edition retains"
        )


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
        target = _override_target(operation, predecessor, authored_ids, targets)
        if target is None:
            continue
        selector_id, target_id, fields = target
        candidates = by_storage_id.get(selector_id, ())
        if len(candidates) != 1:
            continue
        baseline = _edition_delta_source._as_row(without_lineage_claims(candidates[0].row))
        removed = operation.get("removed_fields", ())
        if not isinstance(removed, list | tuple):
            continue
        removed = cast("list[object] | tuple[object, ...]", removed)
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


def _override_target(
    operation: _edition_delta_source._Row,
    predecessor: str,
    authored_ids: set[str],
    targets: Mapping[str, _edition_delta_source._Row],
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
    existing_fields = cast("Mapping[str, object]", existing_fields)
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
