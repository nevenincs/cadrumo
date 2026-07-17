"""CLI acceptance for the reviewed-excluded verb.

Drives the real ``aeat app ledger exclude`` CLI end-to-end: add a row, exclude
it, and assert the uniform mutation quintet comes back with ``review_status``
``excluded`` and a ``ledger.transaction.reviewed_excluded`` event id, and that
the excluded row then reads as ``excluded`` in the review queue.

Harness mirrors the restore-journey suite: an isolated profile backend via
``override_settings`` + ``isolated_profile_storage_root`` +
``profile_create_storage_span`` + ``register_minimal_profile``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from click.testing import Result

from ....adapters.persistence.storage.sql.engine import dispose_engine
from ....application.user_profile import profile_create_storage_span
from ....application.workflow import workflow_state_repository
from ....core.config import override_settings
from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ....tests.user_profile import register_minimal_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "00000000-0000-4000-8000-000000000000"


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    dispose_engine()
    with (
        override_settings(cadrumo_local_storage_root=tmp_path, cadrumo_output_language="en"),
        isolated_profile_storage_root(tmp_path=tmp_path),
        profile_create_storage_span(_PROFILE_ID),
    ):
        try:
            workflow_state_repository().update(lambda state: register_minimal_profile(state, profile_id=_PROFILE_ID))
            yield
        finally:
            dispose_engine()


def _add_row() -> str:
    added = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-03-01",
            "--amount",
            "49.99",
            "--direction",
            "OUTGOING",
            "--description",
            "Reimbursed personal card charge",
        ],
    )
    assert added.exit_code == 0, added.output
    payload = json.loads(added.output)
    return payload.get("result", payload)["transaction_id"]


def test_exclude_returns_quintet_and_marks_row_excluded() -> None:
    transaction_id = _add_row()

    excluded = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "exclude",
            transaction_id,
            "--reason",
            "not a business expense",
            "--yes",
        ],
    )
    assert excluded.exit_code == 0, excluded.output
    result = json.loads(excluded.output)["result"]

    # Uniform mutation quintet.
    assert set(result) >= {
        "bucket_id",
        "transaction_id",
        "bucket_event_ids",
        "review_status",
        "transaction",
    }
    assert result["transaction_id"] == transaction_id
    assert result["review_status"] == "excluded"
    assert len(result["bucket_event_ids"]) == 1
    assert result["transaction"]["business_classification"] == "REVIEWED_EXCLUDED"

    # The row reads as excluded in the single-row review view.
    reviewed = _invoke(["--format", "json", "app", "ledger", "review", transaction_id])
    assert reviewed.exit_code == 0, reviewed.output
    review_payload = json.loads(reviewed.output)["result"]
    assert review_payload["review_status"] == "excluded"


def test_exclude_requires_confirmation() -> None:
    transaction_id = _add_row()
    unconfirmed = _invoke(["app", "ledger", "exclude", transaction_id])
    assert unconfirmed.exit_code != 0
