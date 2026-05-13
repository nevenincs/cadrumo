"""Audit the CLI/backend boundary rollout inventory.

These tests do not bless CLI-owned business logic. They make every tracked
boundary row explicit so each rollout wave can remove or downgrade one row at
a time without losing the backend API that owns the behavior.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

from aeat.core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_PLAN_PATH = PROJECT_ROOT / ".vault" / "plan" / "2026-05-08-cli-backend-boundary-plan.md"
_REFERENCE_PATH = PROJECT_ROOT / ".vault" / "reference" / "2026-05-08-cli-backend-boundary-reference.md"
_CLI_ROOT = PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli"

_FORBIDDEN_TEST_PROCESS_LANGUAGE = (
    "aspirational",
    "backwards-compat",
    "compatibility shim",
    "deferred",
    "fails by design",
    "migration state",
    "not yet delivered",
    "past-state",
    "phase ",
    "previously in this file",
    "stub",
    "todo",
    "tbd",
    "wave ",
    "xfail",
)

_LIVE_TEST_FILES = frozenset(
    {
        "src/aeat/entrypoints/cli/test_setup_auth_live.py",
    }
)


@dataclass(frozen=True)
class BoundaryFinding:
    row_id: str
    source: str
    symbols: tuple[str, ...]
    backend_gap: str
    owner: str


_KNOWN_FINDINGS: tuple[BoundaryFinding, ...] = (
    BoundaryFinding(
        row_id="CLI-001",
        source="src/aeat/entrypoints/cli/_common.py",
        symbols=("_canonical_period", "_profile_to_autonomo", "_aggregate_filing_inputs"),
        backend_gap="API-005",
        owner="application.filing",
    ),
    BoundaryFinding(
        row_id="CLI-002",
        source="src/aeat/entrypoints/cli/_ledger.py",
        symbols=("ledger_import", "_direction_resolver"),
        backend_gap="API-001",
        owner="application.transactions",
    ),
    BoundaryFinding(
        row_id="CLI-003",
        source="src/aeat/entrypoints/cli/_invoice.py",
        symbols=("invoice_import", "invoice_review"),
        backend_gap="API-003",
        owner="application.invoices",
    ),
    BoundaryFinding(
        row_id="CLI-004",
        source="src/aeat/entrypoints/cli/financial/profile.py",
        symbols=("set_ratio_cmd", "unset_ratio_cmd", "_resolve_key", "_parse_ratio", "_save_profile"),
        backend_gap="API-004",
        owner="application.profile",
    ),
    BoundaryFinding(
        row_id="CLI-005",
        source="src/aeat/entrypoints/cli/financial/txs.py",
        symbols=("classify_cmd", "classify_llm_cmd", "build_cmd"),
        backend_gap="API-002",
        owner="application.transactions",
    ),
    BoundaryFinding(
        row_id="CLI-006",
        source="src/aeat/entrypoints/cli/financial/invoices.py",
        symbols=("reconcile_cmd", "link_cmd"),
        backend_gap="API-003",
        owner="application.invoices",
    ),
    BoundaryFinding(
        row_id="CLI-007",
        source="src/aeat/entrypoints/cli/filing/__init__.py",
        symbols=("_handle_declaracion_import",),
        backend_gap="API-005",
        owner="application.filing",
    ),
    BoundaryFinding(
        row_id="CLI-008",
        source="src/aeat/entrypoints/cli/_overview.py",
        symbols=("overview_status",),
        backend_gap="API-008",
        owner="application.overview",
    ),
    BoundaryFinding(
        row_id="CLI-010",
        source="src/aeat/entrypoints/cli/data/ledgers/inventory.py",
        symbols=("create_inventory", "add_movement", "_money"),
        backend_gap="API-007",
        owner="application.inventory",
    ),
)


def _parse_source(relative_path: str) -> ast.Module:
    path = PROJECT_ROOT / relative_path
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _defined_symbols(tree: ast.Module) -> set[str]:
    return {
        node.name
        for node in ast.iter_child_nodes(tree)
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)
    }


def _iter_cli_test_files() -> tuple[Path, ...]:
    return tuple(sorted(_CLI_ROOT.rglob("test_*.py")))


def test_boundary_inventory_rows_have_live_source_anchors() -> None:
    """Every tracked CLI violation row must point at source that still exists."""

    offences: list[str] = []
    for finding in _KNOWN_FINDINGS:
        path = PROJECT_ROOT / finding.source
        if not path.exists():
            offences.append(f"{finding.row_id}: source missing: {finding.source}")
            continue
        symbols = _defined_symbols(_parse_source(finding.source))
        missing = sorted(set(finding.symbols) - symbols)
        if missing:
            offences.append(f"{finding.row_id}: missing symbols in {finding.source}: {', '.join(missing)}")
    assert offences == [], "boundary inventory drift:\n  " + "\n  ".join(offences)


def test_boundary_plan_tracks_every_known_cli_finding_and_backend_gap() -> None:
    """The rollout docs must track every static audit row and backend owner."""

    plan_text = _PLAN_PATH.read_text(encoding="utf-8")
    reference_text = _REFERENCE_PATH.read_text(encoding="utf-8")
    combined = f"{plan_text}\n{reference_text}"
    offences: list[str] = []
    for finding in _KNOWN_FINDINGS:
        for token in (finding.row_id, finding.backend_gap, finding.owner):
            if token not in combined:
                offences.append(f"{finding.row_id}: docs do not track {token!r}")
    assert offences == [], "boundary docs missing tracked rows:\n  " + "\n  ".join(offences)


def test_declaration_review_has_no_command_local_format_selector() -> None:
    """Root ``--format`` is the only output selector for declaration review."""

    tree = _parse_source("src/aeat/entrypoints/cli/_declaration.py")
    declaration_review = next(
        node
        for node in ast.iter_child_nodes(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "declaration_review"
    )
    parameter_names = {arg.arg for arg in declaration_review.args.args}
    assert "format_" not in parameter_names


def test_cli_observability_wrapper_module_is_absent_from_command_tree() -> None:
    """Generic run tracing is not part of the accepted CLI surface."""

    wrapper_path = PROJECT_ROOT / "src" / "aeat" / "entrypoints" / "cli" / "_observability.py"
    assert not wrapper_path.exists()

    offences: list[str] = []
    for path in sorted(_CLI_ROOT.rglob("*.py")):
        if path.name.startswith("test_"):
            continue
        text = path.read_text(encoding="utf-8")
        if "cli_run_context" in text or "build_arguments" in text or "._observability" in text:
            offences.append(path.relative_to(PROJECT_ROOT).as_posix())
    assert offences == []


def test_cli_unit_tests_do_not_contain_process_state_or_xfail_language() -> None:
    """CLI unit tests must describe executable behavior, not rollout meta-state."""

    offences: list[str] = []
    for path in _iter_cli_test_files():
        if path == Path(__file__):
            continue
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        if rel in _LIVE_TEST_FILES:
            continue
        text = path.read_text(encoding="utf-8").lower()
        for phrase in _FORBIDDEN_TEST_PROCESS_LANGUAGE:
            pattern = re.compile(rf"(?<![a-z0-9_]){re.escape(phrase)}(?![a-z0-9_])")
            if pattern.search(text):
                offences.append(f"{rel} contains {phrase!r}")
        if re.search(r"(?<![a-z0-9_])pytest\.skip(?![a-z0-9_])", text):
            offences.append(f"{rel} contains pytest.skip")
    assert offences == [], "CLI tests contain process-state or skip language:\n  " + "\n  ".join(offences)
