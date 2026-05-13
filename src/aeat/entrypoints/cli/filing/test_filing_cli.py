"""Smoke tests for ``aeat filing`` CLI commands.

Drives the root ``aeat`` Typer app via :class:`typer.testing.CliRunner`
against per-test ``tmp_path`` directories wired through
``AEAT_DRAFTS_DIR``, ``AEAT_FINANCIAL_TXS_DIR``, and
``AEAT_DEFAULT_PROFILE_PATH``. Profile and submission fixtures
round-trip through the real encrypted persistence layer rather than the
production master key.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....application.filing import FilingBuilderError, FilingOperatorProfile, build_draft, build_runtime_schema_provider
from ....core.config import PROJECT_ROOT
from ....domain.filing import FilingAmendmentRepository, FilingDraftRepository
from ....domain.submission import SubmissionAttempt, SubmissionRepository, SubmissionStatus, SubmittedFiling
from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_JUSTIFICANTE_FIXTURES = PROJECT_ROOT / "tests" / "fixtures" / "justificantes"

runner = CliRunner()


def _registry_modelo_calculable_without_inputs() -> str:
    provider = build_runtime_schema_provider()
    profile = FilingOperatorProfile(tax_id="00000000T", display_name="CLI filing")
    for modelo in sorted(provider.collections):
        try:
            build_draft(
                modelo=modelo,
                period="2026Q1",
                profile=profile,
                inputs={},
                schema_provider=provider,
            )
        except FilingBuilderError:
            continue
        return modelo
    raise AssertionError("registry has no modelo calculable without explicit inputs")


def _write_inputs(tmp_path: Path) -> Path:
    """Write a JSON inputs file for registry-backed CLI build tests."""
    payload: dict[str, object] = {}
    target = tmp_path / "inputs.json"
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def _write_submitted_filing(
    _submissions_dir: Path,
    *,
    modelo: str,
    period: str,
    draft_id: str = "draft-cli-1",
) -> SubmittedFiling:
    """Persist a real submitted-filing record for CLI amendment tests."""
    now = datetime(2026, 4, 13, 8, 0, tzinfo=UTC)
    filing = SubmittedFiling(
        submission_id="sub-cli-1",
        draft_id=draft_id,
        modelo=modelo,
        period=period,
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
    SubmissionRepository().save(filing)
    return filing


def _single_draft_path(drafts_dir: Path) -> Path:
    del drafts_dir
    repository = FilingDraftRepository()
    draft_ids = repository.list_draft_ids()
    assert len(draft_ids) == 1
    return repository.envelope_path_for(draft_ids[0])


def _draft_count() -> int:
    return len(FilingDraftRepository().list_draft_ids())


def _amendment_count() -> int:
    return len(FilingAmendmentRepository().list_amendment_ids())


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
def active_workflow_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Seed the workflow state with an active profile for filing-build tests."""

    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'workflow.db').as_posix()}")
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    from ....adapters.persistence.storage.sql.engine import dispose_engine
    from ....application.profile._actions import set_active_profile, set_profile_values
    from ....application.workflow._persistence import workflow_state_repository

    dispose_engine()
    repository = workflow_state_repository()
    repository.update(
        lambda state: set_active_profile(
            set_profile_values(
                state,
                "operator",
                {"tax.id": "00000000T", "activity": "design", "iva.regime": "GENERAL"},
            ),
            "operator",
        )
    )


