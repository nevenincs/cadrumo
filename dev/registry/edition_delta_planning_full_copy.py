"""Plan full-copy editions against a proved predecessor baseline."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field

from cadrumo.domain.calculations.registry.lineage_attestation import LineageAttestation
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from . import (
    edition_delta_errors,
    edition_delta_planning_counts,
    edition_delta_planning_predecessor,
    edition_delta_planning_state,
    edition_delta_row_delta,
    edition_delta_row_delta_common,
    edition_delta_row_delta_reconstruction,
    edition_delta_source,
    edition_delta_types,
)


@dataclass
class _FullCopyResult:
    predecessor: str | None
    basis: edition_delta_types.PredecessorBasis
    causes: list[edition_delta_types.BlockedCause]
    drops: set[str] = field(default_factory=set)
    kept: Counter[edition_delta_types.KeptReason] = field(default_factory=Counter)
    not_exact: list[str] = field(default_factory=list)
    overrides: tuple[edition_delta_source.Row, ...] = ()
    removals: tuple[edition_delta_source.Row, ...] = ()
    positions: tuple[edition_delta_source.Row, ...] = ()
    attestations: tuple[LineageAttestation, ...] = ()
    reconstructed_order: tuple[str, ...] = ()
    normalised: bool = False
    failure_details: tuple[str, ...] = ()


def _select_full_copy_delta(
    run: edition_delta_planning_state.PlanningRun,
    revision_id: str,
    predecessor: str | None,
    basis: edition_delta_types.PredecessorBasis,
    causes: list[edition_delta_types.BlockedCause],
    full_rows: list[edition_delta_source.Row],
    lifts: Mapping[str, edition_delta_source.Lift],
    source: edition_delta_source.EditionSource,
    defaults: edition_delta_source.Defaults,
) -> _FullCopyResult:
    result = _FullCopyResult(
        predecessor=predecessor,
        basis=basis,
        causes=causes,
        reconstructed_order=tuple(edition_delta_source.row_id(row) for row in full_rows),
    )
    if predecessor is None or causes:
        return result
    try:
        (
            result.causes,
            result.drops,
            result.kept,
            result.not_exact,
            result.overrides,
            result.removals,
            result.positions,
            result.attestations,
            result.reconstructed_order,
            result.normalised,
        ) = edition_delta_row_delta.choose_drops(
            definition=run.definition,
            revision_id=revision_id,
            predecessor=predecessor,
            inherited=run.materialised[predecessor],
            full_rows=full_rows,
            lifts=lifts,
            source=source,
            defaults=defaults,
            # Keep canonical baseline merge placement; preserve local order by positions.
            normalise_order=predecessor in run.order_normalised,
            storage_only=basis is edition_delta_types.PredecessorBasis.STORAGE,
        )
    except edition_delta_errors.MigrationRefusedError as exc:
        result.causes = [edition_delta_types.BlockedCause.TRANSFORMATION_FAILED]
        result.failure_details = (f"requires readable authored source {predecessor!r}; transformation failed: {exc}",)
    return result


def _block_copy(result: _FullCopyResult, full_rows: list[edition_delta_source.Row]) -> None:
    result.basis = edition_delta_types.PredecessorBasis.BLOCKED
    result.drops = set()
    result.kept = Counter()
    result.not_exact = []
    result.overrides = ()
    result.removals = ()
    result.positions = ()
    result.attestations = ()
    result.reconstructed_order = tuple(edition_delta_source.row_id(row) for row in full_rows)
    result.normalised = False


def _seed_materialised(
    run: edition_delta_planning_state.PlanningRun,
    revision_id: str,
    source: edition_delta_source.EditionSource,
    lift: edition_delta_source.EditionLift,
    result: _FullCopyResult,
) -> None:
    """Seed descendants from the storage rows this plan will actually write and merge."""
    plan = result
    if plan.basis is edition_delta_types.PredecessorBasis.BLOCKED:
        placed = [
            edition_delta_source.Placed(row, origin or revision_id)
            for row, origin in zip(source.rows, source.origins, strict=True)
        ]
    elif plan.predecessor is None:
        placed = [
            edition_delta_source.Placed(lift.lifts[edition_delta_source.row_id(row)].row, revision_id)
            for row in lift.rows
        ]
    else:
        stated = frozenset(edition_delta_source.row_id(row) for row in lift.rows) - plan.drops
        layout = edition_delta_source.stated_layout(source, stated)
        stated_rows = _lifted_stated_rows(layout, lift)
        inherited = run.materialised[plan.predecessor]
        overrides = (
            *edition_delta_row_delta_common.manifest_operations(source.manifest, "casilla_overrides"),
            *plan.overrides,
        )
        removals = (
            *edition_delta_row_delta_common.manifest_operations(source.manifest, "casilla_removals"),
            *plan.removals,
        )
        positions = (
            *edition_delta_row_delta_common.manifest_operations(source.manifest, "casilla_positions"),
            *plan.positions,
        )
        placed = edition_delta_row_delta_reconstruction.simulate_storage_output(
            revision_id=revision_id,
            predecessor=plan.predecessor,
            inherited=inherited,
            source=source,
            stated_rows=stated_rows,
            overrides=overrides,
            removals=removals,
            positions=positions,
        )
        by_id = {edition_delta_source.row_id(item.row): item for item in placed}
        placed = [by_id[row_id] for row_id in plan.reconstructed_order]
    run.materialised[revision_id] = placed


def _lifted_stated_rows(
    layout: list[tuple[str, list[edition_delta_source.Block]]], lift: edition_delta_source.EditionLift
) -> list[edition_delta_source.Row]:
    return [lift.lifts[edition_delta_source.row_id(block.row)].row for _, blocks in layout for block in blocks]


def _overridden_ids(overrides: tuple[edition_delta_source.Row, ...]) -> set[str]:
    return {
        str(fields.get("id", selector.get("id")))
        for override in overrides
        if isinstance((selector := override.get("selector")), Mapping)
        and isinstance((fields := override.get("fields", {})), Mapping)
    }


def _blocked_details(result: _FullCopyResult) -> tuple[str, ...]:
    if result.failure_details:
        return result.failure_details
    return tuple(f"requires readable authored source {result.predecessor!r}: {cause.value}" for cause in result.causes)


def _build_full_copy_plan(
    revision_id: str,
    source: edition_delta_source.EditionSource,
    lift: edition_delta_source.EditionLift,
    full_rows: list[edition_delta_source.Row],
    result: _FullCopyResult,
) -> edition_delta_types.EditionPlan:
    stated_ids = frozenset(edition_delta_source.row_id(row) for row in full_rows) - result.drops
    is_delta = result.basis in {
        edition_delta_types.PredecessorBasis.ADJACENT,
        edition_delta_types.PredecessorBasis.DECLARED,
        edition_delta_types.PredecessorBasis.STORAGE,
    }
    overridden = _overridden_ids(result.overrides)
    return edition_delta_types.EditionPlan(
        revision_id=revision_id,
        basis=result.basis,
        predecessor=result.predecessor if is_delta else None,
        blocked=tuple(result.causes),
        source_default=lift.source_default,
        source_default_withheld=lift.withheld,
        rows_before=len(full_rows),
        stated_ids=tuple(
            edition_delta_source.row_id(row) for row in full_rows if edition_delta_source.row_id(row) in stated_ids
        ),
        inherited_ids=tuple(
            edition_delta_source.row_id(row)
            for row in full_rows
            if edition_delta_source.row_id(row) not in stated_ids and edition_delta_source.row_id(row) not in overridden
        ),
        lifted=edition_delta_planning_counts.lift_counts(source, lift.lifts, stated_ids),
        kept=dict(sorted(result.kept.items())),
        not_exact=tuple(result.not_exact),
        comments_dropped=_comments_dropped(source, stated_ids),
        reviewed_against=_reviewed_against(source.manifest),
        dependencies=(result.predecessor,) if result.predecessor is not None else (),
        blocked_detail=_blocked_details(result),
        casilla_overrides=result.overrides,
        casilla_removals=result.removals,
        casilla_positions=result.positions,
        lineage_attestations=result.attestations,
    )


def _comments_dropped(source: edition_delta_source.EditionSource, stated_ids: frozenset[str]) -> int:
    return sum(
        1
        for fragment in source.fragments
        for block in fragment.blocks
        if edition_delta_source.row_id(block.row) not in stated_ids and block.text.lstrip().startswith("#")
    )


def _reviewed_against(manifest: Mapping[str, object]) -> str | None:
    value = manifest.get("reviewed_against")
    return value if isinstance(value, str) else None


def plan_full_copy_edition(
    run: edition_delta_planning_state.PlanningRun,
    position: int,
    revision: ModeloRevision,
) -> edition_delta_source.EditionWork:
    """Plan a full-copy edition: choose its predecessor and the row drops, overrides and positions that reproduce it."""
    revision_id = str(revision.id)
    source = run.sources[revision_id]
    lift = edition_delta_source.edition_lift(source)
    full_rows = list(lift.rows)
    predecessor, basis, causes = edition_delta_planning_predecessor.choose_predecessor(
        position, run.ordered, source, reconsider_technical_roots=True
    )
    result = _select_full_copy_delta(
        run, revision_id, predecessor, basis, causes, full_rows, lift.lifts, source, lift.defaults
    )
    if result.causes:
        _block_copy(result, full_rows)
    if result.normalised:
        run.order_normalised.add(revision_id)
    _seed_materialised(run, revision_id, source, lift, result)
    plan = _build_full_copy_plan(revision_id, source, lift, full_rows, result)
    return edition_delta_source.EditionWork(plan=plan, source=source, lifts=lift.lifts, root_declaration=None)
