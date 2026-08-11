"""Static author gate for observation-envelope carry normalization callers."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_APPLICATION_ROOT = Path(__file__).resolve().parents[1] / "application"
_NORMALIZE_KEYWORD = "normalize_m303_carry"


@dataclass(frozen=True)
class _Caller:
    path: str
    function: str


_EXEMPTIONS = {
    _Caller("modelo/_local_observation_actions.py", "record_operator_local_observation"): (
        "2026-08-11: OPERATOR_MANUAL observations are not admitted by the current "
        "official/app-filing carry normalizer; the operator population must be "
        "adjudicated before this writer can opt in without over-refusal."
    ),
}

_COMPLIANT_CONTROLS = {
    _Caller("live/_filed_observation_persistence.py", "persist_filed_calculation_observation"),
    _Caller("modelo/_filed_revision_observation.py", "persist_filed_revision_observation"),
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
    for path in _APPLICATION_ROOT.rglob("*.py"):
        if "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        parents = {
            child: parent
            for parent in ast.walk(tree)
            for child in ast.iter_child_nodes(parent)
        }
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "prepare_observation_envelope"
            ):
                continue
            caller = _Caller(
                path.relative_to(_APPLICATION_ROOT).as_posix(),
                _enclosing_function(node, parents),
            )
            assert caller not in callers, f"multiple observation-door calls share caller identity {caller}"
            callers[caller] = node
    return callers


def test_every_production_observation_writer_states_carry_normalization_intent() -> None:
    callers = _production_callers()
    explicit = {
        caller
        for caller, node in callers.items()
        if any(keyword.arg == _NORMALIZE_KEYWORD for keyword in node.keywords)
    }
    exempt = set(callers) - explicit

    assert exempt == set(_EXEMPTIONS), (
        "every production caller of prepare_observation_envelope must pass "
        f"{_NORMALIZE_KEYWORD}=... explicitly or carry a dated, reviewed exemption; "
        f"unreconciled={sorted(exempt ^ set(_EXEMPTIONS), key=lambda item: (item.path, item.function))}"
    )
    assert all(reason.strip() for reason in _EXEMPTIONS.values())


def test_known_compliant_observation_writers_remain_explicit() -> None:
    callers = _production_callers()
    explicit = {
        caller
        for caller, node in callers.items()
        if any(keyword.arg == _NORMALIZE_KEYWORD for keyword in node.keywords)
    }

    assert explicit >= _COMPLIANT_CONTROLS