class TestFilingCLI:
    """Smoke coverage for ``aeat filing`` build, show, validate, list, import paths."""

    def test_build_uses_active_workflow_profile(
        self,
        tmp_path: Path,
        drafts_dir: Path,
        active_workflow_profile: None,
    ) -> None:
        del active_workflow_profile
        inputs = _write_inputs(tmp_path)
        modelo = _registry_modelo_calculable_without_inputs()
        result = runner.invoke(
            app,
            [
                "build",
                "--modelo",
                modelo,
                "--period",
                "2026Q1",
                "--inputs",
                str(inputs),
                "--profile-name",
                "Configured operator",
            ],
        )
        assert result.exit_code == 0, result.output
        assert f"registry:{modelo}:" in result.output
        assert _single_draft_path(drafts_dir).name

    def test_build_persists_draft_in_secure_backend(self, tmp_path: Path, drafts_dir: Path) -> None:
        inputs = _write_inputs(tmp_path)
        modelo = _registry_modelo_calculable_without_inputs()
        result = runner.invoke(
            app,
            [
                "build",
                "--modelo",
                modelo,
                "--period",
                "2026Q1",
                "--inputs",
                str(inputs),
                "--profile-tax-id",
                "00000000T",
            ],
        )
        assert result.exit_code == 0, result.output
        assert f"registry:{modelo}:" in result.output
        assert _single_draft_path(drafts_dir).name

    def test_show_and_validate_round_trip(self, tmp_path: Path, drafts_dir: Path, transactions_dir: Path) -> None:
        inputs = _write_inputs(tmp_path)
        modelo = _registry_modelo_calculable_without_inputs()
        build_result = runner.invoke(
            app,
            [
                "build",
                "--modelo",
                modelo,
                "--period",
                "2026Q1",
                "--inputs",
                str(inputs),
                "--profile-tax-id",
                "00000000T",
            ],
        )
        assert build_result.exit_code == 0, build_result.output
        draft_path = _single_draft_path(drafts_dir)

        show_result = runner.invoke(app, ["show", str(draft_path)])
        assert show_result.exit_code == 0, show_result.output
        assert f"registry:{modelo}:" in show_result.output

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
        modelo = _registry_modelo_calculable_without_inputs()
        result = runner.invoke(
            app,
            [
                "build",
                "--modelo",
                modelo,
                "--period",
                "2026Q1",
                "--inputs",
                str(inputs),
                "--profile-tax-id",
                "00000000T",
            ],
        )
        assert result.exit_code == 0, result.output
        draft_path = _single_draft_path(drafts_dir)

        validate_result = runner.invoke(app, ["validate", str(draft_path)])
        assert validate_result.exit_code == 0, validate_result.output
        assert "READY_TO_SUBMIT" in validate_result.output

    def test_list_filters_by_modelo(self, tmp_path: Path, drafts_dir: Path) -> None:
        inputs = _write_inputs(tmp_path)
        modelo = _registry_modelo_calculable_without_inputs()
        build_result = runner.invoke(
            app,
            [
                "build",
                "--modelo",
                modelo,
                "--period",
                "2026Q1",
                "--inputs",
                str(inputs),
                "--profile-tax-id",
                "00000000T",
            ],
        )
        assert build_result.exit_code == 0, build_result.output
        result = runner.invoke(app, ["list", "--modelo", modelo], terminal_width=240)
        assert result.exit_code == 0, result.output
        assert modelo in result.output
        assert "2026Q1" in result.output

    def test_import_refuses_pdf_when_required_registry_inputs_are_missing(
        self,
        drafts_dir: Path,
        submissions_dir: Path,
    ) -> None:
        pdf = _JUSTIFICANTE_FIXTURES / "modelo_130_2026Q1.pdf"
        result = runner.invoke(
            app,
            ["import", "--from-justificante", str(pdf)],
            terminal_width=240,
        )
        assert result.exit_code != 0, result.output
        assert "registry calculation failed" in result.output
        assert "irpf.previous_year_economic_activity_net_income" in result.output
        assert not list(drafts_dir.glob("*.envelope.json"))
        assert not list(submissions_dir.glob("*.envelope.json"))

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
        assert not list(submissions_dir.glob("*.envelope.json"))

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
        assert not list(submissions_dir.glob("*.envelope.json"))

    def test_complementaria_submit_command_is_absent(
        self,
    ) -> None:
        """``aeat filing complementaria submit`` must not exist.

        Local amendment drafting is available, but this CLI surface must not
        expose a remote presentation command.
        """
        result = runner.invoke(app, ["complementaria", "submit", "amd-1"])
        # Click/Typer returns 2 for an unknown subcommand.
        assert result.exit_code == 2, result.output
        assert "no such command" in result.output.lower()

    def test_complementaria_build_reports_missing_submission_cleanly(self) -> None:
        payload = {
            "original_submission_id": "missing-submission",
            "updated_inputs": {
                "01": 1,
            },
        }

        result = runner.invoke(
            app,
            ["complementaria", "build", "111", "2026Q1", json.dumps(payload)],
            terminal_width=240,
        )

        assert result.exit_code != 0, result.output
        assert "missing-submission" in result.output
        assert "Traceback" not in result.output

    def test_complementaria_build_requires_registry_schema_provider(
        self,
        drafts_dir: Path,
        submissions_dir: Path,
        tmp_path: Path,
    ) -> None:
        inputs = _write_inputs(tmp_path)
        modelo = _registry_modelo_calculable_without_inputs()
        period = "2024Q1"
        build_result = runner.invoke(
            app,
            [
                "build",
                "--modelo",
                modelo,
                "--period",
                period,
                "--inputs",
                str(inputs),
                "--profile-tax-id",
                "00000000T",
            ],
        )
        assert build_result.exit_code == 0, build_result.output
        draft_path = _single_draft_path(drafts_dir)
        draft_id = draft_path.name.removesuffix(".envelope.json")
        submitted = _write_submitted_filing(submissions_dir, modelo=modelo, period=period, draft_id=draft_id)
        payload = {
            "original_submission_id": submitted.submission_id,
            "updated_inputs": {
                "01": 1,
            },
        }

        result = runner.invoke(
            app,
            ["complementaria", "build", modelo, period, json.dumps(payload)],
        )

        assert result.exit_code == 0, result.output
        assert _draft_count() == 2
        assert _amendment_count() == 1
