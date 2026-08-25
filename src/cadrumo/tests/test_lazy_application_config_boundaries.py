"""Structural gates for lazy application and read-only configuration boundaries."""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC = Path("src/cadrumo")
_WORKFLOW = _SRC / "application" / "workflow"
_WRITE_SIDE_MODULES = frozenset(
    {
        "cadrumo.application._journal_repository",
        "cadrumo.application.operations.persistence._journal",
        "cadrumo.core.file_permissions",
        "cadrumo.core.logging",
        "cadrumo.core.storage_materialization",
    }
)


def _runtime_imports(tree: ast.Module) -> list[ast.Import | ast.ImportFrom]:
    """Return imports executed at module import time, excluding guarded/type-only code."""
    found: list[ast.Import | ast.ImportFrom] = []

    def visit(statements: Iterable[ast.stmt]) -> None:
        for node in statements:
            if isinstance(node, ast.Import | ast.ImportFrom):
                found.append(node)
            elif isinstance(node, ast.If):
                is_type_checking = isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING"
                if not is_type_checking:
                    visit(node.body)
                    visit(node.orelse)
            elif isinstance(node, ast.Try):
                visit(node.body)
                visit(node.orelse)
                visit(node.finalbody)
                for handler in node.handlers:
                    visit(handler.body)
            elif isinstance(node, ast.With | ast.AsyncWith):
                visit(node.body)
            elif isinstance(node, ast.For | ast.AsyncFor | ast.While):
                visit(node.body)
                visit(node.orelse)
            elif isinstance(node, ast.Match):
                for case in node.cases:
                    visit(case.body)

    visit(tree.body)
    return found


def _module_level_workflow_graph(sources: dict[str, str]) -> dict[str, set[str]]:
    """Build the internal workflow import graph from source text."""
    graph = {name: set() for name in sources}
    for name, source in sources.items():
        tree = ast.parse(source, filename=name)
        for node in _runtime_imports(tree):
            if isinstance(node, ast.Import):
                targets = tuple(
                    alias.name.removeprefix("cadrumo.application.workflow.").split(".", maxsplit=1)[0]
                    for alias in node.names
                    if alias.name.startswith("cadrumo.application.workflow.")
                )
            elif isinstance(node, ast.ImportFrom) and node.level:
                targets = (
                    (node.module.split(".", maxsplit=1)[0],)
                    if node.module
                    else tuple(alias.name for alias in node.names)
                )
            elif isinstance(node, ast.ImportFrom) and (node.module or "").startswith("cadrumo.application.workflow."):
                targets = (node.module.removeprefix("cadrumo.application.workflow.").split(".", maxsplit=1)[0],)
            else:
                targets = ()
            graph[name].update(target for target in targets if target in graph)
        for target in _runtime_dynamic_import_targets(tree):
            internal = (
                target.lstrip(".") if target.startswith(".") else target.removeprefix("cadrumo.application.workflow.")
            )
            internal = internal.split(".", maxsplit=1)[0]
            if internal in graph:
                graph[name].add(internal)
    return graph


def _runtime_dynamic_import_targets(tree: ast.Module) -> set[str]:
    """Return literal dynamic imports executed while the module initializes."""
    targets: set[str] = set()

    class Visitor(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            return

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            return

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            return

        def visit_If(self, node: ast.If) -> None:
            if isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
                return
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            called = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else node.func.attr
                if isinstance(node.func, ast.Attribute)
                else ""
            )
            if called in {"__import__", "import_module"} and node.args:
                argument = node.args[0]
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    targets.add(argument.value)
            self.generic_visit(node)

    Visitor().visit(tree)
    return targets


def _literal_import_targets(source: str) -> set[str]:
    """Extract direct and literal-dynamic imports from every runtime compound body."""
    targets: set[str] = set()
    tree = ast.parse(source)
    for node in _runtime_imports(tree):
        if isinstance(node, ast.Import):
            targets.update(alias.name for alias in node.names)
        elif node.module:
            targets.add(node.module)
        elif node.level:
            targets.update(f"{'.' * node.level}{alias.name}" for alias in node.names)
    targets.update(_runtime_dynamic_import_targets(tree))
    return targets


def _forbidden_write_imports(source: str) -> set[str]:
    """Return write-side modules reached by direct or literal dynamic imports."""
    targets = _literal_import_targets(source)
    return {
        forbidden
        for forbidden in _WRITE_SIDE_MODULES
        if any(
            target == forbidden
            or (target.startswith(".") and target.lstrip(".") == forbidden.rsplit(".", maxsplit=1)[-1])
            or target.endswith(f".{forbidden.rsplit('.', maxsplit=1)[-1]}")
            for target in targets
        )
    }


def _snapshot_tree(root: Path) -> tuple[tuple[str, str, int], ...]:
    """Capture relative path, kind, and size for an isolated filesystem tree."""
    if not root.exists():
        return ()
    rows: list[tuple[str, str, int]] = []
    for path in sorted(root.rglob("*")):
        kind = "dir" if path.is_dir() else "file"
        rows.append((path.relative_to(root).as_posix(), kind, 0 if kind == "dir" else path.stat().st_size))
    return tuple(rows)


def _cycles(graph: dict[str, set[str]]) -> list[tuple[str, ...]]:
    """Return module cycles from a directed graph."""
    found: set[tuple[str, ...]] = set()

    def walk(node: str, path: tuple[str, ...]) -> None:
        if node in path:
            cycle = (*path[path.index(node) :], node)
            rotations = [cycle[index:-1] + cycle[:index] + (cycle[index],) for index in range(len(cycle) - 1)]
            found.add(min(rotations))
            return
        for target in graph.get(node, set()):
            walk(target, (*path, node))

    for node in graph:
        walk(node, ())
    return sorted(found)


