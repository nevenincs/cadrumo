"""CRUD-audit journey (e): bulk-stash recovery without a whole-ledger reset.

The ``2026-06-10-cli-operator-crud-matrix-audit`` rated journey (e) -- "I
imported the wrong file twice and stashed half my rows by mistake" -- a FAIL:
the only documented escape from an accidental bulk stash was ``ledger reset``
(clear and re-import the whole ledger). This suite is the acceptance evidence
that the D2 ``restore`` verb makes that journey PASS: it drives the real
``aeat app ledger`` CLI end-to-end -- add several rows, stash them all, then
``restore`` each one back to active -- and asserts the ledger is whole again
WITHOUT a reset, with the restore recorded in each row's event history.

Harness mirrors the persona-journey suites: an isolated profile backend via
``override_settings`` + ``isolated_profile_storage_root`` +
``profile_create_storage_span`` + ``register_minimal_profile``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.user_profile._orchestration import profile_create_storage_span
from ....application.user_profile._testing import register_minimal_profile
from ....application.workflow._persistence import workflow_state_repository
from ....core.config import override_settings
from ....tests.secure_sql import isolated_profile_storage_root
from .. import app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_RUNNER = CliRunner()

_ROWS = (
    ("2026-03-01", "49.99", "Software subscription"),
    ("2026-03-05", "120.00", "Office chair"),
    ("2026-03-09", "15.50", "Domain renewal"),
    ("2026-03-12", "300.00", "Accountant fee"),
)


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        override_settings(aeat_local_storage_root=tmp_path, aeat_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span("default"),
    ):
        try:
            workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id="default"))
            yield
        finally:
            dispose_engine()


def _list_rows() -> list[dict[str, object]]:
    listed = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "list"])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    return payload.get("result", payload).get("rows", [])


def _add_rows() -> list[str]:
    ids: list[str] = []
    for booked_date, amount, description in _ROWS:
        added = _RUNNER.invoke(
            app,
            [
                "--format",
                "json",
                "app",
                "ledger",
                "add",
                "--date",
                booked_date,
                "--amount",
                amount,
                "--direction",
                "OUTGOING",
                "--description",
                description,
            ],
        )
        assert added.exit_code == 0, added.output
        payload = json.loads(added.output)
        ids.append(payload.get("result", payload)["transaction_id"])
    return ids


def test_bulk_stash_recovery_restores_every_row_without_a_reset() -> None:
    """Stash several rows by mistake, then restore them all to active -- the
    ledger is whole again without nuking and re-importing it."""
    added_ids = _add_rows()
    assert len(added_ids) == len(_ROWS)

    # Stash every row by mistake.
    for transaction_id in added_ids:
        stashed = _RUNNER.invoke(
            app,
            ["app", "ledger", "stash", "--id", transaction_id, "--reason", "bulk stash slip", "--yes"],
        )
        assert stashed.exit_code == 0, stashed.output

    by_state = {row["transaction_id"]: row["lifecycle_state"] for row in _list_rows()}
    assert all(by_state[transaction_id] == "STASHED" for transaction_id in added_ids), by_state

    # Restore every row to active -- the recovery the audit said did not exist.
    restored_event_ids: list[str] = []
    for transaction_id in added_ids:
        restored = _RUNNER.invoke(
            app,
            [
                "--format",
                "json",
                "app",
                "ledger",
                "restore",
                "--id",
                transaction_id,
                "--reason",
                "undo bulk stash",
                "--yes",
            ],
        )
        assert restored.exit_code == 0, restored.output
        payload = json.loads(restored.output).get("result", {})
        assert payload.get("review_status") is not None
        restored_event_ids.extend(payload.get("bucket_event_ids", []))

    # The ledger is whole again: every row is active, and no reset was run.
    by_state_after = {row["transaction_id"]: row["lifecycle_state"] for row in _list_rows()}
    assert {by_state_after[transaction_id] for transaction_id in added_ids} == {"ACTIVE"}, by_state_after
    assert len(by_state_after) == len(_ROWS)
    assert all(event_id for event_id in restored_event_ids)

    # Each row's history records the restore as the latest lifecycle action.
    for transaction_id in added_ids:
        history = _RUNNER.invoke(app, ["--format", "json", "app", "ledger", "history", transaction_id])
        assert history.exit_code == 0, history.output
        rendered = history.output
        assert "ledger.transaction.restored" in rendered, rendered


def test_restore_refuses_an_already_active_row_with_an_instructive_message() -> None:
    """Restoring an already-active row refuses, naming the reason rather than
    emitting a bare error."""
    [active_id] = _add_rows()[:1]
    refused = _RUNNER.invoke(
        app,
        ["app", "ledger", "restore", "--id", active_id, "--reason", "no-op", "--yes"],
    )
    assert refused.exit_code != 0
    assert "already active" in refused.output.lower(), refused.output


def test_restore_requires_explicit_confirmation() -> None:
    """``restore`` without ``--yes`` refuses, mirroring the forward verbs."""
    [transaction_id] = _add_rows()[:1]
    _RUNNER.invoke(app, ["app", "ledger", "stash", "--id", transaction_id, "--reason", "park", "--yes"])
    unconfirmed = _RUNNER.invoke(app, ["app", "ledger", "restore", "--id", transaction_id])
    assert unconfirmed.exit_code != 0, unconfirmed.output
