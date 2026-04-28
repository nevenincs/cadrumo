"""CLI tests for ``aeat review`` approval and stale-detection flows."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ...filing import FilingDraft, FilingDraftStatus, FilingOperatorProfile, build_draft
from ...filing.runtime import build_runtime_schema_provider
from ...financial import RawProvenance, RawTransaction, SourceFormat
from ...financial.transactions import (
    BusinessClassification,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    save_transactions,
)
from .. import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_infra]

_RUNNER = CliRunner()


def _profile() -> FilingOperatorProfile:
    return FilingOperatorProfile(
        tax_id="00000000T",
        display_name="Kent",
        applicable_modelos=("130",),
    )


def _write_draft(path: Path) -> Path:
    draft = build_draft(
        modelo="130",
        period="2026Q1",
        profile=_profile(),
        inputs={"01": 12500, "02": 3500, "05": 400, "06": 0},
        schema_provider=build_runtime_schema_provider(),
    )
    target = path / f"130_2026Q1_{draft.draft_id}.json"
    target.write_text(draft.model_dump_json(indent=2), encoding="utf-8")
    return target


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


@pytest.fixture()
def drafts_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "drafts"
    target.mkdir()
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(target))
    return target


@pytest.fixture()
def transactions_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / "transactions"
    target.mkdir()
    monkeypatch.setenv("AEAT_FINANCIAL_TXS_DIR", str(target))
    return target


def test_review_approve_and_show_persist_metadata(drafts_dir: Path, transactions_dir: Path) -> None:
    draft_path = _write_draft(drafts_dir)
    draft_id = FilingDraft.model_validate_json(draft_path.read_text(encoding="utf-8")).draft_id

    approve = _RUNNER.invoke(
        app,
        ["review", "approve", draft_id, "--approved-by", "kent", "--yes"],
    )
    assert approve.exit_code == 0, approve.output

    show = _RUNNER.invoke(app, ["review", "show", draft_id])
    assert show.exit_code == 0, show.output
    assert "APPROVED" in show.output
    assert "kent" in show.output
    assert "aeat submission preflight" in show.output
    assert "aeat submission export" in show.output
    assert "aeat submission dry-run" not in show.output

    stored = FilingDraft.model_validate_json(draft_path.read_text(encoding="utf-8"))
    assert stored.status is FilingDraftStatus.APPROVED
    assert stored.approved_by == "kent"
    assert stored.approved_at is not None


def test_review_show_marks_draft_stale_after_transaction_catalogue_change(
    drafts_dir: Path,
    transactions_dir: Path,
) -> None:
    draft_path = _write_draft(drafts_dir)
    draft_id = FilingDraft.model_validate_json(draft_path.read_text(encoding="utf-8")).draft_id
    approve = _RUNNER.invoke(
        app,
        ["review", "approve", draft_id, "--approved-by", "kent", "--yes"],
    )
    assert approve.exit_code == 0, approve.output

    catalogue = TransactionCatalogue.from_transactions([_sample_transaction()])
    save_transactions(catalogue, transactions_dir / "transactions.json")

    show = _RUNNER.invoke(app, ["review", "show", draft_id])
    assert show.exit_code == 0, show.output
    assert "APPROVAL_STALE" in show.output
    assert "transaction catalogue changed" in show.output
    assert "aeat review approve" in show.output

    stale = _RUNNER.invoke(app, ["review", "stale"])
    assert stale.exit_code == 0, stale.output
    assert "transaction catalogue changed" in stale.output
    assert "aeat review show <draft_id>" in stale.output

    stored = FilingDraft.model_validate_json(draft_path.read_text(encoding="utf-8"))
    assert stored.status is FilingDraftStatus.APPROVAL_STALE


def test_review_unapprove_clears_approval_record(drafts_dir: Path, transactions_dir: Path) -> None:
    draft_path = _write_draft(drafts_dir)
    draft_id = FilingDraft.model_validate_json(draft_path.read_text(encoding="utf-8")).draft_id
    approve = _RUNNER.invoke(
        app,
        ["review", "approve", draft_id, "--approved-by", "kent", "--yes"],
    )
    assert approve.exit_code == 0, approve.output

    unapprove = _RUNNER.invoke(app, ["review", "unapprove", draft_id, "--yes"])
    assert unapprove.exit_code == 0, unapprove.output
    assert "aeat review approve" in unapprove.output

    stored = FilingDraft.model_validate_json(draft_path.read_text(encoding="utf-8"))
    assert stored.status is FilingDraftStatus.READY_TO_SUBMIT
    assert stored.approved_at is None
    assert stored.approved_by is None
    assert stored.review_checksum is None
    assert stored.approval_basis is None


def test_review_show_rejects_unknown_draft_id(drafts_dir: Path, transactions_dir: Path) -> None:
    result = _RUNNER.invoke(app, ["review", "show", "missing-draft-id"])
    assert result.exit_code == 2
    assert "no persisted draft found" in result.output