def test_workflow_facade_has_exact_lazy_public_parity_in_a_fresh_process() -> None:
    """Every public workflow name must have exactly one lazy owner and resolve from it."""
    script = """
import json
import cadrumo.application.workflow as facade

before = sorted(name for name in __import__('sys').modules if name.startswith(f'{facade.__name__}.'))
owners = {}
canonical = []
owner_names = {facade._LAZY_MODULE_LOADERS[path]().__name__ for path in set(facade._LAZY_EXPORTS.values())}
for name, module_path in facade._LAZY_EXPORTS.items():
    value = getattr(facade, name)
    owner = facade._LAZY_MODULE_LOADERS[module_path]()
    owners[name] = value is getattr(owner, name)
    declared_module = getattr(value, '__module__', None)
    if declared_module in owner_names and declared_module != owner.__name__:
        canonical.append({'name': name, 'declared': owner.__name__, 'actual': declared_module})
print(json.dumps({
    'before': before,
    'all': sorted(facade.__all__),
    'mapped': sorted(facade._LAZY_EXPORTS),
    'owners': owners,
    'canonical': canonical,
}))
"""
    result = subprocess.run(  # noqa: S603 - fixed interpreter and test-owned source
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    observed = json.loads(result.stdout)

    assert observed["before"] == []
    assert observed["all"] == observed["mapped"]
    assert all(observed["owners"].values())
    assert observed["canonical"] == []


def test_workflow_module_level_graph_is_acyclic_and_detector_bites() -> None:
    """Workflow import boundaries must not trade eager facade loading for an internal import cycle."""
    sources = {
        path.stem: path.read_text(encoding="utf-8") for path in _WORKFLOW.glob("*.py") if path.name != "__init__.py"
    }
    graph = _module_level_workflow_graph(sources)

    assert len(graph) > 10, "workflow source discovery is too small for this gate to be meaningful"
    assert _cycles(graph) == []
    assert _cycles({"left": {"right"}, "right": {"left"}}) == [("left", "right", "left")]
    compound_source = "with scope():\n    from . import right\n"
    assert _module_level_workflow_graph({"left": compound_source, "right": ""})["left"] == {"right"}
    dynamic_source = "from importlib import import_module\nimport_module('.right', __package__)\n"
    assert _module_level_workflow_graph({"left": dynamic_source, "right": ""})["left"] == {"right"}
    absolute_source = "import cadrumo.application.workflow.right\n"
    assert _module_level_workflow_graph({"left": absolute_source, "right": ""})["left"] == {"right"}


def test_lazy_facade_and_read_only_config_forbid_materialization_imports() -> None:
    """Metadata/config reads must not import the explicit write-side boundaries."""
    offenders: list[str] = []
    for path in (_WORKFLOW / "__init__.py", _SRC / "core" / "config.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        offenders.extend(
            f"{path.as_posix()} -> {target}" for target in sorted(_forbidden_write_imports(ast.unparse(tree)))
        )

    assert offenders == []

    real_config = (_SRC / "core" / "config.py").read_text(encoding="utf-8")
    planted = {
        "cadrumo.core.storage_materialization": real_config + "\nfrom . import storage_materialization\n",
        "cadrumo.core.file_permissions": real_config + "\nimport cadrumo.core.file_permissions as permissions\n",
        "cadrumo.core.logging": real_config + '\nimport_module("cadrumo.core.logging")\n',
        "cadrumo.application._journal_repository": real_config
        + '\n__import__("cadrumo.application._journal_repository")\n',
    }
    for expected, source in planted.items():
        assert expected in _forbidden_write_imports(source)


def test_loading_settings_and_derived_paths_does_not_materialize_storage(tmp_path: Path) -> None:
    """The read boundary remains pure in an isolated fresh process."""
    isolated_parent = tmp_path / "isolated"
    isolated_parent.mkdir()
    storage_root = isolated_parent / "state"
    before = _snapshot_tree(isolated_parent)
    script = """
import json
import os
import sys
from pathlib import Path

root = Path(os.environ['CADRUMO_LOCAL_STORAGE_ROOT'])
from cadrumo.core.config import classify_storage_route, load_settings

settings = load_settings()
paths = sorted(str(value) for value in settings.model_dump().values() if isinstance(value, Path))
classify_storage_route(settings=settings)
print(json.dumps({
    'exists': root.exists(),
    'paths': paths,
    'write_modules': sorted(name for name in sys.modules if name in __WRITE_MODULES__),
}))
""".replace("__WRITE_MODULES__", repr(sorted(_WRITE_SIDE_MODULES)))
    result = subprocess.run(  # noqa: S603 - fixed interpreter and test-owned source
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "CADRUMO_LOCAL_STORAGE_ROOT": str(storage_root),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )
    observed = json.loads(result.stdout)

    assert observed["paths"], "settings exposed no derived paths; the purity assertion would be vacuous"
    assert observed["exists"] is False
    assert observed["write_modules"] == []
    assert not storage_root.exists()
    assert _snapshot_tree(isolated_parent) == before


def test_filesystem_purity_observation_bites_on_real_materialization(tmp_path: Path) -> None:
    """The filesystem equality oracle detects the production write boundary."""
    from ..core.config import Settings
    from ..core.storage_materialization import ensure_storage_tree

    isolated_parent = tmp_path / "isolated"
    isolated_parent.mkdir()
    before = _snapshot_tree(isolated_parent)
    ensure_storage_tree(Settings(cadrumo_local_storage_root=isolated_parent / "state"))

    assert _snapshot_tree(isolated_parent) != before
