"""CLI tests for ``aeat config repair reset-state``."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.adapters.persistence.storage.sql import SecureObjectRepository
from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.application.workflow._models import WorkflowState
from aeat.application.workflow._persistence import workflow_state_repository
from aeat.domain.buckets import BucketEventHistoryRepository, BucketEventType
from aeat.entrypoints.cli import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_cli_backend(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
    monkeypatch.setenv("AEAT_TOKEN_DIR", str(tmp_path / "tokens"))
    monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("AEAT_FINANCIAL_TXS_DIR", str(tmp_path / "txs"))
    monkeypatch.setenv("AEAT_INVOICES_DIR", str(tmp_path / "invoices"))
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(tmp_path / "drafts"))
    try:
        yield
    finally:
        dispose_engine()


def _seed_workflow_state() -> None:
    """Persist a non-empty workflow state so reset has something to discard."""

    repository = workflow_state_repository()
    repository.save(WorkflowState())


def _row_exists() -> bool:
    return SecureObjectRepository().exists("aeat.workflow", "state")


def test_reset_state_dry_run_returns_fingerprint_without_deleting_row() -> None:
    _seed_workflow_state()
    runner = CliRunner()

    result = runner.invoke(app, ["--format", "json", "config", "repair", "reset-state", "--dry-run"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["dry_run"] is True
    fingerprint = payload["fingerprint"]
    assert fingerprint["schema_version"] == 1
    assert fingerprint["byte_length"] is not None and fingerprint["byte_length"] > 0
    assert fingerprint["reason_class"] == "unreadable"
    assert _row_exists()


def test_reset_state_without_yes_or_dry_run_raises_refusal_and_keeps_row() -> None:
    _seed_workflow_state()
    runner = CliRunner()

    result = runner.invoke(app, ["config", "repair", "reset-state"])

    assert result.exit_code != 0
    assert _row_exists()


def test_reset_state_with_yes_deletes_row_emits_event_and_reload_is_empty() -> None:
    _seed_workflow_state()
    history_before = len(BucketEventHistoryRepository().load().events)
    runner = CliRunner()

    result = runner.invoke(app, ["--format", "json", "config", "repair", "reset-state", "--yes"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["dry_run"] is False
    assert payload["fingerprint"]["reason_class"] == "unreadable"

    assert not _row_exists()

    catalogue = BucketEventHistoryRepository().load()
    reset_events = [
        event for event in catalogue.events.values() if event.event_type is BucketEventType.WORKFLOW_STATE_RESET
    ]
    assert len(reset_events) == 1
    assert len(catalogue.events) == history_before + 1

    reloaded = workflow_state_repository().load()
    fresh = WorkflowState()
    assert reloaded.model_dump(exclude={"updated_at"}) == fresh.model_dump(exclude={"updated_at"})
    assert reloaded.active_profile is None
    assert reloaded.profiles == {}
