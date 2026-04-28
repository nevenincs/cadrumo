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

from ...config import PROJECT_ROOT
from ...deadlines import AutonomoProfile, IVARegime
from ...filing import FilingDraft, FilingDraftStatus, FilingOperatorProfile, approve_draft, build_draft
from ...filing.runtime import build_runtime_schema_provider
from ...financial.transactions import TransactionCatalogue
from .. import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]

_JUSTIFICANTE_FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "justificantes"

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


@pytest.fixture
def transactions_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "transactions"
    target.mkdir()
    monkeypatch.setenv("AEAT_FINANCIAL_TXS_DIR", str(target))
    return target


@pytest.fixture
def profile_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    profile = AutonomoProfile(
        tax_id="00000000T",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )
    target = tmp_path / "profile.json"
    target.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    monkeypatch.setenv("AEAT_DEFAULT_PROFILE_PATH", str(target))
    return target


def _write_original_submission(drafts_dir: Path, submissions_dir: Path) -> str:
    draft = build_draft(
        modelo="130",
        period="2024Q1",
        profile=FilingOperatorProfile(
            tax_id="00000000T",
            display_name="CLI amendment subject",
            applicable_modelos=("130",),
        ),
        inputs={"01": 12500, "02": 3500, "05": 400, "06": 0},
        schema_provider=build_runtime_schema_provider(),
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


class TestFilingCLI:
    def test_build_uses_configured_profile_file(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        profile_path: Path,
    ) -> None:
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
                "--profile",
                str(profile_path),
                "--profile-name",
                "Configured operator",
            ],
        )
        assert result.exit_code == 0, result.output
        produced = sorted(drafts_dir.glob("130_2026Q1_*.json"))
        assert len(produced) == 1

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
        assert "Saved draft" in result.output
        assert " -> " in result.output
        assert "aeat review show" in result.output
        assert "aeat review approve" in result.output
        produced = sorted(drafts_dir.glob("130_2026Q1_*.json"))
        assert len(produced) == 1

    def test_show_and_validate_round_trip(self, tmp_path: Path, drafts_dir: Path, transactions_dir: Path) -> None:
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

    def test_validate_preserves_approval_for_unchanged_reviewed_draft(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        transactions_dir: Path,
    ) -> None:
        del transactions_dir
        draft = build_draft(
            modelo="130",
            period="2026Q1",
            profile=FilingOperatorProfile(
                tax_id="00000000T",
                display_name="Kent",
                applicable_modelos=("130",),
            ),
            inputs={"01": 12500, "02": 3500, "05": 400, "06": 0},
            schema_provider=build_runtime_schema_provider(),
        )
        approved = approve_draft(
            draft,
            approved_by="kent",
            schema_provider=build_runtime_schema_provider(),
            transaction_catalogue=TransactionCatalogue(),
        )
        draft_path = drafts_dir / f"130_2026Q1_{approved.draft_id}.json"
        draft_path.write_text(approved.model_dump_json(indent=2), encoding="utf-8")

        validate_result = runner.invoke(app, ["filing", "validate", str(draft_path)])
        assert validate_result.exit_code == 0, validate_result.output
        assert "aeat submission preflight" in validate_result.output
        assert "aeat submission export" in validate_result.output
        assert "aeat submission dry-run" not in validate_result.output

        refreshed = FilingDraft.model_validate_json(draft_path.read_text(encoding="utf-8"))
        assert refreshed.status is FilingDraftStatus.APPROVED
        assert refreshed.approved_at is not None
        assert refreshed.approved_by == "kent"
        assert refreshed.review_checksum is not None
        assert refreshed.approval_basis is not None

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

    def test_import_persists_draft_and_submission(
        self,
        drafts_dir: Path,
        submissions_dir: Path,
    ) -> None:
        pdf = _JUSTIFICANTE_FIXTURES / "modelo_130_2026Q1.pdf"
        result = runner.invoke(
            app,
            ["filing", "import", "--from-justificante", str(pdf)],
        )
        assert result.exit_code == 0, result.output
        drafts = sorted(drafts_dir.glob("130_2026Q1_*.json"))
        submissions = sorted(submissions_dir.glob("*.json"))
        assert len(drafts) == 1
        assert len(submissions) == 1
        assert "warning" in result.output.lower()
        assert "Imported draft" in result.output

    def test_import_rejects_missing_pdf(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
    ) -> None:
        missing = tmp_path / "nowhere.pdf"
        result = runner.invoke(
            app,
            ["filing", "import", "--from-justificante", str(missing)],
        )
        assert result.exit_code != 0, result.output
        assert not list(drafts_dir.glob("*.json"))
        assert not list(submissions_dir.glob("*.json"))

    def test_import_rejects_unsupported_modelo(
        self,
        drafts_dir: Path,
        submissions_dir: Path,
    ) -> None:
        pdf = _JUSTIFICANTE_FIXTURES / "modelo_100_2025A.pdf"
        result = runner.invoke(
            app,
            ["filing", "import", "--from-justificante", str(pdf)],
        )
        assert result.exit_code != 0, result.output
        assert "100" in result.output
        assert not list(drafts_dir.glob("*.json"))
        assert not list(submissions_dir.glob("*.json"))

    def test_complementaria_build_has_no_submit_followup(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        transactions_dir: Path,
    ) -> None:
        del transactions_dir
        submission_id = _write_original_submission(drafts_dir, submissions_dir)
        draft_files_before = {path.name for path in drafts_dir.glob("*.json")}
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
        assert "aeat review show" in build_result.output
        assert "aeat review approve" in build_result.output
        assert "submit" not in build_result.output.lower()
        amendment_files = sorted((submissions_dir / "amendments").glob("*.json"))
        assert len(amendment_files) == 1
        amended_draft_files = [path for path in drafts_dir.glob("*.json") if path.name not in draft_files_before]
        assert len(amended_draft_files) == 1

    def test_complementaria_submit_command_is_absent(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
        transactions_dir: Path,
    ) -> None:
        del transactions_dir
        submission_id = _write_original_submission(drafts_dir, submissions_dir)
        draft_files_before = {path.name for path in drafts_dir.glob("*.json")}
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
        assert [path for path in drafts_dir.glob("*.json") if path.name not in draft_files_before]

        submit_result = runner.invoke(
            app,
            ["filing", "complementaria", "submit", amendment_id],
        )
        assert submit_result.exit_code == 2, submit_result.output
        assert "no such command" in submit_result.output.lower()
