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

from ....application.filing import FilingDraftStatus, FilingOperatorProfile, approve_draft, build_draft
from ....application.filing.runtime import build_runtime_schema_provider
from ....core.config import PROJECT_ROOT
from ....domain.deadlines import AutonomoProfile, IVARegime
from ....domain.financial.transactions import TransactionCatalogue
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
    from datetime import UTC, datetime

    from ....adapters.persistence.storage import (
        Envelope,
        SensitivityClass,
        save_encrypted_envelope,
    )
    from ....adapters.persistence.storage._encrypted_columns import _resolve_master_key_provider

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


def _write_original_submission(drafts_dir: Path, submissions_dir: Path) -> str:
    from datetime import UTC, datetime

    from ....adapters.outbound.aeat.export._models import SubmissionAttempt, SubmissionStatus, SubmittedFiling
    from ....adapters.outbound.aeat.export._repository import SubmissionRepository
    from ....application.filing._repository import FilingDraftRepository

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
    FilingDraftRepository(store_dir=drafts_dir).save(draft)

    submitted_at = datetime(2026, 4, 13, 8, 0, tzinfo=UTC)
    filing = SubmittedFiling(
        submission_id="sub-cli-1",
        draft_id=draft.draft_id,
        modelo="130",
        period="2024Q1",
        profile_tax_id="00000000T",
        status=SubmissionStatus.SUBMITTED,
        justificante_csv="CSV-SUB-CLI-1",
        submitted_at=submitted_at,
        attempts=(
            SubmissionAttempt(
                attempt_id="sub-cli-1.1",
                started_at=submitted_at,
                ended_at=submitted_at,
                status=SubmissionStatus.SUBMITTED,
            ),
        ),
    )
    SubmissionRepository(store_dir=submissions_dir).save(filing)
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
        produced = sorted(drafts_dir.glob("*.envelope.json"))
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
        produced = sorted(drafts_dir.glob("*.envelope.json"))
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
        produced = next(drafts_dir.glob("*.envelope.json"))

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
        from ....application.filing._repository import FilingDraftRepository

        repo = FilingDraftRepository(store_dir=drafts_dir)
        repo.save(approved)
        envelope_path = repo.envelope_path_for(approved.draft_id)

        validate_result = runner.invoke(app, ["filing", "validate", str(envelope_path)])
        assert validate_result.exit_code == 0, validate_result.output
        assert "aeat submission preflight" in validate_result.output

        refreshed = repo.load(approved.draft_id)
        assert refreshed is not None
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
        drafts = sorted(drafts_dir.glob("*.envelope.json"))
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
            ["filing", "import", "--from-justificante", str(pdf)],
        )
        assert result.exit_code != 0, result.output
        assert "100" in result.output
        assert not list(drafts_dir.glob("*.envelope.json"))
        assert not list(submissions_dir.glob("*.json"))

    def test_complementaria_submit_command_is_absent(
        self,
        runner_disabled: object = None,
    ) -> None:
        """``aeat filing complementaria submit`` must not exist.

        The complementaria submit transport was removed when main's PR
        #446 deleted every live-submit code path (no-live-submit
        charter). This canary fails closed if anyone re-introduces the
        subcommand.
        """
        del runner_disabled
        result = runner.invoke(app, ["filing", "complementaria", "submit", "amd-1"])
        # Click/Typer returns 2 for an unknown subcommand.
        assert result.exit_code == 2, result.output
        assert "no such command" in result.output.lower()
