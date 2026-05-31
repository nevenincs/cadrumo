"""W17.P49 closure aggregate tests.

Verifies every closure contract for Steps S632-S637.  Each assertion is
real-behavior: no mocks, no skips, no tautologies.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_REPO_ROOT = Path(__file__).parent.parent.parent  # .../chore-476-restructure-execution
_SRC_ROOT = _REPO_ROOT / "src" / "aeat"


# ---------------------------------------------------------------------------
# S632 — BROAD-EXCEPT-RATIONALE-PYDANTIC-PARSE-PROXY markers in _dates.py
# ---------------------------------------------------------------------------


def test_s632_pydantic_parse_proxy_rationale_markers_present() -> None:
    """_dates.py must carry the rationale marker on every bare raise ValueError site."""
    src = (_SRC_ROOT / "core" / "parsing" / "_dates.py").read_text(encoding="utf-8")
    token = "BROAD-EXCEPT-RATIONALE-PYDANTIC-PARSE-PROXY"
    count = src.count(token)
    assert count >= 3, (
        f"_dates.py must contain at least 3 occurrences of {token!r}; found {count}"
    )


def test_s632_no_bare_raise_valueerror_without_marker() -> None:
    """Every raise ValueError in _dates.py must be on a line that carries the rationale marker."""
    src = (_SRC_ROOT / "core" / "parsing" / "_dates.py").read_text(encoding="utf-8")
    token = "BROAD-EXCEPT-RATIONALE-PYDANTIC-PARSE-PROXY"
    for lineno, line in enumerate(src.splitlines(), start=1):
        if "raise ValueError(" in line:
            assert token in line, (
                f"_dates.py line {lineno}: bare raise ValueError without rationale marker"
            )


# ---------------------------------------------------------------------------
# S633 — ANY-RETURN-RATIONALE-GOOGLE-OAUTH-STAGING markers in _google.py
# ---------------------------------------------------------------------------


def test_s633_google_oauth_staging_rationale_markers_present() -> None:
    """_google.py must carry the rationale marker on both installed: dict[str, Any] fields."""
    src = (_SRC_ROOT / "entrypoints" / "cli" / "_config" / "_google.py").read_text(
        encoding="utf-8"
    )
    token = "ANY-RETURN-RATIONALE-GOOGLE-OAUTH-STAGING"
    count = src.count(token)
    assert count >= 2, (
        f"_google.py must contain at least 2 occurrences of {token!r}; found {count}"
    )


# ---------------------------------------------------------------------------
# S634 — DEFAULT_CURRENCY replaces bare "EUR" defaults in _ledger_expenses.py
# ---------------------------------------------------------------------------


def test_s634_no_bare_eur_default_in_ledger_expenses() -> None:
    """_ledger_expenses.py must not use bare 'EUR' string as a field default value.

    Literal["EUR"] type annotations are exempt — only default-value positions are checked.
    Uses AST so Literal["EUR"] annotations are never misidentified.
    """
    from aeat.core.external_constants import DEFAULT_CURRENCY

    assert DEFAULT_CURRENCY == "EUR", "sanity: DEFAULT_CURRENCY must equal 'EUR'"

    source_path = _SRC_ROOT / "domain" / "renta" / "_ledger_expenses.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))

    violations: list[int] = []
    for node in ast.walk(tree):
        # AnnAssign: `field: Annotation = default` — check the default value only
        if isinstance(node, ast.AnnAssign) and node.value is not None:
            if isinstance(node.value, ast.Constant) and node.value.value == "EUR":
                violations.append(node.lineno)
        # Assign: `x = "EUR"` (bare assignment, not annotation)
        if isinstance(node, ast.Assign):
            if isinstance(node.value, ast.Constant) and node.value.value == "EUR":
                violations.append(node.lineno)
        # keyword in Call: `Field(default="EUR")` — detect "EUR" as keyword arg value
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if isinstance(kw.value, ast.Constant) and kw.value.value == "EUR":
                    violations.append(kw.value.lineno)

    assert not violations, (
        f"_ledger_expenses.py has bare 'EUR' default value at lines: {violations}; "
        "replace with DEFAULT_CURRENCY from aeat.core.external_constants"
    )


# ---------------------------------------------------------------------------
# S635 — prefill_report: BindingPrefillReport (not Any) in reconciliation model
# ---------------------------------------------------------------------------


def test_s635_prefill_report_type_is_binding_prefill_report() -> None:
    """IvaCompensationReconciliationReport.prefill_report must be typed BindingPrefillReport."""
    from aeat.application.calculations import (
        BindingPrefillReport,
        IvaCompensationReconciliationReport,
    )

    annotation = IvaCompensationReconciliationReport.model_fields["prefill_report"].annotation
    assert annotation is BindingPrefillReport, (
        f"prefill_report field annotation must be BindingPrefillReport; got {annotation!r}"
    )


# ---------------------------------------------------------------------------
# S636 — no pytest.skip in test_calc_sheets_pull_typing.py
# ---------------------------------------------------------------------------


def test_s636_no_pytest_skip_in_calc_sheets_pull_typing() -> None:
    """test_calc_sheets_pull_typing.py must not contain pytest.skip() calls."""
    src = (
        _SRC_ROOT
        / "adapters"
        / "outbound"
        / "google"
        / "test_calc_sheets_pull_typing.py"
    ).read_text(encoding="utf-8")
    assert "pytest.skip(" not in src, (
        "test_calc_sheets_pull_typing.py still contains pytest.skip(); replace with assert precondition"
    )


# ---------------------------------------------------------------------------
# Prior-wave inventory ratchets — invoked via subprocess for clean isolation
# ---------------------------------------------------------------------------


def _run_inventory_ratchet(test_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(test_path), "-q", "--tb=short"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        f"Inventory ratchet {test_path.name} FAILED:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_prior_wave_utf8_enrollment_inventory_passes() -> None:
    _run_inventory_ratchet(_SRC_ROOT / "test_utf8_enrollment_inventory.py")


def test_prior_wave_cast_rationale_inventory_passes() -> None:
    _run_inventory_ratchet(_SRC_ROOT / "test_cast_rationale_inventory.py")


def test_prior_wave_latin1_encoding_constant_enrollment_passes() -> None:
    _run_inventory_ratchet(_SRC_ROOT / "test_latin1_encoding_constant_enrollment.py")


def test_prior_wave_enum_constant_extraction_inventory_passes() -> None:
    _run_inventory_ratchet(_SRC_ROOT / "test_enum_constant_extraction_inventory.py")
