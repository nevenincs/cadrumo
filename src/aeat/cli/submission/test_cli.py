"""Unit tests for the ``aeat submission`` Typer sub-app."""

from __future__ import annotations

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


@pytest.fixture(autouse=True)
def _patch_master_key(tmp_path: Path):
    """Wave-7: install an EphemeralMasterKeyProvider so the CLI's
    ciphertext-at-rest writes work in the test sandbox."""
    from ...storage import (
        EncryptedBlobStore,
        EphemeralMasterKeyProvider,
        SecretStore,
        override_master_key_provider,
        override_secret_store,
    )

    provider = EphemeralMasterKeyProvider()
    blob_store = EncryptedBlobStore(
        root_dir=tmp_path / "blobs",
        master_key_provider=provider,
    )
    secret_store = SecretStore(
        store_dir=tmp_path / "secrets",
        blob_store=blob_store,
        master_key_provider=provider,
    )
    override_master_key_provider(provider)
    override_secret_store(secret_store)
    try:
        yield
    finally:
        override_master_key_provider(None)
        override_secret_store(None)


@pytest.fixture()
def draft_path(tmp_path: Path) -> Path:
    """Persist an approved draft via :class:`FilingDraftRepository` and
    return its canonical envelope path.

    The CLI accepts a draft id or an envelope path; tests that need a
    file path use the latter so the preflight/dry-run loaders see a
    real ciphertext envelope on disk.
    """
    from ...filing._repository import FilingDraftRepository

    draft = _approved_draft()
    repository = FilingDraftRepository(store_dir=tmp_path / "drafts")
    repository.save(draft)
    return repository.envelope_path_for(draft.draft_id)


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
        import json as _json

        from ...filing._repository import FilingDraftRepository

        payload = _approved_draft().model_dump(mode="json")
        payload["status"] = status
        payload["approved_at"] = None
        payload["approved_by"] = None
        payload["review_checksum"] = None
        payload["approval_basis"] = None
        adjusted = FilingDraft.model_validate_json(_json.dumps(payload))
        repository = FilingDraftRepository(store_dir=tmp_path / "bad-drafts")
        repository.save(adjusted)
        path = repository.envelope_path_for(adjusted.draft_id)
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

        # Wave-9: the refreshed draft is persisted through the
        # FilingDraftRepository (ciphertext-only). Decode the draft id
        # from the canonical envelope filename and load via the repo.
        from ...filing._repository import FilingDraftRepository

        draft_id = draft_path.name[: -len(".envelope.json")]
        refreshed = FilingDraftRepository(store_dir=draft_path.parent).load(draft_id)
        assert refreshed is not None
        assert refreshed.status.value == "APPROVAL_STALE"


class TestDryRunCommand:
    def test_ok(self, runner: CliRunner, draft_path: Path, isolated_dirs: Path) -> None:
        result = runner.invoke(app, ["dry-run", str(draft_path)])
        assert result.exit_code == 0, result.output
        assert "dry-run OK" in result.output
        assert "PENDING" in result.output


class TestSubmitCommandRemoved:
    """The ``submit`` subcommand was removed by the 2026-04-18 ADR.

    Replaced :class:`TestSubmitCommand`. The new tests assert that
    invocation falls through to Typer's "no such command" path with
    exit code 2 and that the help surface does not advertise it.
    """

    def test_invocation_fails_with_no_such_command(
        self, runner: CliRunner, draft_path: Path, isolated_dirs: Path
    ) -> None:
        del isolated_dirs
        result = runner.invoke(app, ["submit", str(draft_path)])
        # Typer/click returns 2 for unknown commands.
        assert result.exit_code == 2, result.output
        assert (
            "submit" not in (result.output or "").split("\nUsage")[0].lower()
            or "no such command" in (result.output or "").lower()
        )

    def test_help_does_not_list_submit(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0, result.output
        # The four allowed commands are present; "submit" is not.
        for cmd in ("preflight", "dry-run", "show", "list"):
            assert cmd in result.output, f"expected `{cmd}` in --help, got: {result.output!r}"
        assert " submit " not in result.output, (
            "submission CLI must not advertise `submit` (see .vault/adr/2026-04-18-live-submit-cli-excision-adr.md)"
        )


class TestShowAndList:
    def test_show_existing(self, runner: CliRunner, draft_path: Path, isolated_dirs: Path) -> None:
        from ...filing._repository import FilingDraftRepository

        draft_id = draft_path.name[: -len(".envelope.json")]
        draft = FilingDraftRepository(store_dir=draft_path.parent).load(draft_id)
        assert draft is not None
        dry = runner.invoke(app, ["dry-run", str(draft_path)])
        assert dry.exit_code == 0
        # Extract submission_id from the output
        token = next(t for t in dry.output.split() if t.startswith("submission_id="))
        submission_id = token.split("=", 1)[1]
        result = runner.invoke(app, ["show", submission_id])
        assert result.exit_code == 0, result.output
        assert submission_id in result.output
        assert draft.draft_id in result.output

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
        assert "0 record" in empty.output
