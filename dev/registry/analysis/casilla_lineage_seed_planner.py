"""Coordinate per-modelo lineage planning and preserve unresolved-row coverage."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from cadrumo.domain.calculations.registry.casilla_lineage_totality import (
    unresolved_successor_rows,
)
from cadrumo.domain.calculations.registry.errors import RegistryError
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from .casilla_lineage_seed_design import (
    DesignOracle,
)
from .casilla_lineage_seed_modelo_planner import _ModeloPlanner
from .casilla_lineage_seed_types import (
    EXCLUDED_MODELOS,
    LineagePlan,
    LineageRefusalCategory,
    PartialStamping,
    Ruling,
    _partial_stamping_error,
)


def plan_modelo(
    modelo_id: str,
    modelo: ModeloDefinition,
    oracle: DesignOracle,
    rulings: Mapping[str, list[Ruling]],
) -> LineagePlan:
    """Plan every lineage disposition for one modelo.

    Planning repeats until no identifier would be left partly stamped: each pass
    forbids chains on the identifiers the previous pass could not settle. An
    identifier still partly stamped once its chains are forbidden is the
    corpus's own half-finished state, not this plan's doing, and raises
    :class:`RegistryError` rather than being seeded on weaker evidence.
    """
    forbidden: frozenset[str] = frozenset[str]()
    while True:
        planner = _ModeloPlanner(modelo_id, modelo, oracle, rulings.get(modelo_id, []), forbidden)
        plan = planner.run()
        unsettled = planner.settle_partial_stamps()
        if not unsettled:
            return plan
        if unsettled <= forbidden:
            raise _partial_stamping_error(modelo_id, planner.partial_stamp_records(unsettled))
        forbidden |= unsettled


def plan_corpus(
    modelo_ids: Iterable[str],
    loaded: Mapping[str, ModeloDefinition],
    oracle: DesignOracle,
    rulings: Mapping[str, list[Ruling]],
) -> tuple[list[LineagePlan], tuple[PartialStamping, ...]]:
    """Plan each modelo on its own, so one left partly stamped stops only itself.

    Mirrors :func:`load_corpus` at the next stage: the blast radius of a defect
    stays at the modelo that carries it. Only :class:`RegistryError` is
    caught -- it is this planner's own boundary type for a corpus state it
    refuses to write into. Anything else is a defect in this tooling and must
    not be recorded as a data state.
    """
    plans: list[LineagePlan] = []
    partial: list[PartialStamping] = []
    for modelo_id in modelo_ids:
        try:
            plans.append(plan_modelo(modelo_id, loaded[modelo_id], oracle, rulings))
        except RegistryError as error:
            context = error.context
            if context is None:
                raise
            records = context.get("partial_stamping_records", ())
            if not isinstance(records, tuple) or not all(isinstance(record, PartialStamping) for record in records):
                raise
            partial.extend(records)
    return plans, tuple(partial)


def residual_plan(modelo_id: str, modelo: ModeloDefinition, rulings: Iterable[Ruling]) -> LineagePlan:
    """Refuse, row by row, every unresolved successor row of an excluded modelo.

    Writes nothing: the plan carries refusals only. A row an adjudicated ruling
    holds, withholds or merges is refused under that ruling's category and
    reason; every other row takes the modelo's residual category. The rows are
    exactly those the lineage totality rule reports, so the ledger and the gate
    reading it cannot disagree about which rows need an entry.
    """
    excluded = EXCLUDED_MODELOS[modelo_id]
    ruled: dict[tuple[str, str], tuple[LineageRefusalCategory, str, str]] = {}
    for ruling in rulings:
        for category, pairs, reason in (
            (LineageRefusalCategory.HELD, ruling.held, ruling.held_reason),
            (LineageRefusalCategory.WITHHELD, ruling.withheld, ruling.withheld_reason),
            (LineageRefusalCategory.MERGED, ruling.merged, ruling.merged_reason),
        ):
            for predecessor, successor in pairs:
                ruled[(ruling.successor, successor)] = (category, reason, predecessor)
    rows = {
        (str(revision.id), str(casilla.id)): casilla
        for revision in modelo.revisions.values()
        for casilla in revision.casillas
    }
    plan = LineagePlan(modelo_id)
    for key in unresolved_successor_rows(modelo):
        if excluded.residual_category is None:
            raise ValueError(
                f"modelo {modelo_id} {key.revision}/{key.casilla}: an unresolved successor row in a modelo that "
                f"cannot have one ({excluded.residual_reason})"
            )
        precise = ruled.get((key.revision, key.casilla))
        if precise is not None:
            category, reason, predecessor = precise
            plan.refuse(key.revision, key.casilla, category, reason, predecessor)
            continue
        chain = rows[(key.revision, key.casilla)].continuidad_id
        shape = "no continuidad_id" if chain is None else f"continuidad_id {chain!r} starts its chain in this edition"
        plan.refuse(key.revision, key.casilla, excluded.residual_category, f"{excluded.residual_reason}; {shape}")
    return plan
