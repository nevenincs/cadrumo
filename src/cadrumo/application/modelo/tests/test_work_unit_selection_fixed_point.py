"""Structural fixed-point proof for captured Modelo work selection."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CADRUMO_ROOT = Path(__file__).resolve().parents[3]
_SELECTION_SOURCE = _CADRUMO_ROOT / "application/modelo/work_addressing.py"
_RETIRED_SELECTION_SOURCE = _CADRUMO_ROOT / "application/modelo/_selectors.py"
_REMOVED_SELECTOR_SOURCE = _CADRUMO_ROOT / "application/modelo/work_unit_selection.py"
_PACKAGE_INIT = _CADRUMO_ROOT / "application/modelo/__init__.py"
_CONSUMERS = (
    _CADRUMO_ROOT / "application/modelo/work_review_projection.py",
    _CADRUMO_ROOT / "application/modelo/_external_import_actions.py",
    _CADRUMO_ROOT / "application/modelo/_calculate_input.py",
    _CADRUMO_ROOT / "application/overview/_data_prep.py",
)
_RETIRED_WORK_SELECTION_SYMBOLS = frozenset(
    {
        "ModeloWorkResolution",
        "ModeloWorkSelectorRequest",
        "select_modelo_work_resolution",
    },
)
_PUBLIC_SELECTOR_SYMBOLS = _RETIRED_WORK_SELECTION_SYMBOLS | frozenset(
    {
        "ModeloWorkRevisionConflictError",
        "ModeloWorkSelectionMode",
        "ModeloWorkSelectorContradictionError",
        "ModeloWorkSelectorError",
        "ModeloWorkSelectorState",
        "ModeloWorkUnitCandidate",
        "ModeloWorkUnitNotFoundError",
        "ModeloWorkVisibleTargetAmbiguousError",
        "resolve_active_natural_modelo_work_unit",
        "resolve_modelo_work_bucket",
        "resolve_modelo_work_unit",
    },
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def test_work_selection_fixed_point_has_one_pure_owner_and_every_substitutable_consumer() -> None:
    """The selector owns candidate scans; consumers call it exactly once per path."""
    selection_tree = _tree(_SELECTION_SOURCE)
    selector_nodes = [
        node
        for node in selection_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "select_modelo_work_resolution"
    ]
    assert len(selector_nodes) == 1
    assert {_call_name(node) for node in ast.walk(selector_nodes[0]) if isinstance(node, ast.Call)}.isdisjoint(
        {"load", "load_revisioned", "resolve_active_bucket_id"}
    )

    for consumer in _CONSUMERS:
        consumer_tree = _tree(consumer)
        calls = [
            node
            for node in ast.walk(consumer_tree)
            if isinstance(node, ast.Call) and _call_name(node) == "select_modelo_work_resolution"
        ]
        assert len(calls) == 1, consumer
        assert "for unit in" not in consumer.read_text(encoding="utf-8"), consumer
        assert any(
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.endswith("work_addressing")
            and any(alias.name == "select_modelo_work_resolution" for alias in node.names)
            for node in consumer_tree.body
        ), consumer

    retired_tree = _tree(_RETIRED_SELECTION_SOURCE)
    retired_definitions = {node.name for node in retired_tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))}
    assert _RETIRED_WORK_SELECTION_SYMBOLS.isdisjoint(retired_definitions)
    assert not _REMOVED_SELECTOR_SOURCE.exists()

    package_exports = {
        alias.name for node in _tree(_PACKAGE_INIT).body if isinstance(node, ast.ImportFrom) for alias in node.names
    }
    assert _PUBLIC_SELECTOR_SYMBOLS.isdisjoint(package_exports)
