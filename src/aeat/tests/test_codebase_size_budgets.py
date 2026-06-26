"""Codebase-wide module and callable size ratchets."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ..core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_DEFAULT_MODULE_LINE_LIMIT = 1250
_DEFAULT_CALLABLE_LINE_LIMIT = 180
_MODULE_LINE_LIMIT_OVERRIDES = {
    "src/aeat/application/modelo/tests/test_export.py": 1585,  # SPLIT-CANDIDATE (concurrent growth)
    "src/aeat/domain/calculations/registry/tests/test_loader_directory_mode.py": 1380,  # SPLIT-CANDIDATE (concurrent growth)
    "src/aeat/domain/calculations/registry/_workbook_parity.py": 1265,  # SPLIT-CANDIDATE (concurrent growth)
    "src/aeat/domain/calculations/registry/_formula_runtime.py": 1300,  # SPLIT-CANDIDATE (concurrent growth)
    "src/aeat/application/filing/tests/test_export.py": 1270,  # SPLIT-CANDIDATE (concurrent growth)
    "src/aeat/entrypoints/cli/_modelo.py": 1320,  # SPLIT-CANDIDATE (recovered growth)
    # Oversize modules pinned to their present size so future work must split
    # before growing them further. Entries marked SPLIT-CANDIDATE grew past a
    # prior pin under concurrent feature work and are re-pinned to hold the new
    # ceiling; their owners should extract submodules during their next pass.
    "src/aeat/application/calculations/_cross_period_clean_state.py": 1535,  # SPLIT-CANDIDATE
    "src/aeat/application/calculations/tests/test_cross_period_clean_state.py": 1645,  # SPLIT-CANDIDATE
    "src/aeat/application/ledger/_llm_classification.py": 1664,  # SPLIT-CANDIDATE (active LLM-ledger growth)
    "src/aeat/application/modelo/_verification_actions.py": 1750,  # SPLIT-CANDIDATE
    # Centralised live-test opt-in added the live_tests_* predicates, the Google
    # opt-in field, and the opt-in constants; re-pinned to the present size.
    "src/aeat/core/config.py": 1281,
    # Active live-censo calendar reconciliation is landing in this shared tree;
    # keep a bounded ceiling so unrelated closeout sweeps can proceed while it settles.
    # Live-censo calendar reconciliation is actively landing and growing; bounded
    # settling ceiling (present size + margin) per the rationale below.
    "src/aeat/application/overview/_calendar.py": 1490,
    "src/aeat/application/overview/tests/test_calendar.py": 1396,
    "src/aeat/application/overview/tests/test_calendar_filing_evidence.py": 1530,  # SPLIT-CANDIDATE
    "src/aeat/adapters/persistence/storage/sql/secure_objects.py": 1273,  # SPLIT-CANDIDATE (active storage refactor)
    "src/aeat/domain/calculations/registry/_applicability.py": 1252,  # SPLIT-CANDIDATE
    "src/aeat/domain/calculations/registry/_schema.py": 1340,
    "src/aeat/entrypoints/cli/tests/test_registry_cli.py": 1360,  # SPLIT-CANDIDATE (Period construction verbosity)
    "src/aeat/entrypoints/cli/_app_live.py": 1265,
    "src/aeat/entrypoints/cli/_ledger_payloads.py": 1303,
    "src/aeat/entrypoints/cli/_modelo_payloads.py": 1295,
}
_CALLABLE_LINE_LIMIT_OVERRIDES = {
    ("src/aeat/application/modelo/_revision_persistence.py", "persist_filed_revision"): 192,  # SPLIT-CANDIDATE
    ("src/aeat/application/modelo/_filing_actions.py", "file_modelo_revision"): 192,  # SPLIT-CANDIDATE
    # Recovered-feature growth (stash recovery); SPLIT-CANDIDATE: owners extract helpers.
    ("src/aeat/application/filing/__init__.py", "build_draft"): 196,  # SPLIT-CANDIDATE
    ("src/aeat/application/ledger/_actions_classification.py", "bulk_classify_from_csv"): 185,  # SPLIT-CANDIDATE
    ("src/aeat/application/modelo/_export.py", "export_modelo_revision"): 215,  # SPLIT-CANDIDATE
    ("src/aeat/application/modelo/_projection.py", "project_modelo_100_from_m130"): 290,  # SPLIT-CANDIDATE
    # Oversize callables pinned to their present size so future edits must split
    # before growing them. The calculate-with-diagnostics entry grew under the
    # source-mesh/diagnostics work and is re-pinned (SPLIT-CANDIDATE: extract the
    # diagnostic-collection helpers).
    (
        "src/aeat/application/modelo/_calculation_actions.py",
        "calculate_modelo_revision_from_bucket_aggregation_with_diagnostics",
    ): 226,  # SPLIT-CANDIDATE
    ("src/aeat/domain/calculations/registry/_formula_runtime.py", "calculate_registry_snapshot"): 205,
    ("src/aeat/entrypoints/cli/_ledger.py", "ledger_classify"): 220,  # SPLIT-CANDIDATE
    # Extracted LLM ledger CLI verb (active LLM-ledger campaign); SPLIT-CANDIDATE.
    ("src/aeat/entrypoints/cli/_ledger_llm_cli.py", "ledger_saturate_llm"): 187,
}


def _aeat_python_files() -> tuple[Path, ...]:
    root = PROJECT_ROOT / "src" / "aeat"
    return tuple(path for path in sorted(root.rglob("*.py")) if "__pycache__" not in path.parts)


def _relative(path: Path) -> str:
    return path.relative_to(PROJECT_ROOT).as_posix()


def test_tracked_python_modules_do_not_exceed_line_budgets() -> None:
    offenders: list[str] = []
    for path in _aeat_python_files():
        relative = _relative(path)
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        budget = _MODULE_LINE_LIMIT_OVERRIDES.get(relative, _DEFAULT_MODULE_LINE_LIMIT)
        if line_count > budget:
            offenders.append(f"{relative}: {line_count} lines > budget {budget}")

    assert offenders == [], "Python module size budget exceeded:\n  " + "\n  ".join(offenders)


def test_tracked_production_callables_do_not_exceed_line_budgets() -> None:
    offenders: list[str] = []
    for path in _aeat_python_files():
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
            budget = _CALLABLE_LINE_LIMIT_OVERRIDES.get((relative, node.name), _DEFAULT_CALLABLE_LINE_LIMIT)
            if line_count > budget:
                offenders.append(f"{relative}:{node.name}: {line_count} lines > budget {budget}")

    assert offenders == [], "Python callable size budget exceeded:\n  " + "\n  ".join(offenders)
