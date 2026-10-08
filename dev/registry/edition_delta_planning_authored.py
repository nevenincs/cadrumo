"""Plan already delta-authored editions without replaying their stored operations."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping

from cadrumo.domain.calculations.registry.lineage_attestation import LineageAttestation
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from . import edition_delta_errors as _edition_delta_errors
from . import edition_delta_planning_counts as _edition_delta_planning_counts
from . import edition_delta_planning_mode as _edition_delta_planning_mode
from . import edition_delta_planning_state as _edition_delta_planning_state
from . import edition_delta_row_delta_common as _edition_delta_row_delta_common
from . import edition_delta_row_delta_existing as _edition_delta_row_delta_existing
from . import edition_delta_source as _edition_delta_source
from . import edition_delta_types as _edition_delta_types
from .compiler.casilla_identity import LINEAGE_CLAIM_FIELDS


def _validate_authored_rows(
    revision_id: str,
    source: _edition_delta_source._EditionSource,
    lift: _edition_delta_source._EditionLift,
) -> tuple[tuple[str, ...], str, bool]:
    authored_ids = tuple(_edition_delta_source._row_id(row) for row in source.stated_rows())
    unheld = sorted(row_id for row_id in authored_ids if row_id not in lift.lifts)
    if unheld:
        raise _edition_delta_errors.MigrationRefusedError(
            f"edition {revision_id!r} states casillas {unheld!r} its materialisation does not hold"
        )
    semantic_predecessor = source.manifest.get("predecessor")
    storage_predecessor = source.manifest.get("casilla_storage_baseline")
    predecessor = str(semantic_predecessor if isinstance(semantic_predecessor, str) else storage_predecessor)
    return authored_ids, predecessor, not isinstance(semantic_predecessor, str)


def _authored_operation_scope(
    run: _edition_delta_planning_state.PlanningRun,
    source: _edition_delta_source._EditionSource,
    lift: _edition_delta_source._EditionLift,
    revision_id: str,
    predecessor: str,
    authored_ids: tuple[str, ...],
    storage_only: bool,
) -> tuple[
    set[str],
    Counter[_edition_delta_types.KeptReason],
    list[str],
    tuple[_edition_delta_source._Row, ...],
    tuple[LineageAttestation, ...],
]:
    if predecessor not in run.materialised:
        raise _edition_delta_errors.MigrationRefusedError(
            f"edition {revision_id!r} declares unavailable storage baseline {predecessor!r}"
        )
    return _edition_delta_row_delta_existing.choose_existing_drops(
        revision_id=revision_id,
        predecessor=predecessor,
        storage_rows=(
            _edition_delta_row_delta_common.storage_rows(run.sources[predecessor])
            if _edition_delta_planning_mode.storage_authored(run.sources[predecessor].manifest)
            else {}
        ),
        inherited=run.materialised[predecessor],
        full_rows=lift.rows,
        lifts=lift.lifts,
        source=source,
        defaults=lift.defaults,
        storage_only=storage_only,
    )


def _authored_selector_ids(
    inherited: list[_edition_delta_source._Placed],
    dropped_authored: frozenset[str],
    dropped_lineages: set[str],
) -> set[str]:
    return {
        _edition_delta_source._row_id(placed.row)
        for placed in inherited
        if _edition_delta_source._row_id(placed.row) in dropped_authored
        or _edition_delta_source._lineage(placed.row) in dropped_lineages
    }


def _matching_authored_overrides(
    overrides: tuple[_edition_delta_source._Row, ...],
    selector_ids: set[str],
) -> tuple[_edition_delta_source._Row, ...]:
    return tuple(
        override
        for override in overrides
        if isinstance((selector := override.get("selector")), Mapping) and str(selector.get("id")) in selector_ids
    )


def _build_authored_plan(
    source: _edition_delta_source._EditionSource,
    revision_id: str,
    lift: _edition_delta_source._EditionLift,
    authored_ids: tuple[str, ...],
    predecessor: str,
    drops: set[str],
    kept: Mapping[_edition_delta_types.KeptReason, int],
    not_exact: list[str],
    overrides: tuple[_edition_delta_source._Row, ...],
    attestations: tuple[LineageAttestation, ...],
) -> _edition_delta_types.EditionPlan:
    dropped_authored = frozenset(authored_ids) & drops
    stated_ids = tuple(row_id for row_id in authored_ids if row_id not in dropped_authored)
    stated = frozenset(stated_ids)
    stated_lineages = {
        _edition_delta_source._lineage(lift.lifts[row_id].row)
        for row_id in dropped_authored
        if any(claim in lift.lifts[row_id].row for claim in LINEAGE_CLAIM_FIELDS)
    }
    return _edition_delta_types.EditionPlan(
        revision_id=revision_id,
        basis=_edition_delta_types.PredecessorBasis.LIFT_ONLY,
        predecessor=predecessor,
        blocked=(),
        source_default=lift.source_default,
        source_default_withheld=lift.withheld,
        rows_before=len(lift.rows),
        stated_ids=stated_ids,
        inherited_ids=tuple(
            _edition_delta_source._row_id(row) for row in lift.rows if _edition_delta_source._row_id(row) not in stated
        ),
        lifted=_edition_delta_planning_counts.lift_counts(source, lift.lifts, stated),
        kept=dict(sorted(kept.items())),
        not_exact=tuple(not_exact),
        comments_dropped=0,
        reviewed_against=None,
        dependencies=(predecessor,),
        casilla_overrides=overrides,
        lineage_attestations=tuple(item for item in attestations if item.identity in stated_lineages),
    )


def plan_authored_edition(
    run: _edition_delta_planning_state.PlanningRun,
    revision: ModeloRevision,
) -> _edition_delta_source._EditionWork:
    """Plan an edition already in delta storage: finish its stated rows without replaying existing operations."""
    revision_id = str(revision.id)
    source = run.sources[revision_id]
    lift = _edition_delta_source._edition_lift(source)
    authored_ids, predecessor, storage_only = _validate_authored_rows(revision_id, source, lift)
    drops, kept, not_exact, generated_overrides, attestations = _authored_operation_scope(
        run, source, lift, revision_id, predecessor, authored_ids, storage_only
    )
    dropped_authored = frozenset(authored_ids) & drops
    dropped_lineages = {
        lineage
        for row_id in dropped_authored
        if (lineage := _edition_delta_source._lineage(lift.lifts[row_id].row)) is not None
    }
    selector_ids = _authored_selector_ids(run.materialised[predecessor], dropped_authored, dropped_lineages)
    authored_overrides = _matching_authored_overrides(generated_overrides, selector_ids)
    plan = _build_authored_plan(
        source,
        revision_id,
        lift,
        authored_ids,
        predecessor,
        drops,
        kept,
        not_exact,
        authored_overrides,
        attestations,
    )
    run.materialised[revision_id] = [
        _edition_delta_source._Placed(lift.lifts[_edition_delta_source._row_id(row)].row, revision_id)
        for row in lift.rows
    ]
    return _edition_delta_source._EditionWork(plan=plan, source=source, lifts=lift.lifts, root_declaration=None)
