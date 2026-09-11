"""Forbid imports that would restore retired governed-fact authority paths."""

from __future__ import annotations

import ast
import tomllib
from collections.abc import Iterable, Mapping
from functools import cache
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..import_hygiene_scan import module_name_for, resolve_relative_import

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_EXTERNAL_CONSTANTS_LEDGER = REPO_ROOT / "dev" / "registry" / "analysis" / "facts_external_constants_retirement.toml"
_RETIRED_MODULES = frozenset(
    {
        "cadrumo.core.resources._repos.iva_rate_tables",
        "dev.registry.compiler.categories",
        "dev.registry.compiler.holidays",
        "dev.registry.compiler.iva",
    },
)
_RETIRED_SYMBOLS_BY_MODULE = {
    "dev.registry.compiler.convenio": frozenset(
        {
            "collect_convenio_fingerprints",
            "compile_convenio_facts",
            "load_convenio_authority",
            "validate_convenio_legal_refs",
        },
    ),
}


@cache
def _retired_symbols_by_module() -> dict[str, frozenset[str]]:
    """Return the complete retired-declaration set from its canonical ledger."""
    ledger = tomllib.loads(_EXTERNAL_CONSTANTS_LEDGER.read_text(encoding="utf-8"))
    retired_constants = frozenset(ledger["retired_statutory_symbols"]) | frozenset(ledger["retired_routing_symbols"])
    return {**_RETIRED_SYMBOLS_BY_MODULE, "cadrumo.core.external_constants": retired_constants}


def _module_for_import_alias(target_module: str, imported_name: str) -> str | None:
    """Return a retired child module addressed through its parent, if any."""
    candidate = f"{target_module}.{imported_name}"
    return candidate if _is_retired_module(candidate) else None


def _is_retired_module(module: str) -> bool:
    """Return whether *module* is a retired module or one of its descendants."""
    return any(module == retired or module.startswith(f"{retired}.") for retired in _RETIRED_MODULES)


def _attribute_path(node: ast.Attribute) -> str | None:
    """Return a dotted attribute path when its root is a simple name."""
    parts: list[str] = [node.attr]
    value: ast.expr = node.value
    while isinstance(value, ast.Attribute):
        parts.append(value.attr)
        value = value.value
    if not isinstance(value, ast.Name):
        return None
    parts.append(value.id)
    return ".".join(reversed(parts))


def _literal_string(node: ast.AST) -> str | None:
    """Return a source literal without treating a computed string as declared intent."""
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def _module_expression(node: ast.AST, module_aliases: Mapping[str, str]) -> str | None:
    """Resolve a directly named or imported-alias module expression."""
    if isinstance(node, ast.Name):
        return module_aliases.get(node.id)
    if isinstance(node, ast.Attribute):
        return _attribute_path(node)
    return None


def _names_retirement_surface(module: str, retired_symbols: Mapping[str, frozenset[str]]) -> bool:
    """Return whether a module is retired or is an ancestor of a retired surface."""
    return (
        _is_retired_module(module)
        or module in retired_symbols
        or any(retired.startswith(f"{module}.") for retired in (*_RETIRED_MODULES, *retired_symbols))
    )


