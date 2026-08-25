"""Ownership and cutover proofs for the wizard package surface."""

from __future__ import annotations

import ast
import inspect
import subprocess
from importlib import import_module
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PACKAGE_ROOT = Path(__file__).parents[1]
_REPOSITORY_ROOT = _PACKAGE_ROOT.parents[3]

_PUBLIC_MODULE_NAMES = (
    "catalogue",
    "commands",
    "compiler",
    "copy_sources",
    "descendant_door",
    "descendant_group",
    "errors",
    "flow_validators",
    "legal_zone",
    "models",
    "persistence",
    "results",
    "setup_legal_validators",
    "status",
    "widgets",
)
_INTERNAL_MODULE_NAMES = (
    "_checkpoint_store",
    "_format_hints",
    "_registered_values",
    "_translations",
)
_MOVED_MODULE_NAMES = (
    "catalogue",
    "commands",
    "compiler",
    "copy_sources",
    "descendant_group",
    "errors",
    "flow_validators",
    "legal_zone",
    "models",
    "persistence",
    "results",
    "setup_legal_validators",
    "status",
    "widgets",
)


def _imported_names(module: ModuleType) -> frozenset[str]:
    """Return identifiers imported into ``module`` by its source file."""
    source_path = Path(module.__file__ or "")
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
    return frozenset(names)


def _locally_bound_names(module: ModuleType) -> frozenset[str]:
    """Return names authored at module scope, excluding imported bindings."""
    source_path = Path(module.__file__ or "")
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
    return frozenset(names)


def _source_and_doc_files() -> tuple[Path, ...]:
    """Return cutover-owned source/docs, excluding generated CLI census output."""
    suffixes = {".py", ".rst", ".md", ".json", ".toml"}
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "src", "dev", "docs"],  # noqa: S607 - read-only repository inventory
        cwd=_REPOSITORY_ROOT,
        capture_output=True,
        check=False,
    )
    if result.returncode == 0 and result.stdout:
        tracked = {
            _REPOSITORY_ROOT / relative
            for relative in result.stdout.decode().split("\0")
            if relative
        }
        # Include untracked cutover files in the shared worktree while keeping
        # the expensive fallback for environments that do not carry a .git dir.
        tracked.update(
            path
            for root in (_PACKAGE_ROOT, _REPOSITORY_ROOT / "docs" / "api")
            for path in root.rglob("*")
            if path.is_file()
        )
        return tuple(
            path
            for path in tracked
            if path.exists()
            and "__pycache__" not in path.parts
            and "benchmarks" not in path.parts
            and path.suffix in suffixes
        )

    paths: list[Path] = []
    for root in (_REPOSITORY_ROOT / "src", _REPOSITORY_ROOT / "dev", _REPOSITORY_ROOT / "docs"):
        paths.extend(
            path
            for path in root.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and "benchmarks" not in path.parts
            and path.suffix in suffixes
        )
    return tuple(paths)


def test_wizard_module_inventory_is_complete_and_namespace_is_inert() -> None:
    """Every module is classified, and the package cannot act as a facade."""
    actual = {path.stem for path in _PACKAGE_ROOT.glob("*.py") if path.name != "__init__.py"}
    assert actual == set(_PUBLIC_MODULE_NAMES) | set(_INTERNAL_MODULE_NAMES)

    initializer = ast.parse((_PACKAGE_ROOT / "__init__.py").read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        for node in initializer.body
    )
    assert initializer.body[-1].target.id == "__all__"
    assert ast.literal_eval(initializer.body[-1].value) == []


@pytest.mark.parametrize("module_name", _PUBLIC_MODULE_NAMES)
def test_every_public_wizard_export_is_owned_by_its_defining_module(module_name: str) -> None:
    """Public exports are local definitions, never facade aliases."""
    module = import_module(f"cadrumo.application.wizard.{module_name}")
    exported = tuple(module.__all__)
    assert exported
    assert len(exported) == len(set(exported))
    assert [name for name in exported if name not in vars(module)] == []
    assert sorted(set(exported) & _imported_names(module)) == []
    assert sorted(set(exported) - _locally_bound_names(module)) == []

    foreign_runtime_exports = {
        name: getattr(getattr(module, name), "__module__", None)
        for name in exported
        if (isinstance(value := getattr(module, name), type) or inspect.isroutine(value))
        and getattr(value, "__module__", None) != module.__name__
    }
    assert foreign_runtime_exports == {}


def test_hard_moved_modules_and_old_import_paths_have_no_remnants() -> None:
    """Moved private module paths cannot remain in source or documentation."""
    for module_name in _MOVED_MODULE_NAMES:
        assert not (_PACKAGE_ROOT / f"_{module_name}.py").exists()

    old_paths = tuple(f"cadrumo.application.wizard._{name}" for name in _MOVED_MODULE_NAMES)
    remnants: dict[str, tuple[str, ...]] = {}
    for path in _source_and_doc_files():
        text = path.read_text(encoding="utf-8")
        matches = tuple(old_path for old_path in old_paths if old_path in text)
        if matches:
            remnants[str(path.relative_to(_REPOSITORY_ROOT))] = matches
    assert remnants == {}


def test_private_wizard_leaves_have_no_cross_package_python_consumers() -> None:
    """The four retained private leaves are consumed only inside wizard."""
    private_paths = tuple(f"wizard.{name}" for name in _INTERNAL_MODULE_NAMES)
    external_python = (
        path
        for path in _source_and_doc_files()
        if path.suffix == ".py" and _PACKAGE_ROOT not in path.parents and path != _PACKAGE_ROOT
    )
    references: dict[str, tuple[str, ...]] = {}
    for path in external_python:
        text = path.read_text(encoding="utf-8")
        matches = tuple(private_path for private_path in private_paths if private_path in text)
        if matches:
            references[str(path.relative_to(_REPOSITORY_ROOT))] = matches
    assert references == {}
