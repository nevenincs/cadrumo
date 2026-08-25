"""Current-tree fixed-point proof for the sole captured Modelo work selector.

The accompanying S170 Vaultspec-RAG query is deliberately semantic: it locates
candidate work-unit scans, repository-owning wrappers, and stale addressing
paths. This test is its fail-closed exact-AST complement: it proves every
current Python consumer reaches the canonical defining module directly, rather
than relying on a reviewed, hand-maintained consumer list.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from functools import cache
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_CADRUMO_ROOT = Path(__file__).resolve().parents[3]
_REPOSITORY_ROOT = _CADRUMO_ROOT.parents[1]
_SOURCE_ROOTS = (_CADRUMO_ROOT, _REPOSITORY_ROOT / "dev")
_SELECTION_SOURCE = _CADRUMO_ROOT / "application/modelo/work_addressing.py"
_RETIRED_SELECTION_SOURCE = _CADRUMO_ROOT / "application/modelo/_selectors.py"
_REMOVED_PRIVATE_ADDRESSING_SOURCE = _CADRUMO_ROOT / "application/modelo/_work_addressing.py"
_REMOVED_SELECTOR_SOURCE = _CADRUMO_ROOT / "application/modelo/work_unit_selection.py"
_PACKAGE_INIT = _CADRUMO_ROOT / "application/modelo/__init__.py"
_CANONICAL_MODULE = "cadrumo.application.modelo.work_addressing"
_FACADE_MODULE = "cadrumo.application.modelo"
_RETIRED_MODULES = frozenset(
    {
        "cadrumo.application.modelo._work_addressing",
        "cadrumo.application.modelo.work_unit_selection",
    }
)
_RETIRED_WORK_SELECTION_SYMBOLS = frozenset(
    {
        "ModeloWorkResolution",
        "ModeloWorkSelectorRequest",
        "select_modelo_work_resolution",
    }
)


def _all_sources() -> Iterable[Path]:
    return (path for root in _SOURCE_ROOTS for path in root.rglob("*.py"))


@cache
def _sources() -> tuple[Path, ...]:
    """Return every source that can carry the addressing/facade contract.

    Every application module is parsed because relative ``from ..modelo``
    imports have no useful raw module string. Elsewhere, the lexical prefilter
    is fail-closed for this contract's names, direct module paths, and retired
    paths, then exact AST resolves the retained candidates.
    """
    addressing_names = _defined_addressing_symbols(_tree(_SELECTION_SOURCE))
    needles = (*addressing_names, "application.modelo", "work_addressing", "_work_addressing", "work_unit_selection")
    application_root = _CADRUMO_ROOT / "application"
    candidates = []
    for path in _all_sources():
        text = path.read_text(encoding="utf-8")
        if path.is_relative_to(application_root) or any(needle in text for needle in needles):
            candidates.append(path)
    return tuple(sorted(candidates))


@cache
def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _calls(tree: ast.AST, name: str) -> tuple[ast.Call, ...]:
    return tuple(
        node for node in ast.walk(tree) if isinstance(node, ast.Call) and _call_name(node) == name
    )


def _resolved_import_module(path: Path, node: ast.ImportFrom) -> str | None:
    """Resolve a static import to an absolute module without importing source."""
    if node.level == 0:
        return node.module
    try:
        relative = path.relative_to(_CADRUMO_ROOT).with_suffix("")
    except ValueError:
        return None
    package = ("cadrumo", *relative.parts[:-1])
    parent = package[: len(package) - (node.level - 1)]
    suffix = tuple(node.module.split(".")) if node.module else ()
    return ".".join((*parent, *suffix))


def _imported_modules(path: Path, tree: ast.Module) -> frozenset[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if (module := _resolved_import_module(path, node)) is not None:
                modules.add(module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return frozenset(modules)


def _direct_canonical_import(path: Path, tree: ast.Module) -> bool:
    return _CANONICAL_MODULE in _imported_modules(path, tree) or any(
        isinstance(node, ast.Call)
        and _call_name(node) == "import_module"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and node.args[0].value == _CANONICAL_MODULE
        for node in ast.walk(tree)
    )


def _defined_addressing_symbols(tree: ast.Module) -> frozenset[str]:
    return frozenset(
        node.name
        for node in tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and not node.name.startswith("_")
    )


def _used_names(tree: ast.Module) -> frozenset[str]:
    return frozenset(node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load))


def _function_nodes(tree: ast.Module) -> Iterable[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Return module-level callables, where application selector wrappers live."""
    return (node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)))


def _has_catalogue_get(function: ast.AST) -> bool:
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "get"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "catalogue"
        for node in ast.walk(function)
    )