def _import_violations(tree: ast.Module, *, importer_module: str, importer_is_package: bool) -> tuple[str, ...]:
    """Return retired authority paths imported or reached by one module."""
    retired_symbols = _retired_symbols_by_module()
    findings: set[str] = set()
    module_aliases: dict[str, str] = {}
    importlib_aliases: set[str] = set()
    import_module_names: set[str] = set()
    builtin_import_names: set[str] = {"__import__"}
    builtins_aliases: set[str] = set()
    getattr_names: set[str] = {"getattr"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_retired_module(alias.name):
                    findings.add(f"{node.lineno}: retired module {alias.name}")
                if alias.name in retired_symbols and alias.asname is not None:
                    module_aliases[alias.asname] = alias.name
                if alias.asname is not None and _names_retirement_surface(alias.name, retired_symbols):
                    module_aliases[alias.asname] = alias.name
                if alias.name == "importlib" or (alias.asname is None and alias.name.startswith("importlib.")):
                    importlib_aliases.add(alias.asname or "importlib")
                if alias.name == "builtins" or (alias.asname is None and alias.name.startswith("builtins.")):
                    builtins_aliases.add(alias.asname or "builtins")
        elif isinstance(node, ast.ImportFrom):
            target = resolve_relative_import(importer_module, importer_is_package, node.level, node.module)
            if target is None:
                continue
            if _is_retired_module(target):
                findings.add(f"{node.lineno}: retired module {target}")
            for alias in node.names:
                retired_child = _module_for_import_alias(target, alias.name)
                if retired_child is not None:
                    findings.add(f"{node.lineno}: retired module {retired_child}")
                if alias.name in retired_symbols.get(target, frozenset()):
                    findings.add(f"{node.lineno}: retired symbol {target}.{alias.name}")
                candidate_module = f"{target}.{alias.name}"
                if _names_retirement_surface(candidate_module, retired_symbols):
                    module_aliases[alias.asname or alias.name] = candidate_module
                if target in retired_symbols and alias.name == "*":
                    findings.add(f"{node.lineno}: retired symbol wildcard import {target}")
                if target == "importlib" and alias.name == "import_module":
                    import_module_names.add(alias.asname or alias.name)
                if target == "builtins" and alias.name == "__import__":
                    builtin_import_names.add(alias.asname or alias.name)
                if target == "builtins" and alias.name == "getattr":
                    getattr_names.add(alias.asname or alias.name)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        path = _attribute_path(node)
        if path is None:
            continue
        for module, symbols in retired_symbols.items():
            resolved = path
            for alias, alias_module in module_aliases.items():
                if path == alias or path.startswith(f"{alias}."):
                    resolved = f"{alias_module}{path.removeprefix(alias)}"
                    break
            if _is_retired_module(resolved):
                findings.add(f"{node.lineno}: retired module {resolved}")
            for symbol in symbols:
                if resolved == f"{module}.{symbol}":
                    findings.add(f"{node.lineno}: retired symbol {module}.{symbol}")

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        is_import_module = (isinstance(node.func, ast.Name) and node.func.id in import_module_names) or (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in importlib_aliases
            and node.func.attr == "import_module"
        )
        is_builtin_import = (isinstance(node.func, ast.Name) and node.func.id in builtin_import_names) or (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in builtins_aliases
            and node.func.attr == "__import__"
        )
        if is_import_module or is_builtin_import:
            target = _literal_string(node.args[0]) if node.args else None
            if target is not None and _is_retired_module(target):
                findings.add(f"{node.lineno}: retired module {target}")
        is_getattr = (isinstance(node.func, ast.Name) and node.func.id in getattr_names) or (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in builtins_aliases
            and node.func.attr == "getattr"
        )
        if is_getattr and len(node.args) >= 2:
            module = _module_expression(node.args[0], module_aliases)
            symbol = _literal_string(node.args[1])
            if module is not None and symbol in retired_symbols.get(module, frozenset()):
                findings.add(f"{node.lineno}: retired symbol {module}.{symbol}")
    return tuple(sorted(findings))


def _source_modules() -> Iterable[tuple[Path, str, bool]]:
    """Yield every source and development Python module with its import identity."""
    for root, module_root in ((REPO_ROOT / "src", REPO_ROOT / "src"), (REPO_ROOT / "dev", REPO_ROOT)):
        for path in root.rglob("*.py"):
            yield path, module_name_for(path, src_root=module_root), path.name == "__init__.py"


def test_no_source_or_development_module_imports_a_retired_fact_authority_path() -> None:
    """The campaign's retired import paths cannot reappear anywhere in the repository."""
    unread: list[str] = []
    violations: list[str] = []
    for path, module, is_package in _source_modules():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError, UnicodeDecodeError) as exc:
            unread.append(f"{path.relative_to(REPO_ROOT).as_posix()}: {exc}")
            continue
        violations.extend(
            f"{path.relative_to(REPO_ROOT).as_posix()}: {finding}"
            for finding in _import_violations(tree, importer_module=module, importer_is_package=is_package)
        )

    assert unread == [], "the retirement import census could not parse: " + "; ".join(sorted(unread))
    assert violations == [], "retired governed-fact imports remain: " + "; ".join(sorted(violations))


