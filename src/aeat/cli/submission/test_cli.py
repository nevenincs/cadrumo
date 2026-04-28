"""Unit tests for the ``aeat submission`` Typer sub-app."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ...filing import FilingDraft, FilingOperatorProfile, approve_draft, build_draft
from ...filing.runtime import build_runtime_schema_provider
from ...financial import RawProvenance, RawTransaction, SourceFormat
from ...financial.transactions import (
    BusinessClassification,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    save_transactions,
)
from ...submission import SubmissionAttempt, SubmissionStatus, SubmittedFiling
from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture()
def isolated_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the submission engine at tmp dirs via env vars."""
    monkeypatch.setenv("AEAT_SUBMISSIONS_DIR", str(tmp_path / "submissions"))
    monkeypatch.setenv("AEAT_SUBMISSION_BROWSER_TRACE_DIR", str(tmp_path / "traces"))
    monkeypatch.setenv("AEAT_FINANCIAL_TXS_DIR", str(tmp_path / "transactions"))
    return tmp_path


@pytest.fixture()
def draft_path(tmp_path: Path) -> Path:
    draft = _approved_draft()
    path = tmp_path / "draft.json"
    path.write_text(draft.model_dump_json(indent=2), encoding="utf-8")
    return path


def _approved_draft() -> FilingDraft:
    draft = build_draft(
        modelo="130",
        period="2026Q1",
        profile=FilingOperatorProfile(
            tax_id="X1234567L",
            display_name="CLI operator",
            applicable_modelos=("130",),
        ),
        inputs={"01": 12500, "02": 3500, "05": 400, "06": 0},
        schema_provider=build_runtime_schema_provider(),
    )
    return approve_draft(
        draft,
        approved_by="kent",
        schema_provider=build_runtime_schema_provider(),
        transaction_catalogue=TransactionCatalogue(),
    )


def _sample_transaction() -> Transaction:
    raw = RawTransaction(
        transaction_id="row-1",
        booked_date=date(2026, 4, 10),
        value_date=date(2026, 4, 10),
        amount=Decimal("-80.00"),
        currency="EUR",
        counterparty="Supplier SL",
        description="Software subscription",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 4, 18, 8, 0, tzinfo=UTC),
            provider_name="pytest",
        ),
        raw_fields={"Concepto": "Software subscription"},
    )
    return Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "business_classification": BusinessClassification.NOT_YET_PROCESSED,
        }
    )


class TestPreflightCommand:
    def test_ok(self, runner: CliRunner, draft_path: Path, isolated_dirs: Path) -> None:
        result = runner.invoke(app, ["preflight", str(draft_path)])
        assert result.exit_code == 0, result.output
        assert "preflight OK" in result.output

    @pytest.mark.parametrize(
        ("status", "expected_fragment"),
        [
            ("VALIDATED", "not approved"),
            ("READY_TO_SUBMIT", "not approved"),
        ],
    )
    def test_fails_when_draft_not_preflight_eligible(
        self,
        runner: CliRunner,
        tmp_path: Path,
        isolated_dirs: Path,
        status: str,
        expected_fragment: str,
    ) -> None:
        payload = _approved_draft().model_dump(mode="json")
        payload["status"] = status
        payload["approved_at"] = None
        payload["approved_by"] = None
        payload["review_checksum"] = None
        payload["approval_basis"] = None
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        result = runner.invoke(app, ["preflight", str(path)])
        assert result.exit_code == 1
        assert "FAILED" in result.output
        assert expected_fragment in result.output

    def test_marks_persisted_approved_draft_stale_before_preflight(
        self,
        runner: CliRunner,
        draft_path: Path,
        isolated_dirs: Path,
    ) -> None:
        transactions_path = isolated_dirs / "transactions" / "transactions.json"
        transactions_path.parent.mkdir(parents=True, exist_ok=True)
        save_transactions(TransactionCatalogue.from_transactions([_sample_transaction()]), transactions_path)

        result = runner.invoke(app, ["preflight", str(draft_path)])
        assert result.exit_code == 1
        assert "stale" in result.output

        refreshed = FilingDraft.model_validate_json(draft_path.read_text(encoding="utf-8"))
        assert refreshed.status.value == "APPROVAL_STALE"


class TestSubmitCommandRemoved:
    """The ``submit`` and ``dry-run`` subcommands are absent."""

    @pytest.mark.parametrize("command", ["submit", "dry-run"])
    def test_invocation_fails_with_no_such_command(
        self, runner: CliRunner, draft_path: Path, isolated_dirs: Path, command: str
    ) -> None:
        del isolated_dirs, draft_path
        result = runner.invoke(app, [command])
        # Typer/click returns 2 for unknown commands.
        assert result.exit_code == 2, result.output
        assert (
            command not in (result.output or "").split("\nUsage")[0].lower()
            or "no such command" in (result.output or "").lower()
        )

    def test_help_does_not_list_submit(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0, result.output
        for cmd in ("preflight", "export", "verify", "diff", "schemas", "check-nif", "show", "list"):
            assert cmd in result.output, f"expected `{cmd}` in --help, got: {result.output!r}"
        assert " submit " not in result.output, (
            "submission CLI must not advertise `submit` (see .vault/adr/2026-04-18-live-submit-cli-excision-adr.md)"
        )
        assert "dry-run" not in result.output


class TestShowAndList:
    def test_show_existing(self, runner: CliRunner, isolated_dirs: Path) -> None:
        submission_id = _write_historical_submission(isolated_dirs)
        result = runner.invoke(app, ["show", submission_id])
        assert result.exit_code == 0, result.output
        assert submission_id in result.output
        assert "draft-1" in result.output

    def test_show_missing_exits_1(self, runner: CliRunner, isolated_dirs: Path) -> None:
        result = runner.invoke(app, ["show", "deadbeef"])
        assert result.exit_code == 1

    def test_list_filters_by_modelo(self, runner: CliRunner, draft_path: Path, isolated_dirs: Path) -> None:
        del draft_path
        _write_historical_submission(isolated_dirs)
        result = runner.invoke(app, ["list", "--modelo", "130"])
        assert result.exit_code == 0, result.output
        assert "1 record" in result.output
        empty = runner.invoke(app, ["list", "--modelo", "303"])
        assert empty.exit_code == 0
        assert "0 record" in empty.output


def _write_historical_submission(root: Path) -> str:
    now = datetime.now(UTC)
    filing = SubmittedFiling(
        submission_id="sub-1",
        draft_id="draft-1",
        modelo="130",
        period="2026Q1",
        profile_tax_id="X1234567L",
        status=SubmissionStatus.PENDING,
        submitted_at=now,
        attempts=(
            SubmissionAttempt(
                attempt_id="attempt-1",
                started_at=now,
                ended_at=now,
                status=SubmissionStatus.PENDING,
            ),
        ),
    )
    target = root / "submissions" / f"{filing.submission_id}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(filing.model_dump_json(indent=2), encoding="utf-8")
    return filing.submission_id
