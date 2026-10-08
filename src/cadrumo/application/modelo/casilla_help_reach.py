"""Canonical reach graph and box-path view for one casilla's formula dependents."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Iterable, Mapping

from pydantic import BaseModel

from ...core.casilla_id import CasillaId
from ...core.models import STRICT_FROZEN_CONFIG
from ...domain.calculations.registry.schema import FormulaDefinition, RegistrySnapshot
from ...domain.calculations.registry.schema_formula import FormulaExpression
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from .printed_boxes import PrintedBoxes
from .settlement_casilla import declaration_result_casillas


class ModeloHelpBoxV1(BaseModel):
    """One box a change passes through, written as the filer reads it ("[07]")."""

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: CasillaId
    box: str


class ModeloHelpReachV1(BaseModel):
    """How a change travels through formula dependents toward the declaration's result."""

    model_config = STRICT_FROZEN_CONFIG

    path: tuple[ModeloHelpBoxV1, ...]
    others: tuple[ModeloHelpBoxV1, ...]


def _uses(formula: FormulaDefinition) -> set[str]:
    found: set[str] = set()
    pending: list[FormulaExpression] = [formula.expression]
    while pending:
        node = pending.pop()
        if node.casilla_id is not None:
            found.add(str(node.casilla_id))
        pending.extend(node.args)
    return found


def _dependents(formulas: Iterable[FormulaDefinition]) -> dict[str, frozenset[str]]:
    """Each casilla's direct dependents: the casillas whose formula reads it."""
    graph: dict[str, set[str]] = {}
    for formula in formulas:
        target = str(formula.target_casilla_id)
        for used in _uses(formula):
            if used != target:
                graph.setdefault(used, set()).add(target)
    return {used: frozenset(targets) for used, targets in graph.items()}


def _walk_dependents(
    start: str, *, graph: Mapping[str, frozenset[str]], results: frozenset[str], boxes: PrintedBoxes
) -> tuple[dict[str, str], set[str], str | None]:
    def order(key: str) -> tuple[bool, str]:
        return (not boxes.prints(key), key)

    parents: dict[str, str] = {}
    reached: set[str] = {start}
    queue: deque[str] = deque([start])
    found: str | None = None
    while queue:
        node = queue.popleft()
        for following in sorted(graph.get(node, frozenset()), key=order):
            if following in reached:
                continue
            reached.add(following)
            parents[following] = node
            if found is None and following in results:
                found = following
            queue.append(following)
    return parents, reached, found


def _route_from_parents(start: str, found: str | None, parents: Mapping[str, str]) -> list[str]:
    route: list[str] = []
    step = found
    while step is not None and step != start:
        route.append(step)
        step = parents.get(step)
    route.reverse()
    return route


def _path_boxes(
    route: list[str],
    *,
    results: frozenset[str],
    casillas: Mapping[str, CasillaDefinition],
    boxes: PrintedBoxes,
    box_text: Callable[[str], str],
) -> tuple[ModeloHelpBoxV1, ...]:
    return tuple(
        ModeloHelpBoxV1(casilla_id=casillas[key].id, box=box_text(key))
        for key in route
        if key in results or boxes.prints(key)
    )


def _other_reached_boxes(
    start: str,
    reached: set[str],
    on_path: set[str],
    *,
    casillas: Mapping[str, CasillaDefinition],
    boxes: PrintedBoxes,
    box_text: Callable[[str], str],
) -> tuple[ModeloHelpBoxV1, ...]:
    return tuple(
        ModeloHelpBoxV1(casilla_id=casillas[key].id, box=box_text(key))
        for key in sorted(reached)
        if key != start and key not in on_path and boxes.prints(key)
    )


def _reach(
    start: str,
    *,
    graph: Mapping[str, frozenset[str]],
    results: frozenset[str],
    casillas: Mapping[str, CasillaDefinition],
    boxes: PrintedBoxes,
    box_text: Callable[[str], str],
) -> ModeloHelpReachV1:
    """Choose the shortest path, preferring printed boxes and then lower ids on ties."""
    parents, reached, found = _walk_dependents(start, graph=graph, results=results, boxes=boxes)
    route = _route_from_parents(start, found, parents)
    path = _path_boxes(route, results=results, casillas=casillas, boxes=boxes, box_text=box_text)
    others = _other_reached_boxes(start, reached, set(route), casillas=casillas, boxes=boxes, box_text=box_text)
    return ModeloHelpReachV1(path=path, others=others)


def build_casilla_help_reach(
    casilla: CasillaDefinition,
    *,
    snapshot: RegistrySnapshot,
    casillas: Mapping[str, CasillaDefinition],
    boxes: PrintedBoxes,
    box_text: Callable[[str], str],
) -> tuple[tuple[str, ...], bool, ModeloHelpReachV1 | None]:
    """Return immediate dependents, result status, and the deterministic result route.

    Parameter types: ``snapshot`` (:class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`).
    """
    graph = _dependents(snapshot.revision.formulas)
    feeds = tuple(sorted({box_text(target) for target in graph.get(str(casilla.id), frozenset())}))
    selected = declaration_result_casillas(str(snapshot.modelo.id), snapshot.revision)
    results: frozenset[str] = (
        frozenset[str]() if selected is None else frozenset(str(item) for item in selected.casilla_ids)
    )
    is_result = str(casilla.id) in results
    reach = (
        None
        if is_result or not results
        else _reach(str(casilla.id), graph=graph, results=results, casillas=casillas, boxes=boxes, box_text=box_text)
    )
    return feeds, is_result, reach


__all__ = ["ModeloHelpBoxV1", "ModeloHelpReachV1", "build_casilla_help_reach"]
