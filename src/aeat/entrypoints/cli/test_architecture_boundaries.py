"""Static CLI architecture guards for modelo command decomposition."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ...core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_CLI_ROOT = PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli"
_MODELO_MODULE_PREFIX = "_modelo"
_MODELO_LEGACY_ROOT = "_modelo.py"
_MODELO_PAYLOADS = "_modelo_payloads.py"

_LEGACY_ROOT_PRIVATE_IMPORT_MODULES = {
    "domain.modelos._calculation_revision",
    "domain.modelos._filing_record",
    "domain.modelos._row_models",
    "domain.modelos._work_unit",
}

_LEGACY_ROOT_REGISTRY_AUTHORITY_READ_BUDGET = 0
_LEGACY_ROOT_REGISTRY_QUERY_SERVICE_CALL_BUDGET = 0

_PRIVATE_DOMAIN_IMPORT_EXCEPTIONS = {
    ("_modelo_iva_wallet_cli.py", "domain.iva_compensation._errors"),
    ("_modelo_maritime_cli.py", "domain.renta._errors"),
}


def _production_modelo_cli_modules() -> tuple[Path, ...]:
    return tuple(
        path
        for path in sorted(_CLI_ROOT.glob(f"{_MODELO_MODULE_PREFIX}*.py"))
        if path.name not in {_MODELO_LEGACY_ROOT, _MODELO_PAYLOADS}
    )


def _import_from_modules(path: Path) -> tuple[tuple[int, int, str], ...]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: list[tuple[int, int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.append((node.lineno, node.level, node.module))
    return tuple(modules)


def _normalized_module(level: int, module: str) -> str:
    if level >= 3:
        return module
    return module.removeprefix("aeat.")


def _private_backend_import_modules(path: Path) -> tuple[str, ...]:
    modules: list[str] = []
    for _line_number, level, module in _import_from_modules(path):
        normalized = _normalized_module(level, module)
        is_private_application = normalized.startswith("application.") and "._" in normalized
        is_private_domain = normalized.startswith("domain.") and "._" in normalized
        if is_private_application or is_private_domain:
            modules.append(normalized)
    return tuple(sorted(modules))


def _registry_query_service_call_count(path: Path) -> int:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "RegistryQueryService":
            count += 1
    return count


def test_extracted_modelo_cli_modules_do_not_import_legacy_modelo_root() -> None:
    """Extracted command modules must not depend on the monolithic root module."""
    offenders: list[str] = []
    for path in _production_modelo_cli_modules():
        for line_number, _level, module in _import_from_modules(path):
            if module == "_modelo":
                offenders.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}:{line_number}")

    assert offenders == [], "extracted modelo modules import _modelo.py:\n  " + "\n  ".join(offenders)


def test_legacy_modelo_root_does_not_add_private_backend_imports() -> None:
    """The legacy root may shrink private backend debt, but it must not grow it."""
    path = _CLI_ROOT / _MODELO_LEGACY_ROOT
    private_imports = set(_private_backend_import_modules(path))
    unexpected = sorted(private_imports - _LEGACY_ROOT_PRIVATE_IMPORT_MODULES)

    assert unexpected == [], "new private backend imports in _modelo.py:\n  " + "\n  ".join(unexpected)


def test_legacy_modelo_root_does_not_add_registry_authority_reads() -> None:
    """Registry authority reads must move out of the CLI root, not multiply."""
    path = _CLI_ROOT / _MODELO_LEGACY_ROOT
    text = path.read_text(encoding="utf-8")
    authority_reads = text.count("resources().modelos.authority")
    service_calls = _registry_query_service_call_count(path)

    assert authority_reads <= _LEGACY_ROOT_REGISTRY_AUTHORITY_READ_BUDGET
    assert service_calls <= _LEGACY_ROOT_REGISTRY_QUERY_SERVICE_CALL_BUDGET


def test_extracted_modelo_cli_modules_do_not_import_private_application_modules() -> None:
    """CLI modules consume application package facades, not private service files."""
    offenders: list[str] = []
    for path in _production_modelo_cli_modules():
        for line_number, level, module in _import_from_modules(path):
            if level >= 3 and module.startswith("application.") and "._" in module:
                offenders.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}:{line_number}: {module}")
            if module.startswith("aeat.application.") and "._" in module:
                offenders.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}:{line_number}: {module}")

    assert offenders == [], "modelo CLI modules bypass application facades:\n  " + "\n  ".join(offenders)


def test_extracted_modelo_cli_modules_do_not_add_untracked_private_domain_imports() -> None:
    """Private domain imports in extracted CLI modules must be explicit debt rows."""
    offenders: list[str] = []
    for path in _production_modelo_cli_modules():
        for line_number, level, module in _import_from_modules(path):
            is_relative_private_domain = level >= 3 and module.startswith("domain.") and "._" in module
            is_absolute_private_domain = module.startswith("aeat.domain.") and "._" in module
            if not (is_relative_private_domain or is_absolute_private_domain):
                continue
            normalized = module.removeprefix("aeat.")
            if (path.name, normalized) not in _PRIVATE_DOMAIN_IMPORT_EXCEPTIONS:
                offenders.append(f"{path.relative_to(PROJECT_ROOT).as_posix()}:{line_number}: {module}")

    assert offenders == [], "untracked private domain imports in modelo CLI modules:\n  " + "\n  ".join(offenders)
