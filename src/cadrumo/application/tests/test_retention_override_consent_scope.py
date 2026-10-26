"""An approved retention override covers the set it was shown, not a predicate.

The operator is shown a count of retained filed records and a safe-erase date,
and authorises erasing THOSE. If the retained set grows between that decision
and the destruction -- a filing persisted across a crash/resume window, say --
re-stamping the same approval onto the refreshed assessment would extend their
consent to records they never saw.

The guard drops the override in that case, so the reset pauses unresolved and
the operator gives consent again against the count that actually blocks. It is
deliberately one-directional: a set that SHRANK is still covered, because the
operator already authorised more than now stands.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ..config_reset import _retention_decision_from_record
from ..config_reset_models import ConfigResetRetentionDecision

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REASON = "Court order requiring erasure before the statutory retention date."


def _assessment(*, records: int):
    from ...domain.retention.floor import RetentionBlockingRecord, RetentionFloorAssessment

    now = datetime.now(UTC)
    return RetentionFloorAssessment(
        as_of=now,
        floor_years=4,
        retained=tuple(
            RetentionBlockingRecord(
                filing_record_id=f"{index:064x}",
                modelo="303",
                filing_year=2025,
                filed_at=now,
                earliest_safe_erase_date=now + timedelta(days=365),
            )
            for index in range(records)
        ),
    )


def _approved_for(records: int) -> ConfigResetRetentionDecision:
    return ConfigResetRetentionDecision(
        assessed_at=datetime.now(UTC),
        blocks_erase=True,
        retained_record_count=records,
        latest_safe_erase_date=datetime.now(UTC) + timedelta(days=365),
        override_approved=True,
        override_reason=_REASON,
    )


def test_the_override_survives_an_unchanged_retained_set() -> None:
    """The ordinary resume: same records, same consent."""
    decision = _retention_decision_from_record(_assessment(records=2), _approved_for(2))

    assert decision.override_approved is True
    assert decision.override_reason == _REASON


def test_the_override_survives_a_shrunken_retained_set() -> None:
    """Fewer records than authorised is still inside the operator's decision."""
    decision = _retention_decision_from_record(_assessment(records=1), _approved_for(2))

    assert decision.override_approved is True


def test_the_override_drops_when_the_retained_set_grew() -> None:
    """The load-bearing case: consent does not stretch to unseen records.

    Dropping the approval is what makes the reset pause unresolved rather than
    destroy filings the operator was never shown.
    """
    decision = _retention_decision_from_record(_assessment(records=5), _approved_for(2))

    assert decision.override_approved is False
    assert decision.override_reason is None
    assert decision.blocks_erase is True
