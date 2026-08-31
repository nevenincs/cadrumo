"""Boundary tests for registry public imports and private module ownership.

The cross-package raw-registry-orchestration check this module carried
(``test_production_code_does_not_import_raw_registry_orchestration``, guarding
``build_snapshot`` / ``load_registry_tree``) is superseded by the
project-wide ratcheting import-hygiene gate,
``src/cadrumo/tests/test_import_hygiene_gate.py`` (backed by
the import-hygiene scanner and its checked-in baseline). Its
former allowlist
(``authority.py``, both package ``__init__.py`` files,
``_imputacion_parameters.py``, ``_recargo_equivalencia.py``) is now empty in
practice: none
of those sites still import the raw orchestration symbols cross-package, and
the general gate now enforces the boundary for every package, not just the
registry. The checks below (positive facade-content assertions and the
absolute-import / intra-package-test-boundary checks) are NOT import-hygiene
duplicates and remain the registry package's own authority.
"""

from __future__ import annotations

import ast
import importlib
from collections.abc import Mapping
from pathlib import Path

import pytest

from .....core.directory_scan import scan_directory
from .....tests import REPO_ROOT
from .._cross_revision_divergence import CrossRevisionCasillaDivergence
from ..formula_runtime_ops import resolve_keyed_bracket, resolve_parameter
from ..ledger_iva_bindings import (
    IvaLedgerObservation,
    resolve_ledger_iva_aggregation_binding_values,
    validate_ledger_iva_aggregation_binding_definition,
)
from ..ledger_oss_bindings import (
    OssIossLedgerObservation,
    resolve_ledger_oss_aggregation_binding_values,
    validate_ledger_oss_aggregation_binding_definition,
)
from ..runtime_graph import (
    expression_binding_refs,
    expression_casilla_refs,
    expression_date_binding_refs,
    expression_parameter_refs,
    expression_relation_refs,
)
from ..schema_surfaces import CasillaContinuidadEvolutionDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PRIVATE_REGISTRY_PREFIX = "cadrumo.domain.calculations.registry._"
_REGISTRY_SOURCE_ROOT = REPO_ROOT / "src" / "cadrumo"
_REGISTRY_TEST_ROOT = REPO_ROOT / "src" / "cadrumo" / "domain" / "calculations" / "registry"
_PROJECT_PYTHON_ROOTS = (REPO_ROOT / "src", REPO_ROOT / "dev")
_LEDGER_BINDING_PUBLIC_NAMES = (
    "IvaLedgerObservation",
    "OssIossLedgerObservation",
    "resolve_ledger_iva_aggregation_binding_values",
    "resolve_ledger_oss_aggregation_binding_values",
    "validate_ledger_iva_aggregation_binding_definition",
    "validate_ledger_oss_aggregation_binding_definition",
)
_CASILLA_CONTINUITY_PUBLIC_NAMES = (
    "CasillaContinuidadEvolutionDefinition",
    "CrossRevisionCasillaDivergence",
)
_MODELO_REGISTRY_PRIVATE_MODULES = ("_bindings", "_errors", "_record_design", "_schema")


def test_registry_ledger_binding_substrate_lives_in_its_defining_module() -> None:
    contracts = (
        IvaLedgerObservation,
        OssIossLedgerObservation,
        resolve_ledger_iva_aggregation_binding_values,
        resolve_ledger_oss_aggregation_binding_values,
        validate_ledger_iva_aggregation_binding_definition,
        validate_ledger_oss_aggregation_binding_definition,
    )

    assert tuple(contract.__name__ for contract in contracts) == _LEDGER_BINDING_PUBLIC_NAMES
    assert {contract.__module__ for contract in contracts} == {
        "cadrumo.domain.calculations.registry.ledger_iva_bindings",
        "cadrumo.domain.calculations.registry.ledger_oss_bindings",
    }


def test_registry_casilla_continuity_reports_live_in_their_defining_modules() -> None:
    contracts = (
        CasillaContinuidadEvolutionDefinition,
        CrossRevisionCasillaDivergence,
    )

    assert tuple(contract.__name__ for contract in contracts) == _CASILLA_CONTINUITY_PUBLIC_NAMES
    assert {contract.__module__ for contract in contracts} == {
        "cadrumo.domain.calculations.registry.schema_surfaces",
        "cadrumo.domain.calculations.registry._cross_revision_divergence",
    }


def test_registry_formula_reference_walkers_live_in_their_defining_module() -> None:
    walkers = (
        expression_binding_refs,
        expression_casilla_refs,
        expression_date_binding_refs,
        expression_parameter_refs,
        expression_relation_refs,
    )

    assert tuple(walker.__name__ for walker in walkers) == (
        "expression_binding_refs",
        "expression_casilla_refs",
        "expression_date_binding_refs",
        "expression_parameter_refs",
        "expression_relation_refs",
    )
    assert {walker.__module__ for walker in walkers} == {"cadrumo.domain.calculations.registry.runtime_graph"}


