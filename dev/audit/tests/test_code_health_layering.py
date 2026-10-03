"""The code-health report's import dimension: the gate's exit status, classified.

``classify_import_gate_result`` is the whole mapping from the import gate's
process result onto the report's severity model, so it is exercised directly
on plain inputs. The real gate is run end to end by
``test_advisory_dimensions_scan``.
"""

from __future__ import annotations

import json

import pytest

from dev.exit_codes import FAILED, OK, TOOL_BROKEN, TOOL_MISSING

from ..report import IMPORT_QUALITY_RECIPE, Status, classify_import_gate_result

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_INTERRUPTED = 130


def _run_finished(headline: str, *, failed: list[str], operational: list[str]) -> str:
    envelope = {
        "event": "run_finished",
        "headline": headline,
        "failed_reasons": failed,
        "graph_authority": {"operational_reasons": operational},
    }
    return "progress line\n" + json.dumps(envelope) + "\n"


def test_a_clean_gate_is_green_and_available() -> None:
    report = classify_import_gate_result(OK, "", "")

    assert report.status is Status.GREEN
    assert report.available
    assert report.details == []


def test_a_gate_that_ran_and_found_violations_is_red_and_available() -> None:
    stdout = _run_finished("Import health failed: 2 new occurrence(s)", failed=["a -> b"], operational=[])

    report = classify_import_gate_result(FAILED, stdout, "")

    assert report.status is Status.RED
    assert report.available
    assert "import quality failed" in report.headline
    assert report.details[:2] == ["Import health failed: 2 new occurrence(s)", "a -> b"]
    assert f"`just {IMPORT_QUALITY_RECIPE}`" in report.details[-1]


@pytest.mark.parametrize("returncode", [TOOL_BROKEN, TOOL_MISSING, _INTERRUPTED])
def test_a_gate_that_could_not_complete_is_red_and_unavailable(returncode: int) -> None:
    """Never GREEN, never an advisory AMBER, and never mistaken for a findings verdict."""
    stdout = _run_finished(
        "Import health is unavailable because an authority component failed.",
        failed=[],
        operational=["subordinate checker timed out after 300s"],
    )

    report = classify_import_gate_result(returncode, stdout, "")

    assert report.status is Status.RED
    assert not report.available
    assert f"exited {returncode} without completing" in report.headline
    assert "subordinate checker timed out after 300s" in report.details


def test_an_unenveloped_failure_falls_back_to_the_raw_lines() -> None:
    report = classify_import_gate_result(TOOL_BROKEN, "", "lint-imports: crashed\n")

    assert not report.available
    assert report.details[0] == "lint-imports: crashed"
