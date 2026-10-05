"""Prepare a fail-closed, idempotent AEIP write plan without mutation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from cadrumo.domain.calculations.registry.errors import RegistryLoadError

from ..compiler.loader import load_modelo_directory
from . import constants as _constants
from .adjudications import AdjudicationSet
from .apply_preparation_evolutions import desired_evolutions, existing_evolutions, prepare_evolution_writes
from .apply_preparation_stamps import prepare_stamp_writes
from .apply_support import _add_refusal, _safe_resolve
from .stale_adjudications import detect_stale_adjudications
from .types import (
    AeipApplyPlan,
    AeipEvolutionWrite,
    AeipInventory,
    AeipOccurrence,
    AeipStampWrite,
    ChainPlan,
    ChainPlanEntry,
    EvolutionPair,
)

__all__ = ("prepare_apply",)

_RowKey = tuple[str, str]
_PlannedRow = tuple[str, bool, AeipOccurrence]
_PairEndpoint = tuple[ChainPlanEntry, EvolutionPair, AeipOccurrence, AeipOccurrence | None]


def prepare_apply(
    modelos_root: Path,
    inventory: AeipInventory,
    plan: ChainPlan,
    adjudications: AdjudicationSet,
    *,
    modelo_id: str = "100",
) -> AeipApplyPlan:
    """Preflight every stamp and evolution target against Modelo 100."""
    refusals: list[str] = []
    seen_refusals: set[str] = set()
    if modelo_id != "100":
        _add_refusal(refusals, seen_refusals, f"AEIP apply is restricted to Modelo 100, not {modelo_id!r}")
    base_root, modelo_root = _resolve_registry_root(modelos_root, modelo_id, refusals, seen_refusals)
    if base_root is None or modelo_root is None:
        return _empty_plan(refusals)

    _record_unresolved_judgments(plan, inventory, adjudications, refusals, seen_refusals)
    definition = _load_canonical_modelo(modelo_root, modelo_id, refusals, seen_refusals)
    if definition is None:
        return _empty_plan(refusals)

    current_rows = _index_current_rows(definition, refusals, seen_refusals)
    planned_rows, pair_endpoints = _index_plan_rows(plan, refusals, seen_refusals)
    existing_stamps, stamp_writes = prepare_stamp_writes(
        modelo_root, current_rows, planned_rows, pair_endpoints, refusals, seen_refusals
    )
    _refuse_unplanned_lineage(inventory, current_rows, planned_rows, refusals, seen_refusals)
    desired = desired_evolutions(pair_endpoints, refusals, seen_refusals)
    existing, existing_count, unexpected_count = existing_evolutions(definition, desired, refusals, seen_refusals)
    evolution_writes = prepare_evolution_writes(modelo_root, modelo_id, desired, existing, refusals, seen_refusals)
    _refuse_duplicate_targets(stamp_writes, evolution_writes, refusals, seen_refusals)
    return AeipApplyPlan(
        stamp_writes=tuple(stamp_writes),
        evolution_writes=tuple(evolution_writes),
        existing_stamps=existing_stamps,
        existing_evolutions=existing_count,
        unexpected_evolutions=unexpected_count,
        refusals=tuple(refusals),
    )


def _resolve_registry_root(
    modelos_root: Path,
    modelo_id: str,
    refusals: list[str],
    seen_refusals: set[str],
) -> tuple[Path | None, Path | None]:
    try:
        base_root = modelos_root.resolve()
    except OSError as error:
        _add_refusal(refusals, seen_refusals, f"cannot resolve modelos root: {error}")
        return None, None
    modelo_root = _safe_resolve(base_root / modelo_id, base_root)
    if modelo_root is None or not modelo_root.is_dir():
        _add_refusal(refusals, seen_refusals, f"Modelo {modelo_id} registry path is missing or unsafe")
        return None, None
    return base_root, modelo_root


def _record_unresolved_judgments(
    plan: ChainPlan,
    inventory: AeipInventory,
    adjudications: AdjudicationSet,
    refusals: list[str],
    seen_refusals: set[str],
) -> None:
    for ambiguity in plan.ambiguities:
        _add_refusal(refusals, seen_refusals, f"ambiguity [{ambiguity.kind}] {ambiguity.detail}")
    for stale in detect_stale_adjudications(inventory, adjudications):
        _add_refusal(refusals, seen_refusals, f"stale adjudication [{stale.kind}] {stale.detail}")


def _load_canonical_modelo(
    modelo_root: Path,
    modelo_id: str,
    refusals: list[str],
    seen_refusals: set[str],
) -> Any | None:
    try:
        return load_modelo_directory(modelo_root)
    except RegistryLoadError as error:
        _add_refusal(refusals, seen_refusals, f"Modelo {modelo_id} canonical load failed: {error}")
        return None


def _index_current_rows(
    definition: Any,
    refusals: list[str],
    seen_refusals: set[str],
) -> dict[_RowKey, Any]:
    current_rows: dict[_RowKey, Any] = {}
    for revision in definition.revisions.values():
        for casilla in revision.casillas:
            key = (str(revision.id), str(casilla.id))
            if key in current_rows:
                _add_refusal(refusals, seen_refusals, f"duplicate loaded casilla {key[0]}/{key[1]}")
            current_rows[key] = casilla
    return current_rows


def _index_plan_rows(
    plan: ChainPlan,
    refusals: list[str],
    seen_refusals: set[str],
) -> tuple[dict[_RowKey, _PlannedRow], list[_PairEndpoint]]:
    planned_rows: dict[_RowKey, _PlannedRow] = {}
    pair_endpoints: list[_PairEndpoint] = []
    for entry in plan.entries:
        _index_chain_occurrences(entry, planned_rows, refusals, seen_refusals)
        pair_endpoints.extend(_index_chain_pairs(entry, refusals, seen_refusals))
    return planned_rows, pair_endpoints


def _index_chain_occurrences(
    entry: ChainPlanEntry,
    planned_rows: dict[_RowKey, _PlannedRow],
    refusals: list[str],
    seen_refusals: set[str],
) -> None:
    if entry.chain_id in {existing[0] for existing in planned_rows.values()}:
        _add_refusal(refusals, seen_refusals, f"duplicate planned AEIP chain id {entry.chain_id!r}")
    for index, occurrence in enumerate(entry.occurrences):
        key = (str(occurrence.revision_id), str(occurrence.casilla_id))
        if key in planned_rows:
            _add_refusal(refusals, seen_refusals, f"duplicate planned AEIP occurrence {key[0]}/{key[1]}")
        planned_rows[key] = (entry.chain_id, index > 0, occurrence)


def _index_chain_pairs(
    entry: ChainPlanEntry,
    refusals: list[str],
    seen_refusals: set[str],
) -> list[_PairEndpoint]:
    found: list[_PairEndpoint] = []
    from .apply_support import _pair_endpoints

    for pair in entry.pairs:
        endpoints = _pair_endpoints(entry, pair)
        if endpoints is None:
            _add_refusal(
                refusals,
                seen_refusals,
                f"{entry.chain_id} {pair.from_revision}->{pair.to_revision}: cannot localize pair endpoints",
            )
            continue
        found.append((entry, pair, endpoints[0], endpoints[1]))
    return found


def _refuse_unplanned_lineage(
    inventory: AeipInventory,
    current_rows: dict[_RowKey, Any],
    planned_rows: dict[_RowKey, _PlannedRow],
    refusals: list[str],
    seen_refusals: set[str],
) -> None:
    planned_keys = set(planned_rows)
    for occurrence in inventory.occurrences:
        key = (str(occurrence.revision_id), str(occurrence.casilla_id))
        current = current_rows.get(key)
        if key not in planned_keys and current is not None and current.continuidad_id is not None:
            _add_refusal(
                refusals,
                seen_refusals,
                f"{key[0]}/{key[1]} carries AEIP continuidad_id outside the adjudicated plan",
            )
    _refuse_unplanned_category_lineage(current_rows, planned_keys, refusals, seen_refusals)


def _refuse_unplanned_category_lineage(
    current_rows: dict[_RowKey, Any],
    planned_keys: set[_RowKey],
    refusals: list[str],
    seen_refusals: set[str],
) -> None:
    for key, current in current_rows.items():
        if key in planned_keys or _constants.ANEXO_A_SECTION_LEAF not in tuple(current.section or ()):
            continue
        category_chain = None if current.continuidad_id is None else str(current.continuidad_id)
        if (
            str(current.semantic_role or "") == _constants.CATEGORY_SEMANTIC_ROLE
            and category_chain
            and category_chain.startswith(_constants.CHAIN_PREFIX)
        ):
            _add_refusal(
                refusals,
                seen_refusals,
                f"{key[0]}/{key[1]} category row carries an AEIP continuidad_id outside the plan",
            )


def _refuse_duplicate_targets(
    stamp_writes: list[AeipStampWrite],
    evolution_writes: list[AeipEvolutionWrite],
    refusals: list[str],
    seen_refusals: set[str],
) -> None:
    paths = [write.path for write in stamp_writes] + [write.path for write in evolution_writes]
    if len(paths) != len(set(paths)):
        _add_refusal(refusals, seen_refusals, "apply plan contains duplicate target paths")


def _empty_plan(refusals: list[str]) -> AeipApplyPlan:
    return AeipApplyPlan((), (), 0, 0, 0, tuple(refusals))
