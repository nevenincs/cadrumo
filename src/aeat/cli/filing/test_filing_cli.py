"""Smoke tests for ``aeat filing`` CLI commands.

These tests use Typer's :class:`CliRunner` against the root
``aeat`` Typer app and a temporary drafts directory configured
via ``AEAT_DRAFTS_DIR``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ...filing import build_draft
from ...filing.testing import SyntheticProfile, default_schema_provider
from .. import app

runner = CliRunner()


def _write_inputs(tmp_path: Path) -> Path:
    """Write a JSON inputs file with a clean Modelo 130 draft."""
    payload = {
        "01": 12500,
        "02": 3500,
        "05": 400,
        "06": 0,
    }
    target = tmp_path / "inputs.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


@pytest.fixture
def drafts_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``AEAT_DRAFTS_DIR`` at a clean per-test directory."""
    target = tmp_path / "drafts"
    target.mkdir()
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(target))
    return target


@pytest.fixture
def submissions_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "submissions"
    target.mkdir()
    monkeypatch.setenv("AEAT_SUBMISSIONS_DIR", str(target))
    monkeypatch.setenv("AEAT_SUBMISSION_BROWSER_TRACE_DIR", str(tmp_path / "traces"))
    return target


def _write_original_submission(drafts_dir: Path, submissions_dir: Path) -> str:
    draft = build_draft(
        modelo="130",
        period="2024Q1",
        profile=SyntheticProfile(
            tax_id="00000000T",
            display_name="CLI amendment subject",
            applicable_modelos=("130",),
        ),
        inputs={"01": 12500, "02": 3500, "05": 400, "06": 0},
        schema_provider=default_schema_provider(),
    )
    draft_path = drafts_dir / f"130_2024Q1_{draft.draft_id}.json"
    draft_path.write_text(draft.model_dump_json(indent=2), encoding="utf-8")

    submission_payload = {
        "submission_id": "sub-cli-1",
        "draft_id": draft.draft_id,
        "modelo": "130",
        "period": "2024Q1",
        "profile_tax_id": "00000000T",
        "status": "SUBMITTED",
        "justificante_csv": "CSV-SUB-CLI-1",
        "justificante_pdf_path": None,
        "submitted_at": "2026-04-13T08:00:00+00:00",
        "acknowledged_at": None,
        "attempts": [
            {
                "attempt_id": "sub-cli-1.1",
                "started_at": "2026-04-13T08:00:00+00:00",
                "ended_at": "2026-04-13T08:00:00+00:00",
                "status": "SUBMITTED",
                "error_code": None,
                "error_message": None,
                "browser_trace_path": None,
            }
        ],
    }
    (submissions_dir / "sub-cli-1.json").write_text(json.dumps(submission_payload), encoding="utf-8")
    return "sub-cli-1"


@pytest.mark.unit
class TestFilingCLI:
    def test_build_writes_draft_to_disk(self, tmp_path: Path, drafts_dir: Path) -> None:
        inputs = _write_inputs(tmp_path)
        result = runner.invoke(
            app,
            [
                "filing",
                "build",
                "--modelo",
                "130",
                "--period",
                "2026Q1",
                "--inputs",
                str(inputs),
            ],
        )
        assert result.exit_code == 0, result.output
        produced = sorted(drafts_dir.glob("130_2026Q1_*.json"))
        assert len(produced) == 1

    def test_show_and_validate_round_trip(self, tmp_path: Path, drafts_dir: Path) -> None:
        inputs = _write_inputs(tmp_path)
        build_result = runner.invoke(
            app,
            [
                "filing",
                "build",
                "--modelo",
                "130",
                "--period",
                "2026Q1",
                "--inputs",
                str(inputs),
            ],
        )
        assert build_result.exit_code == 0
        produced = next(drafts_dir.glob("130_2026Q1_*.json"))

        show_result = runner.invoke(app, ["filing", "show", str(produced)])
        assert show_result.exit_code == 0

        validate_result = runner.invoke(app, ["filing", "validate", str(produced)])
        assert validate_result.exit_code == 0

    def test_list_filters_by_modelo(self, tmp_path: Path, drafts_dir: Path) -> None:
        inputs = _write_inputs(tmp_path)
        runner.invoke(
            app,
            [
                "filing",
                "build",
                "--modelo",
                "130",
                "--period",
                "2026Q1",
                "--inputs",
                str(inputs),
            ],
        )
        result = runner.invoke(app, ["filing", "list", "--modelo", "130"])
        assert result.exit_code == 0

    def test_complementaria_build_and_submit_dry_run(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
    ) -> None:
        submission_id = _write_original_submission(drafts_dir, submissions_dir)
        payload = {
            "original_submission_id": submission_id,
            "updated_inputs": {"01": 13000, "02": 3500, "05": 400, "06": 0},
            "reasons": {"01": "Late income invoice received after original filing."},
        }
        payload_path = tmp_path / "amendment.json"
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        build_result = runner.invoke(
            app,
            ["filing", "complementaria", "build", "130", "2024Q1", str(payload_path)],
        )
        assert build_result.exit_code == 0, build_result.output
        amendment_files = sorted((submissions_dir / "amendments").glob("*.json"))
        assert len(amendment_files) == 1
        amendment_id = amendment_files[0].stem

        submit_result = runner.invoke(app, ["filing", "complementaria", "submit", amendment_id])
        assert submit_result.exit_code == 0, submit_result.output
        assert "dry-run amendment submission OK" in submit_result.output

    def test_complementaria_live_refuses_stub_transport(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
    ) -> None:
        submission_id = _write_original_submission(drafts_dir, submissions_dir)
        payload = {
            "original_submission_id": submission_id,
            "updated_inputs": {"01": 13000, "02": 3500, "05": 400, "06": 0},
        }
        payload_path = tmp_path / "amendment-live.json"
        payload_path.write_text(json.dumps(payload), encoding="utf-8")

        build_result = runner.invoke(
            app,
            ["filing", "complementaria", "build", "130", "2024Q1", str(payload_path)],
        )
        assert build_result.exit_code == 0, build_result.output
        amendment_id = next((submissions_dir / "amendments").glob("*.json")).stem

        submit_result = runner.invoke(
            app,
            ["filing", "complementaria", "submit", amendment_id, "--live"],
            env={
                "AEAT_LIVE_SUBMIT_ENABLED": "true",
            },
        )
        assert submit_result.exit_code == 1, submit_result.output
        assert "refusing" in submit_result.output.lower()
        assert "stubbed" in submit_result.output.lower()
