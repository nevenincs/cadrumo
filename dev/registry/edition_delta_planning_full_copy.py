"""Plan full-copy editions against a proved predecessor baseline."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field

from cadrumo.domain.calculations.registry.lineage_attestation import LineageAttestation
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from . import edition_delta_errors as _edition_delta_errors
from . import edition_delta_planning_counts as _edition_delta_planning_counts
from . import edition_delta_planning_predecessor as _edition_delta_planning_predecessor
from . import edition_delta_planning_state as _edition_delta_planning_state
from . import edition_delta_row_delta as _edition_delta_row_delta
from . import edition_delta_source as _edition_delta_source
from . import edition_delta_types as _edition_delta_types


@dataclass
class _FullCopyResult:
    predecessor: str | None
    basis: _edition_delta_types.PredecessorBasis
    causes: list[_edition_delta_types.BlockedCause]
    drops: set[str] = field(default_factory=set)
    kept: Counter[_edition_delta_types.KeptReason] = field(default_factory=Counter)
    not_exact: list[str] = field(default_factory=list)
    overrides: tuple[_edition_delta_source._Row, ...] = ()
    removals: tuple[_edition_delta_source._Row, ...] = ()
    positions: tuple[_edition_delta_source._Row, ...] = ()
    attestations: tuple[LineageAttestation, ...] = ()
    reconstructed_order: tuple[str, ...] = ()
    normalised: bool = False
    failure_details: tuple[str, ...] = ()


def _select_full_copy_delta(
    run: _edition_delta_planning_state.PlanningRun,
    revision_id: str,
    predecessor: str | None,
    basis: _edition_delta_types.PredecessorBasis,
    causes: list[_edition_delta_types.BlockedCause],
    full_rows: list[_edition_delta_source._Row],
    lifts: Mapping[str, _edition_delta_source._Lift],
    source: _edition_delta_source._EditionSource,
    defaults: _edition_delta_source._Defaults,
) -> _FullCopyResult:
    result = _FullCopyResult(
        predecessor=predecessor,
        basis=basis,
        causes=causes,
        reconstructed_order=tuple(_edition_delta_source._row_id(row) for row in full_rows),
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
        ) = _edition_delta_row_delta._choose_drops(
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
            storage_only=basis is _edition_delta_types.PredecessorBasis.STORAGE,
        )
    except _edition_delta_errors.MigrationRefusedError as exc:
        result.causes = [_edition_delta_types.BlockedCause.TRANSFORMATION_FAILED]
        result.failure_details = (f"requires readable authored source {predecessor!r}; transformation failed: {exc}",)
    return result


def _block_copy(result: _FullCopyResult, full_rows: list[_edition_delta_source._Row]) -> None:
    result.basis = _edition_delta_types.PredecessorBasis.BLOCKED
    result.drops = set()
    result.kept = Counter()
    result.not_exact = []
    result.overrides = ()
    result.removals = ()
    result.positions = ()
    result.attestations = ()
    result.reconstructed_order = tuple(_edition_delta_source._row_id(row) for row in full_rows)
    result.normalised = False


def _seed_materialised(
    run: _edition_delta_planning_state.PlanningRun,
    revision_id: str,
    basis: _edition_delta_types.PredecessorBasis,
    full_rows: list[_edition_delta_source._Row],
    lifts: Mapping[str, _edition_delta_source._Lift],
    reconstructed_order: tuple[str, ...],
) -> None:
    if basis is _edition_delta_types.PredecessorBasis.BLOCKED:
        full_by_id = {_edition_delta_source._row_id(row): row for row in full_rows}
        run.materialised[revision_id] = [
            _edition_delta_source._Placed(full_by_id[row_id], revision_id) for row_id in reconstructed_order
        ]
        return
    # The loader replay already proved this target, including storage overrides.
    run.materialised[revision_id] = [
        _edition_delta_source._Placed(lifts[row_id].row, revision_id) for row_id in reconstructed_order
    ]


def _overridden_ids(overrides: tuple[_edition_delta_source._Row, ...]) -> set[str]:
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
    source: _edition_delta_source._EditionSource,
    lift: _edition_delta_source._EditionLift,
    full_rows: list[_edition_delta_source._Row],
    result: _FullCopyResult,
) -> _edition_delta_types.EditionPlan:
    stated_ids = frozenset(_edition_delta_source._row_id(row) for row in full_rows) - result.drops
    is_delta = result.basis in {
        _edition_delta_types.PredecessorBasis.ADJACENT,
        _edition_delta_types.PredecessorBasis.DECLARED,
        _edition_delta_types.PredecessorBasis.STORAGE,
    }
    overridden = _overridden_ids(result.overrides)
    return _edition_delta_types.EditionPlan(
        revision_id=revision_id,
        basis=result.basis,
        predecessor=result.predecessor if is_delta else None,
        blocked=tuple(result.causes),
        source_default=lift.source_default,
        source_default_withheld=lift.withheld,
        rows_before=len(full_rows),
        stated_ids=tuple(
            _edition_delta_source._row_id(row) for row in full_rows if _edition_delta_source._row_id(row) in stated_ids
        ),
        inherited_ids=tuple(
            _edition_delta_source._row_id(row)
            for row in full_rows
            if _edition_delta_source._row_id(row) not in stated_ids
            and _edition_delta_source._row_id(row) not in overridden
        ),
        lifted=_edition_delta_planning_counts.lift_counts(source, lift.lifts, stated_ids),
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


def _comments_dropped(source: _edition_delta_source._EditionSource, stated_ids: frozenset[str]) -> int:
    return sum(
        1
        for fragment in source.fragments
        for block in fragment.blocks
        if _edition_delta_source._row_id(block.row) not in stated_ids and block.text.lstrip().startswith("#")
    )


def _reviewed_against(manifest: Mapping[str, object]) -> str | None:
    value = manifest.get("reviewed_against")
    return value if isinstance(value, str) else None


def plan_full_copy_edition(
    run: _edition_delta_planning_state.PlanningRun,
    position: int,
    revision: ModeloRevision,
) -> _edition_delta_source._EditionWork:
    """Plan a full-copy edition: choose its predecessor and the row drops, overrides and positions that reproduce it."""
    revision_id = str(revision.id)
    source = run.sources[revision_id]
    lift = _edition_delta_source._edition_lift(source)
    full_rows = list(lift.rows)
    predecessor, basis, causes = _edition_delta_planning_predecessor.choose_predecessor(
        position, run.ordered, source, reconsider_technical_roots=True
    )
    result = _select_full_copy_delta(
        run, revision_id, predecessor, basis, causes, full_rows, lift.lifts, source, lift.defaults
    )
    if result.causes:
        _block_copy(result, full_rows)
    if result.normalised:
        run.order_normalised.add(revision_id)
    _seed_materialised(run, revision_id, result.basis, full_rows, lift.lifts, result.reconstructed_order)
    plan = _build_full_copy_plan(revision_id, source, lift, full_rows, result)
    return _edition_delta_source._EditionWork(plan=plan, source=source, lifts=lift.lifts, root_declaration=None)