def _has_repository_read(function: ast.AST) -> bool:
    """Return whether a selector function creates the work catalogue repository itself."""
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "WorkUnitCatalogueRepository"
        for node in ast.walk(function)
    )


def _substitutable_natural_scan(function: ast.AST) -> bool:
    """Identify a work-unit candidate scan outside the canonical selector.

    The shape is semantic rather than path-based: a catalogue iteration that
    compares a candidate across at least two visible natural coordinates. It
    discovers a future M303-style first-match loop without an allowlist.
    """
    for node in ast.walk(function):
        if not isinstance(node, (ast.For, ast.GeneratorExp, ast.ListComp, ast.SetComp, ast.DictComp)):
            continue
        if not any(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Attribute)
            and call.func.attr == "values"
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "catalogue"
            for call in ast.walk(node)
        ):
            continue
        attributes = {
            child.attr
            for child in ast.walk(node)
            if isinstance(child, ast.Attribute)
            and isinstance(child.value, ast.Name)
            and child.value.id in {"unit", "work_unit", "candidate"}
        }
        if len(attributes & {"modelo", "filing_year", "period"}) >= 2:
            return True
    return False


def test_work_selection_fixed_point_has_one_pure_owner_and_no_parallel_scan_or_read_authority() -> None:
    """Only the canonical pure selector may scan supplied work-unit candidates."""
    selection_tree = _tree(_SELECTION_SOURCE)
    selectors = [
        node
        for node in selection_tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "select_modelo_work_resolution"
    ]
    assert len(selectors) == 1
    assert not _has_repository_read(selectors[0])
    assert {_call_name(node) for node in ast.walk(selectors[0]) if isinstance(node, ast.Call)}.isdisjoint(
        {"resolve_active_bucket_id"}
    )
    assert "WorkUnitCatalogueRepository" not in {
        node.id for node in ast.walk(selection_tree) if isinstance(node, ast.Name)
    }

    selector_definitions = [
        (path, function)
        for path in _sources()
        for function in _function_nodes(_tree(path))
        if _calls(function, "select_modelo_work_resolution")
    ]
    assert selector_definitions, "the canonical selector has no consumer census"
    assert all(
        path == _SELECTION_SOURCE or "tests" in path.parts or not _has_repository_read(function)
        for path, function in selector_definitions
    ), selector_definitions
    assert all(
        path == _SELECTION_SOURCE or not _has_catalogue_get(function)
        for path, function in selector_definitions
    ), selector_definitions

    parallel_scans = [
        (path, function.name)
        for path in _sources()
        if path != _SELECTION_SOURCE
        for function in _function_nodes(_tree(path))
        if _substitutable_natural_scan(function)
    ]
    assert parallel_scans == [], parallel_scans

    retired_tree = _tree(_RETIRED_SELECTION_SOURCE)
    retired_definitions = {
        node.name for node in retired_tree.body if isinstance(node, (ast.ClassDef, ast.FunctionDef))
    }
    assert _RETIRED_WORK_SELECTION_SYMBOLS.isdisjoint(retired_definitions)
    assert not _REMOVED_PRIVATE_ADDRESSING_SOURCE.exists()
    assert not _REMOVED_SELECTOR_SOURCE.exists()


def test_every_current_addressing_consumer_uses_direct_defining_import_and_modelo_namespace_is_inert() -> None:
    """Census production, tests, tooling, annotations, registrations, and dynamic consumers."""
    addressing_symbols = _defined_addressing_symbols(_tree(_SELECTION_SOURCE))
    facade_imports: list[Path] = []
    stale_imports: list[tuple[Path, str]] = []
    indirect_consumers: list[Path] = []

    for source in _sources():
        tree = _tree(source)
        modules = _imported_modules(source, tree)
        if _FACADE_MODULE in modules:
            facade_imports.append(source)
        stale_imports.extend((source, module) for module in modules & _RETIRED_MODULES)
        if source != _SELECTION_SOURCE and _used_names(tree) & addressing_symbols and not _direct_canonical_import(source, tree):
            indirect_consumers.append(source)

    assert facade_imports == [], facade_imports
    assert stale_imports == [], stale_imports
    assert indirect_consumers == [], indirect_consumers

    package_tree = _tree(_PACKAGE_INIT)
    assert not any(
        isinstance(node, ast.Import)
        or (isinstance(node, ast.ImportFrom) and node.module != "__future__")
        for node in package_tree.body
    )
    assert all(
        isinstance(node, (ast.Expr, ast.Assign, ast.AnnAssign))
        or (isinstance(node, ast.ImportFrom)
        and node.module == "__future__")
        for node in package_tree.body
    )
