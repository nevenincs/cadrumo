"""Ownership proofs for every public user-profile defining module."""

from __future__ import annotations

import ast
import inspect
from importlib import import_module
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PACKAGE_ROOT = Path(__file__).parents[1]
_PUBLIC_MODULE_NAMES = (
    "acquisition_sources",
    "aggregate",
    "authentication",
    "bundle",
    "bundle_encryption",
    "bundle_export",
    "bundle_export_contracts",
    "bundle_export_operation",
    "capabilities",
    "capsule_archive",
    "capsule_record",
    "capsule_restore",
    "censal_observation",
    "censal_operation",
    "censo_errors",
    "censo_sync",
    "commands",
    "completeness",
    "cotejo_apply",
    "custody_carry",
    "custody_hold",
    "custody_hold_models",
    "custody_ports",
    "custody_repository",
    "custody_service",
    "custody_transactions",
    "fact_write",
    "filing_baseline",
    "keys_validation",
    "language_resolver",
    "lifecycle",
    "login_interaction",
    "login_session",
    "login_session_port",
    "operations",
    "overview",
    "passphrase_rotation",
    "preflight",
    "presentation",
    "profile_pointer",
    "profile_pointer_ports",
    "profile_record_repository",
    "profile_repository",
    "profile_summary",
    "projections",
    "prospective_password",
    "recovery_contracts",
    "recovery_custody",
    "registration",
    "repository",
    "section_rows",
    "status_projection",
    "usage_ratio_resolution",
    "validation",
)
_PUBLIC_DEFINING_MODULES: tuple[ModuleType, ...] = tuple(
    import_module(f"cadrumo.application.user_profile.{name}") for name in _PUBLIC_MODULE_NAMES
)


def _imported_names(module: ModuleType) -> frozenset[str]:
    """Return every identifier imported by a public defining module."""
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
    """Return names whose public binding is authored in this module."""
    source_path = Path(module.__file__ or "")
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.TypeAlias):
            if isinstance(node.name, ast.Name):
                names.add(node.name.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, ast.Assign):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
    return frozenset(names)


def test_public_module_inventory_is_complete_and_the_package_namespace_is_inert() -> None:
    """A public module cannot be added without a defining-identity proof."""
    actual = {path.stem for path in _PACKAGE_ROOT.glob("*.py") if path.name != "__init__.py"}
    assert actual == set(_PUBLIC_MODULE_NAMES)

    initializer = ast.parse((_PACKAGE_ROOT / "__init__.py").read_text(encoding="utf-8"))
    assert not any(
        isinstance(node, ast.Import | ast.ImportFrom | ast.FunctionDef | ast.AsyncFunctionDef)
        for node in initializer.body
    )


@pytest.mark.parametrize("module", _PUBLIC_DEFINING_MODULES, ids=lambda module: module.__name__)
def test_every_public_user_profile_export_is_owned_by_its_defining_module(module: ModuleType) -> None:
    """Exports are defined here, never imported, aliased, or re-exported."""
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
