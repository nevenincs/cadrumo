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
_APPLICATION_ROOT = PROJECT_ROOT / "src" / "aeat" / "application"
_LOCALES_ROOT = PROJECT_ROOT / "src" / "aeat" / "locales"
_APPLICATION_ERROR_REGISTRY = PROJECT_ROOT / "src" / "aeat" / "core" / "errors" / "registry" / "_application.py"

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

_W01_P002_OPERATOR_GUIDANCE_FILES = (
    _CLI_ROOT / "_common.py",
    _CLI_ROOT / "_config.py",
    _APPLICATION_ROOT / "archive" / "_registry.py",
    _APPLICATION_ROOT / "auth" / "__init__.py",
    _APPLICATION_ROOT / "auth" / "_acquisition_lock.py",
    _APPLICATION_ROOT / "auth" / "_catalogue.py",
    _APPLICATION_ROOT / "auth" / "_sessions.py",
    _APPLICATION_ROOT / "diagnostics.py",
    _APPLICATION_ROOT / "filing" / "_calculate.py",
    _APPLICATION_ROOT / "filing" / "_export.py",
    _APPLICATION_ROOT / "operator_surface" / "_contract.py",
    _APPLICATION_ROOT / "overview" / "__init__.py",
    _APPLICATION_ROOT / "profile" / "__init__.py",
    _APPLICATION_ROOT / "review" / "_adapters.py",
    _APPLICATION_ROOT / "review" / "_edit.py",
    _APPLICATION_ROOT / "review" / "_filter.py",
    _APPLICATION_ROOT / "topics" / "__init__.py",
    _APPLICATION_ROOT / "wizard" / "_commands.py",
    _APPLICATION_ROOT / "wizard" / "_status.py",
    _APPLICATION_ERROR_REGISTRY,
    _LOCALES_ROOT / "ca.yml",
    _LOCALES_ROOT / "en.yml",
    _LOCALES_ROOT / "es.yml",
    _LOCALES_ROOT / "hu.yml",
)

_W01_P002_RETIRED_GUIDANCE = re.compile(
    r"aeat\s+config\s+setup|"
    r"aeat\s+setup|"
    r"aeat\s+app\s+topic|"
    r"aeat\s+app\s+archive|"
    r"aeat\s+app\s+invoice|"
    r"aeat\s+app\s+declaration|"
    r"aeat\s+filing|"
    r"aeat\s+financial|"
    r"aeat\s+review\s+show|"
    r"setup_reset|"
    r"SetupReset|"
    r"reset_setup"
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
        symbols=("build", "_load_inputs", "_handle_declaracion_import"),
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
        row_id="CLI-009",
        source="src/aeat/entrypoints/cli/registry.py",
        symbols=("inspect_registry_tree", "select_declarations_for_capture", "verify_filed_state"),
        backend_gap="API-006",
        owner="application.registry",
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


def test_w01_p002_operator_guidance_uses_accepted_roots() -> None:
    """Accepted config/app guidance must not point operators at retired command roots."""

    offences: list[str] = []
    for path in _W01_P002_OPERATOR_GUIDANCE_FILES:
        rel = path.relative_to(PROJECT_ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            if _W01_P002_RETIRED_GUIDANCE.search(line):
                offences.append(f"{rel}:{line_number}: {line.strip()}")

    assert offences == [], "retired operator guidance found:\n  " + "\n  ".join(offences)
