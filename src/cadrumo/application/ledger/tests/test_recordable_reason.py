"""A reason its event could not record is refused before a writer loads or writes anything."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Final
from uuid import UUID

import pytest
from pydantic import ValidationError

from ....domain.buckets.event import BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH, BucketEventType
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.transactions.errors import TransactionValidationError
from ..actions_common import build_ledger_bucket_event, require_recordable_reason
from ..actions_lifecycle import reset_ledger_catalogue
from ..reset_operation import LedgerResetRequest

_YEAR = filing_year_envelope().horizon

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LIMIT: Final = BUCKET_EVENT_PAYLOAD_VALUE_MAX_LENGTH
_PROFILE: Final = "22222222-2222-4222-8222-222222222222"


def _event_takes(reason: str) -> bool:
    try:
        build_ledger_bucket_event(
            bucket_id=_PROFILE,
            event_type=BucketEventType.LEDGER_TRANSACTION_SPLIT,
            occurred_at=datetime(_YEAR, 4, 1, tzinfo=UTC),
            actor="operator",
            object_id="a" * 64,
            payload={"reason": reason},
        )
    except ValidationError:
        return False
    return True


def _guard_takes(reason: str) -> bool:
    try:
        require_recordable_reason(reason, operation="ledger reset")
    except TransactionValidationError:
        return False
    return True


@pytest.mark.parametrize(
    ("reason", "taken"),
    (
        ("", True),
        ("x" * _LIMIT, True),
        ("x" * (_LIMIT + 1), False),
    ),
    ids=("empty", "at-the-limit", "one-over"),
)
def test_the_guard_takes_exactly_what_the_event_records(reason: str, taken: bool) -> None:
    assert _guard_takes(reason) is taken
    assert _event_takes(reason) is taken


def test_the_guard_measures_the_reason_as_the_writers_trim_it() -> None:
    padded = "  " + "x" * _LIMIT + "  "

    assert _guard_takes(padded)
    assert _event_takes(padded.strip())


@pytest.mark.parametrize("dry_run", (True, False), ids=("preview", "commit"))
def test_a_reset_refuses_a_long_reason_in_its_preview_as_in_its_commit(dry_run: bool) -> None:
    # Wider than the event, so only the writer's own guard stands between it and a commit under way.
    request = LedgerResetRequest(profile_id=UUID(_PROFILE), reason="x" * (_LIMIT + 1), dry_run=dry_run)

    with pytest.raises(TransactionValidationError, match="reason is longer"):
        reset_ledger_catalogue(bucket_id=_PROFILE, actor="operator", reason=request.reason, dry_run=request.dry_run)
