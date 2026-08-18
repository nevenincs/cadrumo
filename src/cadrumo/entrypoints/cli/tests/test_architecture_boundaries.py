"""Static CLI architecture guards for modelo command decomposition.

The two cross-package private-import checks this module carried
(``test_extracted_modelo_cli_modules_do_not_import_private_application_modules``
and ``test_extracted_modelo_cli_modules_do_not_add_untracked_private_domain_imports``,
the latter's ``_PRIVATE_DOMAIN_IMPORT_EXCEPTIONS`` allowlist covering
``_modelo_iva_wallet_cli.py`` -> ``domain.iva_compensation._errors`` and
``_modelo_maritime_cli.py`` -> ``domain.renta._errors``) are superseded by the
project-wide ratcheting import-hygiene gate,
``src/cadrumo/tests/test_import_hygiene_gate.py`` (backed by
the import-hygiene scanner and its checked-in baseline).
Both former allowlist entries are
empty in practice at supersession time: neither modelo CLI module still
imports its domain package's private submodule (both now import the public
facade), and the general gate enforces the boundary for every production file
under ``src/cadrumo``, not just the modelo CLI surface. The remaining checks
below (legacy-root growth budgets, raw-id-regex placement, legacy-selector
reintroduction, centralized-addressing bypass) are modelo-CLI-decomposition-
specific structural rules, not import-hygiene duplicates, and remain this
module's own authority.

See Also:
    :func:`~tests._inventory.package_python_files`
        Shared source inventory used to enumerate focused modelo CLI modules.
    :func:`~tests._inventory.ast_for_path`
        Cached AST lookup used by the structural boundary scans.
    :mod:`~entrypoints.cli.tests.test_cli_module_size`
        Companion size-budget guard for CLI decomposition.

Modelo revision commands must stay thin transports over public application
facades, and every modelo command module must respect the CLI's
backend-boundary rule.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping
from pathlib import Path

import pytest

from ....tests import REPO_ROOT, ast_for_path, leaf_name, package_python_files

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_CLI_ROOT = REPO_ROOT / "src" / "cadrumo" / "entrypoints" / "cli"
_MODELO_MODULE_PREFIX = "_modelo"
_MODELO_LEGACY_ROOT = "_modelo.py"
_MODELO_PAYLOADS = "_modelo_payloads.py"
_MODELO_CLI_SUPPORT = "_modelo_cli_support.py"

_LEGACY_ROOT_PRIVATE_IMPORT_MODULES: set[str] = set()

_LEGACY_ROOT_REGISTRY_AUTHORITY_READ_BUDGET = 0
_LEGACY_ROOT_REGISTRY_QUERY_SERVICE_CALL_BUDGET = 0
_RAW_ID_REGEX_HELPERS = {_MODELO_CLI_SUPPORT}
_LEGACY_SELECTOR_HELPERS = {_MODELO_CLI_SUPPORT}
_LEGACY_SELECTOR_CALL_NAMES = {
    "find_latest_run_for_period",
    "get_calculation_revision",
    "get_work_unit",
    "resolve_modelo_calculation_revision_address",
    "resolve_modelo_work_address_unit",
    "workflow_period_for_work_unit",
}
_CENTRALIZED_ADDRESSING_FORBIDDEN_NAMES = {
    "ModeloWorkAddress",
    "parse_modelo_period",
    "resolve_exportable_modelo_calculation_revision_address",
    "resolve_fileable_modelo_calculation_revision_address",
    "resolve_modelo_calculation_revision_address",
    "resolve_modelo_work_address_unit",
    "resolve_verifiable_modelo_calculation_revision_address",
}


def _modelo_cli_modules() -> tuple[Path, ...]:
    modules = tuple(
        path
        for path in package_python_files()
        if path.parent == _CLI_ROOT and path.name.startswith(_MODELO_MODULE_PREFIX)
    )
    # Floor at the corpus source. Every structural guard below iterates this set
    # and asserts an offender list is empty; that green is meaningless if the set
    # is empty. A rename of the ``_modelo`` module prefix or a relocation of
    # ``_CLI_ROOT`` would empty the corpus and pass identically to a clean surface,
    # so the modelo-CLI decomposition would be unguarded and silent.
    assert len(modules) > 10, (
        f"discovered only {len(modules)} modelo CLI modules under {_CLI_ROOT}; the scan "
        "corpus collapsed (a prefix rename or package relocation), so an empty offender "
        "list below would mean 'nothing was checked' rather than 'nothing is wrong'"
    )
    return modules


def _production_modelo_cli_modules() -> tuple[Path, ...]:
    return tuple(path for path in _modelo_cli_modules() if path.name not in {_MODELO_LEGACY_ROOT, _MODELO_PAYLOADS})


def _tree_for_path(path: Path, source_tree_ast: Mapping[Path, ast.AST]) -> ast.AST:
    tree = ast_for_path(path, source_tree_ast)
    if tree is None:
        raise AssertionError(f"unable to parse {path.relative_to(REPO_ROOT).as_posix()}")
    return tree


def _import_from_modules(path: Path, source_tree_ast: Mapping[Path, ast.AST]) -> tuple[tuple[int, int, str], ...]:
    tree = _tree_for_path(path, source_tree_ast)
    modules: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.append((node.lineno, node.level, node.module))
    return tuple(modules)


def _normalized_module(level: int, module: str) -> str:
    if level >= 3:
        return module
    return module.removeprefix("cadrumo.")


def _private_backend_import_modules(path: Path, source_tree_ast: Mapping[Path, ast.AST]) -> tuple[str, ...]:
    modules: list[str] = []
    for _line_number, level, module in _import_from_modules(path, source_tree_ast):
        normalized = _normalized_module(level, module)
        is_private_application = normalized.startswith("application.") and "._" in normalized
        is_private_domain = normalized.startswith("domain.") and "._" in normalized
        if is_private_application or is_private_domain:
            modules.append(normalized)
    return tuple(sorted(modules))


def _registry_query_service_call_count(path: Path, source_tree_ast: Mapping[Path, ast.AST]) -> int:
    tree = _tree_for_path(path, source_tree_ast)
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "RegistryQueryService":
            count += 1
    return count


def _raw_id_regex_lines(path: Path, source_tree_ast: Mapping[Path, ast.AST]) -> tuple[int, ...]:
    tree = _tree_for_path(path, source_tree_ast)
    lines: list[int] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"compile", "fullmatch", "match"}
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "re"
        ):
            lines.append(node.lineno)
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and "[0-9a-f]" in node.value
            and ("{64}" in node.value or "{16}" in node.value)
        ):
            lines.append(node.lineno)
    return tuple(sorted(set(lines)))


def test_extracted_modelo_cli_modules_do_not_import_legacy_modelo_root(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """Extracted command modules must not depend on the monolithic root module."""
    offenders: list[str] = []
    for path in _production_modelo_cli_modules():
        for line_number, _level, module in _import_from_modules(path, source_tree_ast):
            if module == "_modelo":
                offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{line_number}")

    assert offenders == [], "extracted modelo modules import _modelo.py:\n  " + "\n  ".join(offenders)


def test_legacy_modelo_root_does_not_add_private_backend_imports(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """The legacy root may shrink private backend debt, but it must not grow it."""
    path = _CLI_ROOT / _MODELO_LEGACY_ROOT
    private_imports = set(_private_backend_import_modules(path, source_tree_ast))
    unexpected = sorted(private_imports - _LEGACY_ROOT_PRIVATE_IMPORT_MODULES)

    assert unexpected == [], "new private backend imports in _modelo.py:\n  " + "\n  ".join(unexpected)


def test_legacy_modelo_root_does_not_add_registry_authority_reads(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Registry authority reads must move out of the CLI root, not multiply."""
    path = _CLI_ROOT / _MODELO_LEGACY_ROOT
    text = path.read_text(encoding="utf-8")
    authority_reads = text.count("resources().modelos.authority")
    service_calls = _registry_query_service_call_count(path, source_tree_ast)

    assert authority_reads <= _LEGACY_ROOT_REGISTRY_AUTHORITY_READ_BUDGET
    assert service_calls <= _LEGACY_ROOT_REGISTRY_QUERY_SERVICE_CALL_BUDGET


