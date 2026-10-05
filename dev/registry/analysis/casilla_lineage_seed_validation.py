"""Check planned lineage writes against the same cross-revision registry laws."""

from __future__ import annotations

import collections
from itertools import pairwise

from cadrumo.domain.calculations.registry.casilla_lineage import CasillaLineageOrigin
from cadrumo.domain.calculations.registry.revision_order import ordered_revisions
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from ..compiler.registry_scope import validate_registry_scope
from .casilla_lineage_seed_types import LineagePlan


def contradictions(modelo: ModeloDefinition, plan: LineagePlan) -> list[str]:
    """Cross-revision contradictions the planned state would contain.

    A continuation must find its chain on the predecessor edition; an absence
    must not. Checked over every row carrying an origin once the plan is applied.
    """
    revisions = ordered_revisions(modelo)
    stated = _stated_rows(revisions, plan)
    return [
        problem
        for previous, successor in pairwise(revisions)
        for problem in _pair_contradictions(previous.id, successor.id, stated)
    ]


def _stated_rows(revisions, plan: LineagePlan) -> dict[tuple[str, str], dict[str, str | None]]:
    stated: dict[tuple[str, str], dict[str, str | None]] = {}
    for revision in revisions:
        for casilla in revision.casillas:
            row = {
                "continuidad_id": casilla.continuidad_id,
                "continuidad_origin": None if casilla.continuidad_origin is None else casilla.continuidad_origin.value,
            }
            row.update(plan.edits.get((revision.id, casilla.id), {}))
            stated[(revision.id, casilla.id)] = row
    return stated


def _pair_contradictions(
    previous: str,
    successor: str,
    stated: dict[tuple[str, str], dict[str, str | None]],
) -> list[str]:
    prior = {row["continuidad_id"] for (revision, _), row in stated.items() if revision == previous} - {None}
    problems: list[str] = []
    seen: collections.Counter[str] = collections.Counter()
    for (revision, casilla_id), row in stated.items():
        if revision != successor:
            continue
        chain, origin = row["continuidad_id"], row["continuidad_origin"]
        if chain is not None:
            seen[chain] += 1
        conflict = _row_origin_conflict(previous, successor, casilla_id, chain, origin, prior)
        if conflict is not None:
            problems.append(conflict)
    problems.extend(f"{successor}: chain {chain!r} on {count} rows" for chain, count in seen.items() if count > 1)
    return problems


def _row_origin_conflict(
    previous: str,
    successor: str,
    casilla_id: str,
    chain: str | None,
    origin: str | None,
    prior: set[str | None],
) -> str | None:
    if origin is None:
        return None
    continues = CasillaLineageOrigin(origin).continues_a_chain
    if continues and chain not in prior:
        return f"{successor}/{casilla_id}: {origin} but chain {chain!r} absent from {previous}"
    if not continues and chain is not None and chain in prior:
        return f"{successor}/{casilla_id}: {origin} but chain {chain!r} present in {previous}"
    return None


def materialise(modelo: ModeloDefinition, plan: LineagePlan) -> ModeloDefinition:
    """The modelo as it will load once the plan is written."""
    revisions = {}
    for revision_id, revision in modelo.revisions.items():
        casillas = []
        for casilla in revision.casillas:
            keys = plan.edits.get((revision.id, casilla.id))
            if keys is None:
                casillas.append(casilla)
                continue
            update: dict[str, object] = dict(keys)
            if "continuidad_origin" in update:
                update["continuidad_origin"] = CasillaLineageOrigin(keys["continuidad_origin"])
            casillas.append(casilla.model_copy(update=update))
        revisions[revision_id] = revision.model_copy(update={"casillas": tuple(casillas)})
    return modelo.model_copy(update={"revisions": revisions})


def gate_regressions(modelo: ModeloDefinition, plan: LineagePlan) -> list[str]:
    """Registry-scope failures the plan would introduce, judged by the registry's own validators.

    The seeder's incremental checks decide link by link; this is the exact
    answer, so the plan and the load-time gates cannot disagree.
    """
    if not plan.edits:
        # A plan with no edits materialises to the modelo itself, so it can regress nothing.
        return []
    before = set(validate_registry_scope((modelo,)))
    return sorted(set(validate_registry_scope((materialise(modelo, plan),))) - before)