def test_detector_rejects_module_symbol_attribute_and_relative_import_revivals() -> None:
    """A representative resurrection of every retirement form is detected."""
    fixture = ast.parse(
        "import dev.registry.compiler.iva\n"
        "from dev.registry.compiler import categories\n"
        "from dev.registry.compiler.holidays import compile_holiday_calendar_facts\n"
        "from cadrumo.core.resources._repos.iva_rate_tables import IvaRateTableRepository\n"
        "from dev.registry.compiler.convenio import compile_convenio_facts\n"
        "import dev.registry.compiler.convenio as convenio\n"
        "convenio.load_convenio_authority(root)\n"
        "import dev.registry.compiler as compiler\n"
        "compiler.iva.recreated()\n"
        "from dev.registry.compiler.convenio import *\n"
        "from cadrumo.core import external_constants\n"
        "external_constants.M347_THRESHOLD_EUR\n"
        "import cadrumo.core.external_constants\n"
        "cadrumo.core.external_constants.M347_THRESHOLD_EUR\n"
        "import importlib\n"
        "importlib.import_module('dev.registry.compiler.iva.recreated')\n"
        "__import__('dev.registry.compiler.holidays.recreated')\n"
        "getattr(convenio, 'collect_convenio_fingerprints')\n"
        "import builtins\n"
        "builtins.__import__('cadrumo.core.resources._repos.iva_rate_tables.recreated')\n"
        "builtins.getattr(convenio, 'validate_convenio_legal_refs')\n"
    )
    relative = ast.parse("from . import iva\n")

    findings = _import_violations(fixture, importer_module="dev.registry.compiler.authority", importer_is_package=False)
    relative_findings = _import_violations(
        relative,
        importer_module="dev.registry.compiler.authority",
        importer_is_package=False,
    )

    assert {
        "retired module dev.registry.compiler.iva",
        "retired module dev.registry.compiler.categories",
        "retired module dev.registry.compiler.holidays",
        "retired module cadrumo.core.resources._repos.iva_rate_tables",
        "retired symbol dev.registry.compiler.convenio.compile_convenio_facts",
        "retired symbol dev.registry.compiler.convenio.load_convenio_authority",
        "retired symbol cadrumo.core.external_constants.M347_THRESHOLD_EUR",
        "retired module dev.registry.compiler.iva.recreated",
        "retired module dev.registry.compiler.holidays.recreated",
        "retired symbol dev.registry.compiler.convenio.collect_convenio_fingerprints",
        "retired module cadrumo.core.resources._repos.iva_rate_tables.recreated",
        "retired symbol dev.registry.compiler.convenio.validate_convenio_legal_refs",
        "retired symbol wildcard import dev.registry.compiler.convenio",
    }.issubset(set(finding.split(": ", 1)[1] for finding in (*findings, *relative_findings)))


def test_detector_allows_canonical_fact_projections_and_pending_iva_grounding() -> None:
    """The gate does not treat canonical replacements or explicitly pending work as retired."""
    tree = ast.parse(
        "from cadrumo.domain.iva.rates import load_iva_rate_table\n"
        "from cadrumo.domain.iva._grounding import verify_table_legal_refs\n"
        "from dev.registry.compiler.convenio import convenio_authority_from_facts\n"
        "from cadrumo.core.external_constants import UTF_8_ENCODING\n"
        "import importlib\n"
        "importlib.import_module('cadrumo.domain.iva._grounding')\n"
        "import dev.registry.compiler.convenio as convenio\n"
        "getattr(convenio, 'convenio_authority_from_facts')\n"
    )

    assert _import_violations(tree, importer_module="dev.registry.compiler.authority", importer_is_package=False) == ()