def test_registry_parameter_resolution_lives_in_its_defining_module() -> None:
    resolvers = (resolve_keyed_bracket, resolve_parameter)

    assert tuple(resolver.__name__ for resolver in resolvers) == ("resolve_keyed_bracket", "resolve_parameter")
    assert {resolver.__module__ for resolver in resolvers} == {
        "cadrumo.domain.calculations.registry.formula_runtime_ops"
    }


def test_registry_package_marker_is_inert() -> None:
    registry = importlib.import_module("cadrumo.domain.calculations.registry")

    assert registry.__all__ == []
    assert not any(hasattr(registry, name) for name in _LEDGER_BINDING_PUBLIC_NAMES)


def test_source_tree_does_not_use_absolute_registry_private_imports() -> None:
    offenders = sorted(
        f"{path.relative_to(REPO_ROOT)} imports {module_name}"
        for path in scan_directory(_REGISTRY_SOURCE_ROOT, pattern="*.py", recursive=True)
        for module_name in _absolute_registry_private_imports(path)
    )

    assert offenders == []


#: Paths this gate does not read, and why. The benchmark baseline is a frozen
#: copy of an earlier tree kept for comparison; it is not a consumer of today's
#: package and rewriting it would destroy the baseline it exists to be.
_FROZEN_BENCHMARK_SNAPSHOT = REPO_ROOT / "dev" / "benchmarks" / "cli" / ".baseline-source-snapshot"

#: The modules allowed to bind the package namespace, keyed by path with the
#: reason. Asserting a namespace exports nothing requires binding it, so a module
#: that PROVES the inertness cannot be read as consuming it.
#:
#: This table held ONE entry while four files bound the namespace, because the
#: matcher above could not see a relative import and so reported the other three
#: as clean. Every entry here states the same reason, which is the point: the
#: exemption is for proving inertness and for nothing else.
_INERTNESS_PROOF_REASON = (
    "Binds the package solely to assert that it exports nothing -- the inertness "
    "this gate exists to protect. There is no way to check that property without "
    "importing the namespace it is a property of."
)
_FACADE_BINDING_EXEMPTIONS: Mapping[str, str] = {
    "src/cadrumo/domain/calculations/registry/tests/test_aeat_nif_iva_oracle.py": _INERTNESS_PROOF_REASON,
    "src/cadrumo/domain/calculations/registry/tests/test_authority.py": _INERTNESS_PROOF_REASON,
    "src/cadrumo/domain/calculations/registry/tests/test_modelo_applicability.py": _INERTNESS_PROOF_REASON,
    "src/cadrumo/domain/calculations/registry/tests/test_remote_authority_canonicalisation.py": (
        _INERTNESS_PROOF_REASON
    ),
}


def test_project_consumers_do_not_import_the_inert_registry_package_facade() -> None:
    """Every project consumer must name a defining registry module directly."""
    offenders = sorted(
        f"{path.relative_to(REPO_ROOT)} imports the registry package facade"
        for root in _PROJECT_PYTHON_ROOTS
        for path in scan_directory(root, pattern="*.py", recursive=True)
        if not path.is_relative_to(_FROZEN_BENCHMARK_SNAPSHOT)
        and path.relative_to(REPO_ROOT).as_posix() not in _FACADE_BINDING_EXEMPTIONS
        and _imports_registry_package_facade(path)
    )

    assert offenders == []


def test_every_facade_binding_exemption_still_binds_the_facade() -> None:
    """An exemption that no longer describes a real binding is slack, not permission."""
    stale = sorted(
        relative
        for relative in _FACADE_BINDING_EXEMPTIONS
        if not _imports_registry_package_facade(REPO_ROOT / relative)
    )

    assert stale == [], f"exemption(s) no longer bind the package facade; remove them: {stale}"


def test_modelo_registry_tests_use_public_registry_api_boundaries() -> None:
    offenders = sorted(
        f"{path.name} imports .{module_name}"
        for path in scan_directory(_REGISTRY_TEST_ROOT, pattern="test_modelo_*_registry.py")
        for module_name in _relative_private_imports(path)
        if module_name in _MODELO_REGISTRY_PRIVATE_MODULES
    )

    assert offenders == []


def _absolute_registry_private_imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names if alias.name.startswith(_PRIVATE_REGISTRY_PREFIX))
            continue
        if (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and node.module is not None
            and node.module.startswith(_PRIVATE_REGISTRY_PREFIX)
        ):
            imports.append(node.module)
    return tuple(imports)


