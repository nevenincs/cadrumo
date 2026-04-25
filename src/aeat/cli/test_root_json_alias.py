"""Regression tests for the root-level ``aeat --json`` alias."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ..deadlines import AutonomoProfile, IVARegime
from . import app as root_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]

_runner = CliRunner()


def _prepare_workflow_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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


def _unwrap_result(output: str) -> dict[str, object]:
    payload = json.loads(output)
    return payload["result"]


def test_root_json_alias_reaches_modelos_show() -> None:
    """`aeat --json modelos show 303` should emit machine-readable output."""

    result = _runner.invoke(root_app, ["--json", "modelos", "show", "303"])
    assert result.exit_code == 0, result.output
    payload = _unwrap_result(result.output)
    assert payload["code"] == "303"


def test_root_json_alias_reaches_portals_show() -> None:
    """`aeat --json portals show portal_sede_root` should emit JSON."""

    result = _runner.invoke(root_app, ["--json", "portals", "show", "portal_sede_root"])
    assert result.exit_code == 0, result.output
    payload = _unwrap_result(result.output)
    assert payload["portal"] == "portal_sede_root"


def test_root_json_alias_reaches_submission_check_nif() -> None:
    """`aeat --json submission check-nif X1234567L` should emit JSON."""

    result = _runner.invoke(root_app, ["--json", "submission", "check-nif", "X1234567L"])
    assert result.exit_code == 0, result.output
    payload = _unwrap_result(result.output)
    assert payload["status"] == "valid"
    assert payload["canonical"] == "X1234567L"


def test_root_json_alias_reaches_auth_status() -> None:
    """`aeat --json auth status` should emit the no-session JSON shape."""

    result = _runner.invoke(root_app, ["--json", "auth", "status"])
    assert result.exit_code == 0, result.output
    payload = _unwrap_result(result.output)
    assert payload["session"] is None


def test_root_json_alias_reaches_workflow_next(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`aeat --json workflow next --no-sync` should emit JSON from root mode."""

    _prepare_workflow_env(tmp_path, monkeypatch)
    result = _runner.invoke(root_app, ["--json", "workflow", "next", "--no-sync"])
    assert result.exit_code == 0, result.output
    payload = _unwrap_result(result.output)
    assert payload["run_id"]
    assert payload["final_stage"] == "ABORTED"


def test_root_json_alias_reaches_workflow_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`aeat --json workflow list` should emit a JSON array from root mode."""

    _prepare_workflow_env(tmp_path, monkeypatch)
    seed = _runner.invoke(root_app, ["--json", "workflow", "next", "--no-sync"])
    assert seed.exit_code == 0, seed.output

    result = _runner.invoke(root_app, ["--json", "workflow", "list"])
    assert result.exit_code == 0, result.output
    payload = _unwrap_result(result.output)
    assert len(payload) >= 1
