"""Real-wiring tests for the ``aeat workflow`` CLI.

These tests exercise the production helper path rather than the
``set_test_hooks`` seam, using a real profile JSON file, the
runtime filing schema provider, and the dry-run-safe submission
engine helper already shipped in the repo.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ...deadlines import AutonomoProfile, IVARegime
from .. import app as root_app
from ..deadlines._helpers import build_engine as build_deadline_engine
from ._helpers import clear_test_hooks

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]

runner = CliRunner()


def _next_pending_modelo_130_period() -> str:
    """Return a still-open Modelo 130 period for the current year."""

    today = date.today()
    profile = AutonomoProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )
    schedule = build_deadline_engine().compute(profile, today.year, today=today)
    for obligation in schedule.obligations:
        if obligation.modelo == "130" and obligation.closes_on >= today:
            return obligation.period
    raise AssertionError("expected at least one pending Modelo 130 obligation in the current year")


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
    period = _next_pending_modelo_130_period()
    result = runner.invoke(
        root_app,
        [
            "workflow",
            "run",
            "--modelo",
            "130",
            "--period",
            period,
            "--json",
            "--no-sync",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["final_stage"] == "DONE"
    persisted = runtime_env.parent / "runs" / f"{payload['run_id']}.json"
    assert persisted.exists()


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
    assert payload["final_stage"] == "DONE"
