"""Real-wiring tests for the ``aeat workflow`` CLI.

These tests exercise the production helper path rather than the
``set_test_hooks`` seam, using a real profile JSON file, the
runtime filing schema provider, and the dry-run-safe submission
engine helper already shipped in the repo.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ...deadlines import AutonomoProfile, IVARegime
from .. import app as root_app
from ._helpers import clear_test_hooks

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]

runner = CliRunner()


@pytest.fixture(autouse=True)
def _clear_hooks() -> Iterator[None]:
    clear_test_hooks()
    yield None
    clear_test_hooks()


@pytest.fixture()
def runtime_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    profile = AutonomoProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")

    inputs_path = tmp_path / "inputs.json"
    inputs_path.write_text(json.dumps({"01": 12500, "02": 3500, "05": 400, "06": 0}), encoding="utf-8")

    monkeypatch.setenv("AEAT_DEFAULT_PROFILE_PATH", str(profile_path))
    monkeypatch.setenv("AEAT_WORKFLOW_DRAFT_INPUTS_PATH", str(inputs_path))
    monkeypatch.setenv("AEAT_WORKFLOW_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("AEAT_SUBMISSIONS_DIR", str(tmp_path / "submissions"))
    monkeypatch.setenv("AEAT_SUBMISSION_BROWSER_TRACE_DIR", str(tmp_path / "traces"))
    return profile_path


def test_workflow_run_uses_real_runtime_wiring(runtime_env: Path) -> None:
    # Gate-1 now requires DraftStatus.APPROVED; a freshly built draft is
    # READY_TO_SUBMIT at best, so preflight fails with "not approved".
    # Use 2026Q2 (deadline July 2026) so the period is still open.
    result = runner.invoke(
        root_app,
        [
            "workflow",
            "run",
            "--modelo",
            "130",
            "--period",
            "2026Q2",
            "--json",
            "--no-sync",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["final_stage"] == "ABORTED"
    assert payload["aborted_reason"] == "PREFLIGHT_FAILED"
    assert "not approved" in payload["summary"]["en"]


def test_workflow_next_uses_real_runtime_wiring(runtime_env: Path) -> None:
    result = runner.invoke(
        root_app,
        [
            "workflow",
            "next",
            "--json",
            "--no-sync",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["final_stage"] == "ABORTED"
    assert payload["aborted_reason"] == "PREFLIGHT_FAILED"
    assert "not approved" in payload["summary"]["en"]
