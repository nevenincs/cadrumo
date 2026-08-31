"""UTC-boundary regressions for historical submission audit records."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from ....core.period import Period
from ..models import ModeloPresentado, SubmissionAttempt, SubmissionStatus, make_submission_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_UTC = datetime(2026, 8, 1, 10, 0, tzinfo=UTC)


def _presented(*, submitted_at: datetime = _UTC, acknowledged_at: datetime | None = None) -> ModeloPresentado:
    """Build a real submission record with the supplied audit timestamps."""
    submission_id = make_submission_id("draft-utc-boundary", 1)
    return ModeloPresentado(
        submission_id=submission_id,
        draft_id="draft-utc-boundary",
        modelo="130",
        period=Period.from_year_and_code(2026, "1T"),
        profile_tax_id="X1234567L",
        status=SubmissionStatus.PRESENTADA,
        submitted_at=submitted_at,
        acknowledged_at=acknowledged_at,
        attempts=(
            SubmissionAttempt(
                attempt_id=f"{submission_id}.1",
                started_at=_UTC,
                ended_at=_UTC + timedelta(seconds=1),
                status=SubmissionStatus.PRESENTADA,
            ),
        ),
    )


@pytest.mark.parametrize(
    "value",
    (
        datetime(2026, 8, 1, 10, 0),
        datetime(2026, 8, 1, 11, 0, tzinfo=timezone(timedelta(hours=1))),
    ),
)
def test_submission_attempt_refuses_naive_and_non_utc_timestamps(value: datetime) -> None:
    """Attempt ordering never sees malformed timestamp shapes."""
    with pytest.raises(ValidationError, match=r"timezone-aware UTC|must be in UTC"):
        SubmissionAttempt(
            attempt_id=f"{make_submission_id('draft-utc-boundary', 1)}.1",
            started_at=value,
            ended_at=value,
            status=SubmissionStatus.PRESENTADA,
        )


def test_presented_record_refuses_mixed_awareness_before_ordering() -> None:
    """A mixed pair yields the domain validation error, not Python's TypeError."""
    with pytest.raises(ValidationError, match="timezone-aware UTC"):
        _presented(acknowledged_at=datetime(2026, 8, 1, 10, 1))


def test_presented_record_preserves_valid_utc_timestamps() -> None:
    """UTC timestamps remain unchanged through the domain model boundary."""
    presented = _presented(submitted_at=_UTC, acknowledged_at=_UTC + timedelta(minutes=1))

    assert presented.submitted_at is _UTC
    assert presented.acknowledged_at == _UTC + timedelta(minutes=1)