#: Dotted path of the inert package namespace this gate protects.
_REGISTRY_PACKAGE = "cadrumo.domain.calculations.registry"

#: Directory backing that package, read to tell a SUBMODULE import apart from a
#: facade-symbol import. ``from .. import export_parse`` names a module and is
#: the canonical way to reach one; ``from .. import parse_export_payload`` names
#: a symbol and is the re-export this gate forbids. Both are ``ImportFrom``
#: nodes resolving to the same package, so the names have to be classified.
_REGISTRY_PACKAGE_DIR = REPO_ROOT / "src" / "cadrumo" / "domain" / "calculations" / "registry"


def _registry_submodule_names() -> frozenset[str]:
    return frozenset(
        {path.stem for path in _REGISTRY_PACKAGE_DIR.glob("*.py") if path.stem != "__init__"}
        | {path.name for path in _REGISTRY_PACKAGE_DIR.iterdir() if path.is_dir()},
    )


def _dotted_package(path: Path) -> tuple[str, ...]:
    """Return the dotted package a source file lives in, or empty when unresolvable.

    Relative imports resolve against the IMPORTING module's package, so a check
    that skips ``node.level > 0`` cannot see a relative facade binding at all.
    That was this gate's blind spot: every real binding in the tree is spelled
    ``from ... import registry``, so the absolute-only matcher reported zero
    offenders while four files bound the namespace, and the paired
    exemption-liveness check then read its one entry as stale.
    """
    source_root = REPO_ROOT / "src"
    if not path.is_relative_to(source_root):
        return ()
    parts = list(path.relative_to(source_root).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        return tuple(parts[:-1])
    return tuple(parts[:-1])


def _imports_registry_package_facade(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    package = _dotted_package(path)
    submodules = _registry_submodule_names()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == _REGISTRY_PACKAGE for alias in node.names):
                return True
            continue
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level == 0:
            base = tuple(node.module.split(".")) if node.module else ()
            resolved = node.module or ""
        else:
            if not package:
                continue
            base = package[: len(package) - (node.level - 1)]
            resolved = ".".join((*base, node.module)) if node.module else ".".join(base)
        if resolved == _REGISTRY_PACKAGE:
            # Reaching THROUGH the namespace for one of its own modules is the
            # canonical path; reaching for a bare symbol is the re-export.
            if any(alias.name not in submodules for alias in node.names):
                return True
            continue
        if node.module is None and any(".".join((*base, alias.name)) == _REGISTRY_PACKAGE for alias in node.names):
            return True
    return False


def _relative_private_imports(path: Path) -> tuple[str, ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return tuple(
        node.module
        for node in ast.walk(tree)
        if (
            isinstance(node, ast.ImportFrom)
            and node.level == 1
            and node.module is not None
            and node.module.startswith("_")
        )
    )


def _locally_bound_names(tree: ast.Module) -> set[str]:
    """Every name a module binds itself, imports excluded.

    ``ast.TypeAlias`` carries PEP 695 ``type X = ...`` statements. Omitting it
    reports a locally defined alias as borrowed, which manufactures findings.
    """
    bound: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            bound.add(node.name)
        elif isinstance(node, ast.Assign):
            bound.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            bound.add(node.target.id)
        elif isinstance(node, ast.TypeAlias) and isinstance(node.name, ast.Name):
            bound.add(node.name.id)
    return bound


def _declared_exports(tree: ast.Module) -> list[str] | None:
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and any(getattr(t, "id", "") == "__all__" for t in node.targets)
            and isinstance(node.value, ast.List | ast.Tuple)
        ):
            return [e.value for e in node.value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
    return None


def test_no_registry_module_exports_a_symbol_it_does_not_define() -> None:
    """A module's public surface is its own contract, never a borrowed one.

    Re-exporting another module's symbol makes two import paths for one name,
    so a consumer can bind to a module that merely forwards it. The owner is
    then free to move while the forwarder still resolves, and the boundary the
    export list appears to describe is not the one imports actually cross.
    """
    modules = sorted(p for p in _REGISTRY_TEST_ROOT.glob("*.py") if p.name != "__init__.py")
    assert len(modules) > 50, f"registry module sweep collapsed to {len(modules)} files"

    borrowed: dict[str, list[str]] = {}
    for path in modules:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        exports = _declared_exports(tree)
        if exports is None:
            continue
        bound = _locally_bound_names(tree)
        if outside := sorted(name for name in exports if name not in bound):
            borrowed[path.name] = outside

    assert borrowed == {}, f"registry modules exporting borrowed symbols: {borrowed}"
