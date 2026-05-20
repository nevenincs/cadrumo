"""CLI tests for ``aeat config repair reset-state``."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage import (
    activate_master_key_provider,
    get_master_key_provider,
)
from aeat.adapters.persistence.storage.sql import SecureObjectRepository
from aeat.adapters.persistence.storage.sql.engine import dispose_engine
from aeat.application.workflow._models import WorkflowState
from aeat.application.workflow._persistence import workflow_state_repository
from aeat.domain.buckets import BucketEventHistoryRepository, BucketEventType
from aeat.tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_cli_backend(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(tmp_path / "storage"))
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
    """Create an active profile so a workflow-state envelope exists.

    ``config profile create`` is bootstrap-exempt: it provisions the
    profile bucket, opens its session, and writes the workflow-state
    secure-object row that ``reset-state`` later discards.
    """

    created = invoke_cached_cli(
        [
            "config",
            "profile",
            "create",
            "operator",
            "--quiet",
            "--tax-id",
            "00000000T",
            "--activity",
            "Servicios",
            "--iva-regime",
            "GENERAL",
        ]
    )
    assert created.exit_code == 0, created.output


def _row_exists() -> bool:
    with activate_master_key_provider(get_master_key_provider()):
        return SecureObjectRepository().exists("aeat.workflow", "state")


def test_reset_state_dry_run_returns_fingerprint_without_deleting_row() -> None:
    _seed_workflow_state()

    result = invoke_cached_cli(["--format", "json", "config", "repair", "reset-state", "--dry-run"])

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

    result = invoke_cached_cli(["config", "repair", "reset-state"])

    assert result.exit_code != 0
    assert _row_exists()


def test_reset_state_with_yes_deletes_row_emits_event_and_reload_is_empty() -> None:
    _seed_workflow_state()
    with activate_master_key_provider(get_master_key_provider()):
        history_before = len(BucketEventHistoryRepository().load().events)

    result = invoke_cached_cli(["--format", "json", "config", "repair", "reset-state", "--yes"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["dry_run"] is False
    assert payload["fingerprint"]["reason_class"] == "unreadable"

    assert not _row_exists()

    with activate_master_key_provider(get_master_key_provider()):
        catalogue = BucketEventHistoryRepository().load()
        reset_events = [
            event for event in catalogue.events.values() if event.event_type is BucketEventType.WORKFLOW_STATE_RESET
        ]
        assert len(reset_events) == 1
        assert len(catalogue.events) == history_before + 1

        reloaded = workflow_state_repository().load()
    fresh = WorkflowState()
    assert reloaded.model_dump(exclude={"updated_at"}) == fresh.model_dump(exclude={"updated_at"})
