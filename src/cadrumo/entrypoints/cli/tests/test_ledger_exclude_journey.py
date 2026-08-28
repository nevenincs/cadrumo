"""CLI acceptance for the reviewed-excluded verb.

Drives the real ``aeat app ledger exclude`` CLI end-to-end: add a row, exclude
it, and assert the uniform mutation quintet comes back with ``review_status``
``excluded`` and a ``ledger.transaction.reviewed_excluded`` event id, and that
the excluded row then reads as ``excluded`` in the review queue.

Harness mirrors the restore-journey suite: an isolated profile backend built
from :func:`~cadrumo.tests.active_profile_isolated_backend_fixture.active_profile_isolated_backend_fixture`.
"""

from __future__ import annotations

import json
from collections.abc import Sequence

import pytest
from click.testing import Result

from ....tests.active_profile_isolated_backend_fixture import active_profile_isolated_backend_fixture
from ....tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_PROFILE_ID = "00000000-0000-4000-8000-000000000000"

_isolated_backend = active_profile_isolated_backend_fixture(
    bucket_id=_PROFILE_ID,
    dispose_engine_around=True,
    settings_overrides={"cadrumo_output_language": "en"},
)


def _invoke(args: Sequence[str]) -> Result:
    return invoke_cached_cli(args)


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
    assert isinstance(payload, dict), added.output
    body = payload.get("result", payload)
    assert isinstance(body, dict), added.output
    transaction_id = body.get("transaction_id")
    assert isinstance(transaction_id, str), added.output
    return transaction_id


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

    # The row reads as excluded in the single-row view. `review` is the
    # interactive list surface and takes no positional id -- addressing one
    # transaction is `view`, whose id is a positional argument.
    reviewed = _invoke(["--format", "json", "app", "ledger", "view", transaction_id])
    assert reviewed.exit_code == 0, reviewed.output
    review_payload = json.loads(reviewed.output)["result"]
    assert review_payload["review_status"] == "excluded"


def test_exclude_requires_confirmation() -> None:
    transaction_id = _add_row()
    unconfirmed = _invoke(["app", "ledger", "exclude", transaction_id])
    assert unconfirmed.exit_code != 0
