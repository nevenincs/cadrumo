"""Static author gate for canonical observation-envelope writers."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

from ..core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PRODUCTION_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class _Caller:
    path: str
    function: str


_CANONICAL_WRITE_DOOR_CALLERS = {
    _Caller(
        "application/live/filed_observation_persistence.py",
        "persist_filed_calculation_observation",
    ),
    _Caller(
        "application/modelo/external_import_actions.py",
        "import_external_filing_evidence",
    ),
    _Caller(
        "application/modelo/filed_revision_observation.py",
        "persist_filed_revision_observation",
    ),
    _Caller(
        "application/modelo/local_observation_actions.py",
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


def test_every_production_observation_writer_uses_the_canonical_write_door() -> None:
    callers = _production_callers()
    assert set(callers) == _CANONICAL_WRITE_DOOR_CALLERS
    assert all(
        all(keyword.arg != "normalize_m303_carry" for keyword in node.keywords)
        for node in callers.values()
    ), "the canonical observation write door owns M303 normalization"


def test_production_observation_writer_population_is_exhaustively_adjudicated() -> None:
    callers = _production_callers()
    assert set(callers) == _CANONICAL_WRITE_DOOR_CALLERS, (
        "every production prepare_observation_envelope caller must enter the reviewed "
        "canonical write-door population; "
        f"unreviewed={sorted(set(callers) - _CANONICAL_WRITE_DOOR_CALLERS, key=lambda item: (item.path, item.function))}, "
        f"missing={sorted(_CANONICAL_WRITE_DOOR_CALLERS - set(callers), key=lambda item: (item.path, item.function))}"
    )
