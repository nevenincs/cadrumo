"""Static author gate for observation-envelope carry normalization callers."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

from ..core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PRODUCTION_ROOT = Path(__file__).resolve().parents[1]
_NORMALIZE_KEYWORD = "normalize_m303_carry"


@dataclass(frozen=True)
class _Caller:
    path: str
    function: str


_LITERAL_NORMALIZING_CONTROLS = {
    _Caller(
        "application/live/filed_observation_persistence.py",
        "persist_filed_calculation_observation",
    ),
}
_CONDITIONAL_NORMALIZING_CONTROLS = {
    _Caller(
        "application/modelo/_filed_revision_observation.py",
        "persist_filed_revision_observation",
    ): "work_unit.modelo == Modelo.M303.value",
}
_NON_NORMALIZING_CONTROLS = {
    _Caller(
        "application/modelo/_local_observation_actions.py",
        "record_operator_local_observation",
    ),
}


def _enclosing_function(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    current = node
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return current.name
    return "<module>"


def _production_callers() -> dict[_Caller, ast.Call]:
    callers: dict[_Caller, ast.Call] = {}
    for path in scan_directory(_PRODUCTION_ROOT, pattern="*.py", recursive=True):
        if "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "prepare_observation_envelope"
            ):
                continue
            caller = _Caller(
                path.relative_to(_PRODUCTION_ROOT).as_posix(),
                _enclosing_function(node, parents),
            )
            assert caller not in callers, f"multiple observation-door calls share caller identity {caller}"
            callers[caller] = node
    return callers


def _normalization_expression(node: ast.Call) -> ast.expr:
    keyword = next(
        (item for item in node.keywords if item.arg == _NORMALIZE_KEYWORD),
        None,
    )
    assert keyword is not None
    return keyword.value


def test_every_production_observation_writer_states_carry_normalization_intent() -> None:
    callers = _production_callers()
    explicit = {
        caller
        for caller, node in callers.items()
        if any(keyword.arg == _NORMALIZE_KEYWORD for keyword in node.keywords)
    }
    implicit = set(callers) - explicit

    assert not implicit, (
        "every production caller of prepare_observation_envelope must pass "
        f"{_NORMALIZE_KEYWORD}=... explicitly; "
        f"implicit={sorted(implicit, key=lambda item: (item.path, item.function))}"
    )


def test_production_observation_writer_population_is_exhaustively_adjudicated() -> None:
    callers = _production_callers()
    adjudicated = _LITERAL_NORMALIZING_CONTROLS | set(_CONDITIONAL_NORMALIZING_CONTROLS) | _NON_NORMALIZING_CONTROLS

    assert set(callers) == adjudicated, (
        "every production prepare_observation_envelope caller must enter the reviewed "
        "normalizing or non-normalizing population; "
        f"unreviewed={sorted(set(callers) - adjudicated, key=lambda item: (item.path, item.function))}, "
        f"missing={sorted(adjudicated - set(callers), key=lambda item: (item.path, item.function))}"
    )


def test_normalizing_observation_writers_retain_their_adjudicated_intent() -> None:
    callers = _production_callers()

    for caller in _LITERAL_NORMALIZING_CONTROLS:
        expression = _normalization_expression(callers[caller])
        assert isinstance(expression, ast.Constant) and expression.value is True

    for caller, expected_expression in _CONDITIONAL_NORMALIZING_CONTROLS.items():
        expression = _normalization_expression(callers[caller])
        assert ast.unparse(expression) == expected_expression


def test_operator_manual_writer_remains_explicitly_non_normalizing() -> None:
    callers = _production_callers()

    for caller in _NON_NORMALIZING_CONTROLS:
        expression = _normalization_expression(callers[caller])
        assert isinstance(expression, ast.Constant) and expression.value is False, (
            "operator-manual observations have neither official declaration headers nor a "
            "filing-boundary disposition, so opting them into carry normalization would invent "
            f"or over-refuse evidence: {caller}"
        )
