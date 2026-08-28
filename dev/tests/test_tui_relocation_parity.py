"""Static parity proofs for the completed canonical TUI relocations.

These tests name each defining module directly and inspect the live source
AST for duplicate definitions or forwarding namespaces, scanned across
``src/cadrumo``, ``dev`` and ``packaging`` together -- the check only means
something with all three trees in view, which is why it lives here rather
than under ``src/cadrumo``. The real-behavior proofs that drive the shipped
Textual apps through actual application doors stay in
``src/cadrumo/entrypoints/tui/tests/test_relocation_parity.py``, since they
need no cross-tree reach.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from .._paths import REPO_ROOT as _REPO_ROOT

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CANONICAL_DEFINITIONS = (
    ("cadrumo.entrypoints.tui.profile.overview", "ProfileManagerScreen"),
    ("cadrumo.entrypoints.tui.profile.status", "StatusScreen"),
    ("cadrumo.entrypoints.tui.secret.login", "LoginScreen"),
    ("cadrumo.entrypoints.tui.secret.registration", "RegistrationScreen"),
    ("cadrumo.entrypoints.tui.secret.registration", "RecoveryWordsScreen"),
    ("cadrumo.entrypoints.tui.flows.app", "FlowScreen"),
    ("cadrumo.entrypoints.tui.modelo.view.work_review", "ModeloWorkReviewApp"),
    ("cadrumo.entrypoints.tui.modelo.view.work_review", "ModeloWorkReviewScreen"),
)

_INERT_NAMESPACES = (
    "cadrumo.entrypoints.tui",
    "cadrumo.entrypoints.tui.components",
    "cadrumo.entrypoints.tui.profile",
    "cadrumo.entrypoints.tui.secret",
    "cadrumo.entrypoints.tui.flows",
    "cadrumo.entrypoints.tui.modelo",
    "cadrumo.entrypoints.tui.modelo.view",
    "cadrumo.entrypoints.tui.devtools",
)

_TUI_ROOT = _REPO_ROOT / "src" / "cadrumo" / "entrypoints" / "tui"
_SOURCE_ROOTS = (
    _REPO_ROOT / "src" / "cadrumo",
    _REPO_ROOT / "dev",
    _REPO_ROOT / "packaging",
)
_SRC_ROOT = _REPO_ROOT / "src"
_MANAGER_MODULE = "cadrumo.entrypoints.tui.tests.manager_pilot"
_MANAGER_SYMBOL = "wait_until_settled"


def _source_trees() -> tuple[tuple[Path, ast.Module], ...]:
    return tuple(
        (path, ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
        for root in _SOURCE_ROOTS
        if root.is_dir()
        for path in sorted(root.rglob("*.py"))
    )


def _module_name(path: Path) -> str | None:
    """Return the importable module for a source file, when it is under ``src``."""
    try:
        relative = path.relative_to(_SRC_ROOT).with_suffix("")
    except ValueError:
        return None
    parts = list(relative.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _relative_target(path: Path, node: ast.ImportFrom) -> str | None:
    """Resolve a relative import from any module under ``src/cadrumo``."""
    module = _module_name(path)
    if module is None:
        return None
    package = module.split(".") if path.name == "__init__.py" else module.split(".")[:-1]
    base_length = len(package) - node.level + 1
    if base_length <= 0:
        return None
    base = package[:base_length]
    if node.module:
        base.extend(node.module.split("."))
    return ".".join(base)


def _import_from_targets(path: Path, node: ast.ImportFrom) -> tuple[str, ...]:
    base = _relative_target(path, node) if node.level else node.module
    if not base:
        return tuple(alias.name for alias in node.names if alias.name != "*")
    return (base, *(f"{base}.{alias.name}" for alias in node.names if alias.name != "*"))


def _import_targets(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    targets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = _relative_target(path, node) if node.level else node.module
            targets.append(base or "<relative>")
        elif isinstance(node, ast.Call):
            targets.extend(_dynamic_import_targets(ast.Module(body=[ast.Expr(value=node)], type_ignores=[])))
    return tuple(targets)


def _constant_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr) and all(isinstance(value, ast.Constant) for value in node.values):
        return "".join(str(value.value) for value in node.values if isinstance(value, ast.Constant))
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _constant_string(node.left)
        right = _constant_string(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _dynamic_import_targets(tree: ast.Module) -> tuple[str, ...]:
    targets: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        is_dynamic_import = (isinstance(function, ast.Name) and function.id in {"__import__", "import_module"}) or (
            isinstance(function, ast.Attribute) and function.attr == "import_module"
        )
        if is_dynamic_import and node.args:
            target = _constant_string(node.args[0])
            if target is not None:
                targets.append(target)
    return tuple(targets)


def _repo_path(path: Path) -> str:
    return path.relative_to(_REPO_ROOT).as_posix()


def _manager_edge(path: Path, node: ast.AST) -> tuple[object, ...]:
    if isinstance(node, ast.Import):
        return (_repo_path(path), "import", tuple((alias.name, alias.asname) for alias in node.names))
    if isinstance(node, ast.ImportFrom):
        return (
            _repo_path(path),
            "from",
            node.level,
            node.module or "",
            tuple((alias.name, alias.asname) for alias in node.names),
        )
    raise TypeError(f"unsupported import node: {type(node)!r}")


def _manager_target_hit(target: str) -> bool:
    return any(part in {_MANAGER_MODULE.rsplit(".", 1)[-1], _MANAGER_SYMBOL} for part in target.split("."))


def _manager_import_edges(trees: tuple[tuple[Path, ast.Module], ...]) -> tuple[tuple[object, ...], ...]:
    edges: list[tuple[object, ...]] = []
    for path, tree in trees:
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                targets = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else _import_from_targets(path, node)
                )
                if any(_manager_target_hit(target) for target in targets):
                    edges.append(_manager_edge(path, node))
        edges.extend(
            (_repo_path(path), "dynamic", target)
            for target in _dynamic_import_targets(tree)
            if _manager_target_hit(target)
        )
    return tuple(sorted(edges, key=repr))


def _class_definition_sites(class_name: str) -> tuple[Path, ...]:
    sites: list[Path] = []
    for path, tree in _source_trees():
        if any(isinstance(node, ast.ClassDef) and node.name == class_name for node in ast.walk(tree)):
            sites.append(path)
    return tuple(sites)


def _function_definition_sites(
    trees: tuple[tuple[Path, ast.Module], ...],
    function_name: str,
) -> tuple[Path, ...]:
    sites: list[Path] = []
    for path, tree in trees:
        if any(
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name
            for node in ast.walk(tree)
        ):
            sites.append(path)
    return tuple(sites)


def test_relocated_symbols_have_single_canonical_defining_modules_and_inert_facades() -> None:
    """Every completed relocation is reached through its defining module only."""
    for module_name, symbol_name in _CANONICAL_DEFINITIONS:
        module = importlib.import_module(module_name)
        symbol = getattr(module, symbol_name)
        assert symbol.__module__ == module_name
        assert _class_definition_sites(symbol_name) == (Path(module.__file__ or ""),)

    for namespace_name in _INERT_NAMESPACES:
        namespace = importlib.import_module(namespace_name)
        assert namespace.__all__ == ()
        source_path = Path(namespace.__file__ or "")
        imports = [
            target
            for target in _import_targets(source_path)
            if target != "__future__" and not target.startswith("from __future__")
        ]
        assert not imports, f"{namespace_name} is a forwarding facade: {imports}"


def test_manager_pilot_has_one_canonical_home_and_exactly_seven_direct_consumers() -> None:
    """The settling barrier lives in the TUI test package, not the old root."""
    old_home = _TUI_ROOT.parents[1] / "tests" / "manager_pilot.py"
    canonical_home = _TUI_ROOT / "tests" / "manager_pilot.py"
    assert not old_home.exists()
    assert canonical_home.is_file()

    expected_consumers = {
        "test_manager_field_editors.py",
        "test_manager_language_switch.py",
        "test_manager_masked_field_preservation.py",
        "test_manager_masked_required_field.py",
        "test_manager_required_field_refusal.py",
        "test_manager_screen.py",
        "test_visual_verification.py",
    }
    trees = _source_trees()
    expected_edges = tuple(
        sorted(
            (
                (
                    _repo_path(canonical_home.parent / consumer),
                    "from",
                    1,
                    "manager_pilot",
                    (("wait_until_settled", None),),
                )
                for consumer in expected_consumers
            ),
            key=repr,
        )
    )
    assert _manager_import_edges(trees) == expected_edges
    assert _function_definition_sites(trees, _MANAGER_SYMBOL) == (canonical_home,)

    tests_init = _TUI_ROOT / "tests" / "__init__.py"
    tests_init_tree = ast.parse(tests_init.read_text(encoding="utf-8"), filename=str(tests_init))
    assert not [
        node
        for node in ast.walk(tests_init_tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        and not (isinstance(node, ast.ImportFrom) and node.module == "__future__")
    ]