def test_extracted_modelo_cli_modules_do_not_define_raw_id_regexes_outside_support(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """Raw exact-id shape checks belong in the shared CLI support helper."""
    offenders: list[str] = []
    for path in _production_modelo_cli_modules():
        if path.name in _RAW_ID_REGEX_HELPERS:
            continue
        for line_number in _raw_id_regex_lines(path, source_tree_ast):
            offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{line_number}")

    assert offenders == [], "modelo CLI modules define raw id regexes outside shared support:\n  " + "\n  ".join(
        offenders,
    )


def test_extracted_modelo_cli_modules_do_not_reintroduce_legacy_selector_calls(
    source_tree_ast: Mapping[Path, ast.AST],
) -> None:
    """Extracted command modules delegate work/revision selection to application facades."""
    offenders: list[str] = []
    for path in _production_modelo_cli_modules():
        if path.name in _LEGACY_SELECTOR_HELPERS:
            continue
        tree = _tree_for_path(path, source_tree_ast)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = leaf_name(node.func)
                if name in _LEGACY_SELECTOR_CALL_NAMES:
                    offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{node.lineno}: {name}")

    assert offenders == [], "modelo CLI modules reintroduced local selector policy:\n  " + "\n  ".join(offenders)


def test_modelo_cli_uses_centralized_operator_addressing_facades(source_tree_ast: Mapping[Path, ast.AST]) -> None:
    """Modelo CLI code must not rebuild work/revision addressing policy locally."""
    offenders: list[str] = []
    for path in _modelo_cli_modules():
        if path.name in {_MODELO_PAYLOADS, _MODELO_CLI_SUPPORT}:
            continue
        tree = _tree_for_path(path, source_tree_ast)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in _CENTRALIZED_ADDRESSING_FORBIDDEN_NAMES:
                        offenders.append(
                            f"{path.relative_to(REPO_ROOT).as_posix()}:{node.lineno}: import {alias.name}",
                        )
            if isinstance(node, ast.Call):
                name = leaf_name(node.func)
                if name in _CENTRALIZED_ADDRESSING_FORBIDDEN_NAMES:
                    offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{node.lineno}: {name}")

    assert offenders == [], "modelo CLI bypasses centralized operator-addressing facades:\n  " + "\n  ".join(offenders)
