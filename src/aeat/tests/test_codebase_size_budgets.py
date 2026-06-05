"""Codebase-wide module and callable size ratchets."""

from __future__ import annotations

import ast
import shutil
import subprocess
from pathlib import Path

import pytest

from ..core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DEFAULT_MODULE_LINE_LIMIT = 1250
_DEFAULT_CALLABLE_LINE_LIMIT = 180

_LEGACY_MODULE_LINE_BUDGETS = {
    "src/aeat/adapters/inbound/declaracion/tests/test_parser_boundary.py": 2079,
    "src/aeat/adapters/inbound/declaracion/tests/test_verification_chain.py": 2374,
    "src/aeat/adapters/outbound/aeat/auth/_authenticator.py": 1437,
    "src/aeat/adapters/outbound/aeat/auth/_clave_movil.py": 1719,
    "src/aeat/adapters/outbound/aeat/auth/tests/test_authenticator.py": 1356,
    "src/aeat/adapters/outbound/aeat/sede/_declarations.py": 2134,
    "src/aeat/adapters/outbound/aeat/sede/tests/test_declarations.py": 1848,
    "src/aeat/adapters/outbound/google/_calc_sheets_apply.py": 1294,
    "src/aeat/adapters/persistence/storage/master_key/_master_key.py": 1757,
    "src/aeat/adapters/persistence/storage/sql/secure_objects.py": 1667,
    "src/aeat/adapters/persistence/storage/sql/tests/test_secure_objects.py": 2045,
    "src/aeat/adapters/persistence/storage/tests/test_runtime_migrated_repositories.py": 1265,
    "src/aeat/application/ledger/tests/test_actions.py": 2514,
    "src/aeat/application/auth/_operator.py": 1400,
    "src/aeat/application/live/__init__.py": 1892,
    "src/aeat/application/modelo/tests/test_file_flow.py": 2109,
    "src/aeat/application/overview/__init__.py": 1461,
    "src/aeat/application/overview/tests/test_calendar.py": 1458,
    "src/aeat/application/workflow/_engine.py": 1289,
    "src/aeat/core/config.py": 1478,
    "src/aeat/core/errors/registry/_adapters.py": 1295,
    "src/aeat/core/errors/registry/_application.py": 1419,
    "src/aeat/core/errors/registry/_domain.py": 2318,
    "src/aeat/domain/calculations/registry/_applicability.py": 1454,
    "src/aeat/domain/calculations/registry/_bindings.py": 2708,
    "src/aeat/domain/calculations/registry/_record_design.py": 1781,
    "src/aeat/domain/calculations/registry/_schema.py": 2584,
    "src/aeat/domain/calculations/registry/_workbook_parity.py": 1336,
    "src/aeat/domain/calculations/registry/tests/test_referential_integrity.py": 1387,
    "src/aeat/domain/calculations/registry/tests/test_registry_schema.py": 1565,
    "src/aeat/tests/fixtures/justificantes/_generate.py": 3091,
}

_LEGACY_CALLABLE_LINE_BUDGETS = {
    ("src/aeat/adapters/outbound/aeat/auth/_clave_movil.py", "_fresh_login_locked"): 184,
    ("src/aeat/adapters/outbound/google/_calc_sheets_apply.py", "apply_export_plan"): 222,
    ("src/aeat/application/ledger/_actions_split_merge.py", "merge_transactions"): 221,
    ("src/aeat/application/modelo/_export.py", "export_modelo_revision"): 194,
    ("src/aeat/application/overview/__init__.py", "build_overview_calendar"): 189,
    ("src/aeat/core/observability/_context.py", "run_context"): 188,
    ("src/aeat/domain/calculations/registry/_validate_revision_sections.py", "validate_revision_definition"): 196,
    ("src/aeat/domain/iva_compensation/_reconciliation.py", "reconcile_iva_compensation_wallet"): 270,
    ("src/aeat/entrypoints/cli/_config/_profile_bundle.py", "register_profile_bundle_commands"): 221,
    ("src/aeat/entrypoints/cli/_config/_repair_cli.py", "register_repair_maintenance_commands"): 279,
    ("src/aeat/entrypoints/cli/_ledger.py", "ledger_classify"): 194,
    ("src/aeat/entrypoints/cli/_ledger_evidence_cli.py", "register_evidence_commands"): 206,
    ("src/aeat/entrypoints/cli/_ledger_read_cli.py", "register_read_commands"): 538,
    ("src/aeat/entrypoints/cli/_modelo_iva_wallet_cli.py", "register_iva_wallet_commands"): 199,
    ("src/aeat/entrypoints/cli/_modelo_projection_cli.py", "register_projection_commands"): 243,
}


def _tracked_python_files() -> tuple[Path, ...]:
    git_executable = shutil.which("git")
    assert git_executable is not None, "git executable is required for tracked-file inventory"
    result = subprocess.run(  # noqa
        [git_executable, "ls-files", "-z", "src/aeat"],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
    )
    paths = tuple(Path(raw.decode("utf-8")) for raw in result.stdout.split(b"\0") if raw)
    return tuple(PROJECT_ROOT / path for path in paths if path.suffix == ".py" and (PROJECT_ROOT / path).exists())


def _relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def test_tracked_python_modules_do_not_exceed_line_budgets() -> None:
    offenders: list[str] = []
    for path in _tracked_python_files():
        relative = _relative(path)
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        budget = _LEGACY_MODULE_LINE_BUDGETS.get(relative, _DEFAULT_MODULE_LINE_LIMIT)
        if line_count > budget:
            offenders.append(f"{relative}: {line_count} lines > budget {budget}")

    assert offenders == [], "Python module size budget exceeded:\n  " + "\n  ".join(offenders)


def test_tracked_production_callables_do_not_exceed_line_budgets() -> None:
    offenders: list[str] = []
    for path in _tracked_python_files():
        relative = _relative(path)
        if "/tests/" in relative:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                continue
            if node.end_lineno is None:
                continue
            line_count = node.end_lineno - node.lineno + 1
            budget = _LEGACY_CALLABLE_LINE_BUDGETS.get((relative, node.name), _DEFAULT_CALLABLE_LINE_LIMIT)
            if line_count > budget:
                offenders.append(f"{relative}:{node.name}: {line_count} lines > budget {budget}")

    assert offenders == [], "Python callable size budget exceeded:\n  " + "\n  ".join(offenders)
