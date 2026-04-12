"""Unit tests for the ``aeat submission`` Typer sub-app."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.cli.submission import app

pytestmark = pytest.mark.unit


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def isolated_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the submission engine at tmp dirs via env vars."""
    monkeypatch.setenv("AEAT_SUBMISSIONS_DIR", str(tmp_path / "submissions"))
    monkeypatch.setenv("AEAT_SUBMISSION_BROWSER_TRACE_DIR", str(tmp_path / "traces"))
    monkeypatch.setenv("AEAT_SUBMISSION_REQUIRE_HUMAN_CONFIRMATION", "true")
    return tmp_path


@pytest.fixture()
def draft_path(tmp_path: Path) -> Path:
    payload = {
        "draft_id": "draft-cli-1",
        "modelo": "130",
        "period": "2026Q1",
        "profile_tax_id": "X1234567L",
        "status": "READY_TO_SUBMIT",
        "values": {"01": "1000.00", "03": "100.00"},
        "findings": [],
    }
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class TestPreflightCommand:
    def test_ok(self, runner: CliRunner, draft_path: Path, isolated_dirs: Path) -> None:
        result = runner.invoke(app, ["preflight", str(draft_path)])
        assert result.exit_code == 0, result.output
        assert "preflight OK" in result.output

    def test_fails_when_draft_not_ready(self, runner: CliRunner, tmp_path: Path, isolated_dirs: Path) -> None:
        payload = {
            "draft_id": "d-bad",
            "modelo": "130",
            "period": "2026Q1",
            "profile_tax_id": "X",
            "status": "DRAFT",
            "values": {},
            "findings": [],
        }
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        result = runner.invoke(app, ["preflight", str(path)])
        assert result.exit_code == 1
        assert "FAILED" in result.output


class TestDryRunCommand:
    def test_ok(self, runner: CliRunner, draft_path: Path, isolated_dirs: Path) -> None:
        result = runner.invoke(app, ["dry-run", str(draft_path)])
        assert result.exit_code == 0, result.output
        assert "dry-run OK" in result.output
        assert "PENDING" in result.output


class TestSubmitCommand:
    def test_refuses_without_flag(self, runner: CliRunner, draft_path: Path, isolated_dirs: Path) -> None:
        result = runner.invoke(app, ["submit", str(draft_path)])
        assert result.exit_code == 2
        assert "refusing" in result.output.lower()

    def test_runs_live_with_flag(self, runner: CliRunner, draft_path: Path, isolated_dirs: Path) -> None:
        result = runner.invoke(
            app,
            ["submit", str(draft_path), "--i-understand-this-is-real"],
        )
        assert result.exit_code == 0, result.output
        assert "LIVE submission OK" in result.output
        assert "SUBMITTED" in result.output


class TestShowAndList:
    def test_show_existing(self, runner: CliRunner, draft_path: Path, isolated_dirs: Path) -> None:
        dry = runner.invoke(app, ["dry-run", str(draft_path)])
        assert dry.exit_code == 0
        # Extract submission_id from the output
        token = next(t for t in dry.output.split() if t.startswith("submission_id="))
        submission_id = token.split("=", 1)[1]
        result = runner.invoke(app, ["show", submission_id])
        assert result.exit_code == 0, result.output
        assert submission_id in result.output
        assert "draft-cli-1" in result.output

    def test_show_missing_exits_1(self, runner: CliRunner, isolated_dirs: Path) -> None:
        result = runner.invoke(app, ["show", "deadbeef"])
        assert result.exit_code == 1

    def test_list_filters_by_modelo(self, runner: CliRunner, draft_path: Path, isolated_dirs: Path) -> None:
        runner.invoke(app, ["dry-run", str(draft_path)])
        result = runner.invoke(app, ["list", "--modelo", "130"])
        assert result.exit_code == 0, result.output
        assert "1 record" in result.output
        empty = runner.invoke(app, ["list", "--modelo", "303"])
        assert empty.exit_code == 0
        assert "0 record" in empty.output
