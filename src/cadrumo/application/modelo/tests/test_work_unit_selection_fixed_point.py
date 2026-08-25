"""Structural fixed-point proof for captured Modelo work selection."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CADRUMO_ROOT = Path(__file__).resolve().parents[3]
_SELECTION_SOURCE = _CADRUMO_ROOT / "application/modelo/work_addressing.py"
_RETIRED_SELECTION_SOURCE = _CADRUMO_ROOT / "application/modelo/_selectors.py"
_REMOVED_PRIVATE_ADDRESSING_SOURCE = _CADRUMO_ROOT / "application/modelo/_work_addressing.py"
_REMOVED_SELECTOR_SOURCE = _CADRUMO_ROOT / "application/modelo/work_unit_selection.py"
_PACKAGE_INIT = _CADRUMO_ROOT / "application/modelo/__init__.py"
_SCAN_REPLACEMENT_CONSUMERS = (
    _CADRUMO_ROOT / "application/modelo/work_review_projection.py",
    _CADRUMO_ROOT / "application/modelo/_external_import_actions.py",
    _CADRUMO_ROOT / "application/modelo/_calculate_input.py",
    _CADRUMO_ROOT / "application/overview/_data_prep.py",
)
_BOUNDARY_SELECTOR_CONSUMERS = (
    _CADRUMO_ROOT / "application/modelo/_history.py",
    _CADRUMO_ROOT / "application/modelo/_reconcile.py",
    _CADRUMO_ROOT / "application/modelo/_taxation_comparison.py",
)
_PUBLIC_ADDRESSING_CONSUMERS = (
    _CADRUMO_ROOT / "application/modelo/_calculate_input.py",
    _CADRUMO_ROOT / "application/modelo/_external_import_actions.py",
    _CADRUMO_ROOT / "application/modelo/_history.py",
    _CADRUMO_ROOT / "application/modelo/_quickfile.py",
    _CADRUMO_ROOT / "application/modelo/_reconcile.py",
    _CADRUMO_ROOT / "application/modelo/_taxation_comparison.py",
    _CADRUMO_ROOT / "application/modelo/_work_lifecycle.py",
    _CADRUMO_ROOT / "application/modelo/_workspace_models.py",
    _CADRUMO_ROOT / "application/modelo/work_review_projection.py",
    _CADRUMO_ROOT / "application/overview/_data_prep.py",
    _CADRUMO_ROOT / "application/workflow/resume.py",
    _CADRUMO_ROOT / "application/workflow/tests/test_resume.py",
    _CADRUMO_ROOT / "entrypoints/cli/_config/_profile_inspect.py",
    _CADRUMO_ROOT / "entrypoints/cli/_modelo.py",
    _CADRUMO_ROOT / "entrypoints/cli/_modelo_behavior_support.py",
    _CADRUMO_ROOT / "entrypoints/cli/_modelo_cli_support.py",
    _CADRUMO_ROOT / "entrypoints/cli/_modelo_export_cli.py",
    _CADRUMO_ROOT / "entrypoints/cli/_modelo_review_package_cli.py",
    _CADRUMO_ROOT / "entrypoints/cli/_modelo_work_lifecycle_cli.py",
    _CADRUMO_ROOT / "entrypoints/cli/_modelo_work_revision_cli.py",
    _CADRUMO_ROOT / "entrypoints/cli/tests/_modelo_review_package_support.py",
    _CADRUMO_ROOT / "entrypoints/cli/tests/test_config_preflight_revision_default.py",
    _CADRUMO_ROOT / "entrypoints/tui/devtools/modelo_work_wizard.py",
    _CADRUMO_ROOT / "tests/registry_revision.py",
    _CADRUMO_ROOT / "application/modelo/tests/test_calculate_input_error_localization.py",
    _CADRUMO_ROOT / "application/modelo/tests/test_profile_readiness_gate.py",
    _CADRUMO_ROOT / "application/modelo/tests/test_revision_id_d1_contract.py",
    _CADRUMO_ROOT / "application/modelo/tests/test_selectors.py",
    _CADRUMO_ROOT / "application/modelo/tests/test_work_addressing.py",
    _CADRUMO_ROOT / "application/modelo/tests/test_work_period_normalization.py",
    _CADRUMO_ROOT / "application/modelo/tests/test_workspace_models.py",
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
        "resolve_modelo_work_bucket",
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


def _selector_calls(tree: ast.Module) -> list[ast.Call]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _call_name(node) == "select_modelo_work_resolution"
    ]


def _imports_pure_selector(tree: ast.Module) -> bool:
    return any(
        isinstance(node, ast.ImportFrom)
        and node.module is not None
        and node.module.endswith("work_addressing")
        and any(alias.name == "select_modelo_work_resolution" for alias in node.names)
        for node in ast.walk(tree)
    )


def _imports_defining_addressing_module(tree: ast.Module) -> bool:
    return any(
        (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.module.endswith("work_addressing")
        )
        or (
            isinstance(node, ast.Import)
            and any(alias.name.endswith(".work_addressing") for alias in node.names)
        )
        for node in ast.walk(tree)
    )


def _imported_module_names(tree: ast.Module) -> set[str]:
    return {
        module
        for node in ast.walk(tree)
        for module in (
            ((node.module,) if node.module is not None else ())
            if isinstance(node, ast.ImportFrom)
            else tuple(alias.name for alias in node.names)
            if isinstance(node, ast.Import)
            else ()
        )
    }


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
    public_definitions = {
        node.name for node in selection_tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    }
    assert {"resolve_active_natural_modelo_work_unit", "resolve_modelo_work_unit"}.isdisjoint(public_definitions)

    for consumer in _SCAN_REPLACEMENT_CONSUMERS:
        consumer_tree = _tree(consumer)
        assert len(_selector_calls(consumer_tree)) == 1, consumer
        assert "for unit in" not in consumer.read_text(encoding="utf-8"), consumer
        assert _imports_pure_selector(consumer_tree), consumer

    for consumer in _BOUNDARY_SELECTOR_CONSUMERS:
        consumer_tree = _tree(consumer)
        assert len(_selector_calls(consumer_tree)) == 1, consumer
        assert _imports_pure_selector(consumer_tree), consumer

    retired_tree = _tree(_RETIRED_SELECTION_SOURCE)
    retired_definitions = {node.name for node in retired_tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))}
    assert _RETIRED_WORK_SELECTION_SYMBOLS.isdisjoint(retired_definitions)
    assert not _REMOVED_PRIVATE_ADDRESSING_SOURCE.exists()
    assert not _REMOVED_SELECTOR_SOURCE.exists()

    package_exports = {
        alias.name for node in _tree(_PACKAGE_INIT).body if isinstance(node, ast.ImportFrom) for alias in node.names
    }
    assert _PUBLIC_SELECTOR_SYMBOLS.isdisjoint(package_exports)


def test_every_current_addressing_consumer_directly_imports_the_sole_defining_module() -> None:
    """Census static, local, type-only, test, CLI, TUI, and workflow imports."""
    for consumer in _PUBLIC_ADDRESSING_CONSUMERS:
        assert _imports_defining_addressing_module(_tree(consumer)), consumer

    for source in _CADRUMO_ROOT.rglob("*.py"):
        imported_modules = _imported_module_names(_tree(source))
        assert not any(
            module in {"_work_addressing", "work_unit_selection"}
            or module.endswith(("._work_addressing", ".work_unit_selection"))
            for module in imported_modules
        ), source
