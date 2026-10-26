"""Coordinate planning for a behavior-preserving casilla edition delta migration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from cadrumo.domain.calculations.registry.revision_order import ordered_revisions
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision

from . import edition_delta_errors as _edition_delta_errors
from . import edition_delta_planning_authored as _edition_delta_planning_authored
from . import edition_delta_planning_counts as _edition_delta_planning_counts
from . import edition_delta_planning_full_copy as _edition_delta_planning_full_copy
from . import edition_delta_planning_mode as _edition_delta_planning_mode
from . import edition_delta_planning_predecessor as _edition_delta_planning_predecessor
from . import edition_delta_planning_state as _edition_delta_planning_state
from . import edition_delta_source as _edition_delta_source
from . import edition_delta_types as _edition_delta_types

__all__ = ("plan_migration",)


def plan_migration(
    modelo_dir: Path,
    definition: ModeloDefinition,
) -> _edition_delta_types.MigrationPlan:
    """Decide every edition's dependencies and transformation, writing nothing."""
    return _plan(modelo_dir, definition)[0]


def _plan(
    modelo_dir: Path,
    definition: ModeloDefinition,
) -> tuple[_edition_delta_types.MigrationPlan, tuple[_edition_delta_source._EditionWork, ...]]:
    ordered = tuple(ordered_revisions(definition))
    sources = {
        str(revision.id): _edition_delta_source._read_edition(modelo_dir, str(revision.id)) for revision in ordered
    }
    run = _edition_delta_planning_state.PlanningRun(
        modelo_dir=modelo_dir,
        definition=definition,
        ordered=ordered,
        sources=sources,
        already_delta_authored=any(
            _edition_delta_planning_mode.storage_authored(source.manifest) for source in sources.values()
        ),
    )
    planned: dict[str, _edition_delta_source._EditionWork] = {}
    for position, revision in _dependency_order(run):
        source = run.sources[str(revision.id)]
        if _edition_delta_planning_mode.storage_authored(source.manifest):
            item = _edition_delta_planning_authored.plan_authored_edition(run, revision)
        else:
            item = _edition_delta_planning_full_copy.plan_full_copy_edition(run, position, revision)
        planned[str(revision.id)] = item
    run.work.extend(planned[str(revision.id)] for revision in ordered)
    return (
        _edition_delta_types.MigrationPlan(
            modelo_id=str(definition.id),
            editions=tuple(item.plan for item in run.work),
            already_delta_authored=run.already_delta_authored,
        ),
        tuple(run.work),
    )


def _planning_dependency(
    run: _edition_delta_planning_state.PlanningRun,
    position: int,
) -> str | None:
    """Return only the baseline the existing edition planner will actually read."""
    source = run.sources[str(run.ordered[position].id)]
    if _edition_delta_planning_mode.storage_authored(source.manifest):
        declared = source.manifest.get("predecessor")
        baseline = declared if isinstance(declared, str) else source.manifest.get("casilla_storage_baseline")
        return baseline if isinstance(baseline, str) else None
    predecessor, _basis, causes = _edition_delta_planning_predecessor.choose_predecessor(
        position, run.ordered, source, reconsider_technical_roots=True
    )
    return None if causes else predecessor


def _dependency_order(
    run: _edition_delta_planning_state.PlanningRun,
) -> tuple[tuple[int, ModeloRevision], ...]:
    """Evaluate storage dependencies first without changing chronological selection or reporting.

    Storage ancestry can point to a later edition. Keep each original position
    for predecessor selection, and reject a planning cycle rather than invent
    a different baseline. The walk is iterative and visits each edition once.
    """
    positions = {str(revision.id): position for position, revision in enumerate(run.ordered)}
    settled: set[int] = set()
    ordered: list[tuple[int, ModeloRevision]] = []
    for start in range(len(run.ordered)):
        path: list[int] = []
        visiting: set[int] = set()
        current = start
        while current not in settled:
            if current in visiting:
                cycle = [*path[path.index(current) :], current]
                chain = " -> ".join(repr(str(run.ordered[position].id)) for position in cycle)
                raise _edition_delta_errors.MigrationRefusedError(f"cyclic edition planning dependency: {chain}")
            path.append(current)
            visiting.add(current)
            dependency = _planning_dependency(run, current)
            if dependency is None:
                break
            if dependency not in positions:
                revision_id = str(run.ordered[current].id)
                raise _edition_delta_errors.MigrationRefusedError(
                    f"edition {revision_id!r} declares unavailable storage baseline {dependency!r}"
                )
            current = positions[dependency]
        for position in reversed(path):
            settled.add(position)
            ordered.append((position, run.ordered[position]))
    return tuple(ordered)


def _lift_authored_edition(
    revision: ModeloRevision,
    source: _edition_delta_source._EditionSource,
    *,
    storage_only: bool,
) -> _edition_delta_source._EditionWork:
    revision_id = str(revision.id)
    lift = _edition_delta_source._edition_lift(source)
    stated_ids = tuple(
        _edition_delta_source._row_id(block.row) for fragment in source.fragments for block in fragment.blocks
    )
    unheld = sorted(row_id for row_id in stated_ids if row_id not in lift.lifts)
    if unheld:
        raise _edition_delta_errors.MigrationRefusedError(
            f"edition {revision_id!r} states casillas {unheld!r} its materialisation does not hold",
        )
    stated = frozenset(stated_ids)
    declared = source.manifest.get("predecessor")
    plan = _edition_delta_types.EditionPlan(
        revision_id=revision_id,
        basis=(
            _edition_delta_types.PredecessorBasis.STORAGE
            if storage_only
            else _edition_delta_types.PredecessorBasis.LIFT_ONLY
        ),
        predecessor=declared if isinstance(declared, str) else None,
        blocked=(),
        source_default=lift.source_default,
        source_default_withheld=lift.withheld,
        rows_before=len(lift.rows),
        stated_ids=stated_ids,
        inherited_ids=tuple(
            row_id for row in lift.rows if (row_id := _edition_delta_source._row_id(row)) not in stated
        ),
        lifted=_edition_delta_planning_counts.lift_counts(source, lift.lifts, stated),
        kept={},
        not_exact=(),
        comments_dropped=0,
        reviewed_against=None,
    )
    return _edition_delta_source._EditionWork(plan=plan, source=source, lifts=lift.lifts, root_declaration=None)


def _plan_lift_in_place(
    definition: ModeloDefinition,
    ordered: Sequence[ModeloRevision],
    sources: Mapping[str, _edition_delta_source._EditionSource],
    *,
    storage_only: bool = False,
) -> tuple[_edition_delta_types.MigrationPlan, tuple[_edition_delta_source._EditionWork, ...]]:
    """Lift restated defaults in place while preserving every authored delta operation."""
    work = [
        _lift_authored_edition(revision, sources[str(revision.id)], storage_only=storage_only) for revision in ordered
    ]
    return (
        _edition_delta_types.MigrationPlan(
            modelo_id=str(definition.id),
            editions=tuple(item.plan for item in work),
            already_delta_authored=True,
        ),
        tuple(work),
    )
