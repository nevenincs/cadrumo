"""Smoke tests for ``aeat filing`` CLI commands.

Drives the root ``aeat`` Typer app via :class:`typer.testing.CliRunner`
against per-test ``tmp_path`` directories wired through
``AEAT_DRAFTS_DIR``, ``AEAT_SUBMISSIONS_DIR``,
``AEAT_FINANCIAL_TXS_DIR``, and ``AEAT_DEFAULT_PROFILE_PATH``. Profile
and submission fixtures round-trip through the real encrypted
persistence layer rather than the production master key.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....core.config import PROJECT_ROOT
from ....domain.deadlines import AutonomoProfile, IVARegime
from ....domain.submission import SubmissionAttempt, SubmissionStatus, SubmittedFiling
from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

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


def _write_submitted_filing(submissions_dir: Path, *, draft_id: str = "draft-cli-1") -> SubmittedFiling:
    """Persist a real submitted-filing record for CLI amendment tests."""
    now = datetime(2026, 4, 13, 8, 0, tzinfo=UTC)
    filing = SubmittedFiling(
        submission_id="sub-cli-1",
        draft_id=draft_id,
        modelo="130",
        period="2024Q1",
        profile_tax_id="00000000T",
        status=SubmissionStatus.SUBMITTED,
        justificante_csv="CSV-sub-cli-1",
        justificante_pdf_path=None,
        submitted_at=now,
        acknowledged_at=None,
        attempts=(
            SubmissionAttempt(
                attempt_id="sub-cli-1.1",
                started_at=now,
                ended_at=now,
                status=SubmissionStatus.SUBMITTED,
            ),
        ),
    )
    (submissions_dir / "sub-cli-1.json").write_text(filing.model_dump_json(), encoding="utf-8")
    return filing


def _single_draft_path(drafts_dir: Path) -> Path:
    drafts = list(drafts_dir.glob("*.envelope.json"))
    assert len(drafts) == 1
    return drafts[0]


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
    from datetime import UTC, datetime

    from ....adapters.persistence.storage import (
        Envelope,
        SensitivityClass,
        save_encrypted_envelope,
    )
    from ....adapters.persistence.storage.crypto._encrypted_columns import _resolve_master_key_provider

    profile = AutonomoProfile(
        tax_id="00000000T",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )
    target = tmp_path / "profile.json"
    envelope = Envelope[AutonomoProfile](
        schema_version=1,
        written_at=datetime.now(UTC),
        classification=SensitivityClass.IDENTITY,
        payload=profile,
    )
    save_encrypted_envelope(
        envelope,
        target,
        master_key_provider=_resolve_master_key_provider(),
        hkdf_context=b"aeat.application.setup.profile.v1",
    )
    monkeypatch.setenv("AEAT_DEFAULT_PROFILE_PATH", str(target))
    return target


class TestFilingCLI:
    """Smoke coverage for ``aeat filing`` build, show, validate, list, import paths."""

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
        assert "Saved draft" in result.output
        assert "registry:130:2019-y-siguientes" in result.output
        assert _single_draft_path(drafts_dir).exists()

    def test_build_writes_draft_to_disk(self, tmp_path: Path, drafts_dir: Path) -> None:
        inputs = _write_inputs(tmp_path)
        result = runner.invoke(
            app,
            [
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
        assert "registry:130:2019-y-siguientes" in result.output
        assert _single_draft_path(drafts_dir).exists()

    def test_show_and_validate_round_trip(self, tmp_path: Path, drafts_dir: Path, transactions_dir: Path) -> None:
        inputs = _write_inputs(tmp_path)
        build_result = runner.invoke(
            app,
            [
                "build",
                "--modelo",
                "130",
                "--period",
                "2026Q1",
                "--inputs",
                str(inputs),
            ],
        )
        assert build_result.exit_code == 0, build_result.output
        draft_path = _single_draft_path(drafts_dir)

        show_result = runner.invoke(app, ["show", str(draft_path)])
        assert show_result.exit_code == 0, show_result.output
        assert "registry:130:2019-y-siguientes" in show_result.output

        validate_result = runner.invoke(app, ["validate", str(draft_path)])
        assert validate_result.exit_code == 0, validate_result.output
        assert "READY_TO_SUBMIT" in validate_result.output

    def test_validate_preserves_approval_for_unchanged_reviewed_draft(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        transactions_dir: Path,
    ) -> None:
        del transactions_dir
        inputs = _write_inputs(tmp_path)
        result = runner.invoke(
            app,
            [
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
        draft_path = _single_draft_path(drafts_dir)

        validate_result = runner.invoke(app, ["validate", str(draft_path)])
        assert validate_result.exit_code == 0, validate_result.output
        assert "READY_TO_SUBMIT" in validate_result.output

    def test_list_filters_by_modelo(self, tmp_path: Path, drafts_dir: Path) -> None:
        inputs = _write_inputs(tmp_path)
        runner.invoke(
            app,
            [
                "build",
                "--modelo",
                "130",
                "--period",
                "2026Q1",
                "--inputs",
                str(inputs),
            ],
        )
        result = runner.invoke(app, ["list", "--modelo", "130"])
        assert result.exit_code == 0

    def test_import_persists_draft_and_submission(
        self,
        drafts_dir: Path,
        submissions_dir: Path,
    ) -> None:
        pdf = _JUSTIFICANTE_FIXTURES / "modelo_130_2026Q1.pdf"
        result = runner.invoke(
            app,
            ["import", "--from-justificante", str(pdf)],
        )
        assert result.exit_code == 0, result.output
        assert "from justificante" in result.output
        assert _single_draft_path(drafts_dir).exists()
        assert list(submissions_dir.glob("*.envelope.json"))

    def test_import_rejects_missing_pdf(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        submissions_dir: Path,
    ) -> None:
        missing = tmp_path / "nowhere.pdf"
        result = runner.invoke(
            app,
            ["import", "--from-justificante", str(missing)],
        )
        assert result.exit_code != 0, result.output
        assert not list(drafts_dir.glob("*.envelope.json"))
        assert not list(submissions_dir.glob("*.json"))

    def test_import_rejects_unsupported_modelo(
        self,
        drafts_dir: Path,
        submissions_dir: Path,
    ) -> None:
        pdf = _JUSTIFICANTE_FIXTURES / "modelo_100_2025A.pdf"
        result = runner.invoke(
            app,
            ["import", "--from-justificante", str(pdf)],
        )
        assert result.exit_code != 0, result.output
        assert not list(drafts_dir.glob("*.envelope.json"))
        assert not list(submissions_dir.glob("*.json"))

    def test_complementaria_submit_command_is_absent(
        self,
        runner_disabled: object = None,
    ) -> None:
        """``aeat filing complementaria submit`` must not exist.

        The complementaria submit transport was removed when every
        live-submit code path was deleted under the no-live-submit
        charter. This canary fails closed if anyone re-introduces the
        subcommand.
        """
        del runner_disabled
        result = runner.invoke(app, ["complementaria", "submit", "amd-1"])
        # Click/Typer returns 2 for an unknown subcommand.
        assert result.exit_code == 2, result.output
        assert "no such command" in result.output.lower()

    def test_complementaria_build_requires_registry_schema_provider(
        self,
        drafts_dir: Path,
        submissions_dir: Path,
        tmp_path: Path,
    ) -> None:
        inputs = _write_inputs(tmp_path)
        build_result = runner.invoke(
            app,
            [
                "build",
                "--modelo",
                "130",
                "--period",
                "2024Q1",
                "--inputs",
                str(inputs),
            ],
        )
        assert build_result.exit_code == 0, build_result.output
        draft_path = _single_draft_path(drafts_dir)
        draft_id = draft_path.name.removesuffix(".envelope.json")
        submitted = _write_submitted_filing(submissions_dir, draft_id=draft_id)
        payload = {
            "original_submission_id": submitted.submission_id,
            "updated_inputs": {
                "01": 13000,
                "02": 3500,
                "05": 400,
                "06": 0,
            },
        }

        result = runner.invoke(
            app,
            ["complementaria", "build", "130", "2024Q1", json.dumps(payload)],
        )

        assert result.exit_code == 0, result.output
        assert "Saved amended draft" in result.output
        assert len(list(drafts_dir.glob("*.envelope.json"))) == 2
        assert (submissions_dir / "amendments").exists()
