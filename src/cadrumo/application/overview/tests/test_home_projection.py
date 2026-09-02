"""Contract tests for the immutable Home projection."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ..home_projection import (
    HomeAccountSession,
    HomeAvailability,
    HomeLedgerReadiness,
    HomeProjectionV1,
    HomeSessionPosture,
    HomeZoneState,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_NOW = datetime(2026, 9, 2, 10, 0, tzinfo=UTC)
_AVAILABLE = HomeZoneState(availability=HomeAvailability.AVAILABLE, observed_at=_NOW)
_LOCKED = HomeZoneState(availability=HomeAvailability.LOCKED, reason_code="profile.locked")


def test_available_empty_projection_preserves_proven_zero_counts() -> None:
    projection = HomeProjectionV1(
        generated_at=_NOW,
        account=HomeAccountSession(posture=HomeSessionPosture.ACTIVE, profile_label="Example profile"),
        actions_state=_AVAILABLE,
        declarations_state=_AVAILABLE,
        ledger_state=_AVAILABLE,
        ledger=HomeLedgerReadiness(entries=0, requiring_review=0, unclassified=0, missing_evidence=0),
        agenda_state=_AVAILABLE,
        messages_state=_AVAILABLE,
        messages_requiring_attention=0,
    )

    assert projection.ledger is not None
    assert projection.ledger.entries == 0
    assert projection.messages_requiring_attention == 0
    with pytest.raises(ValidationError):
        projection.ledger.entries = 1


def test_locked_projection_cannot_claim_zero_ledger_or_messages() -> None:
    with pytest.raises(ValidationError, match="non-available Ledger zone"):
        HomeProjectionV1(
            generated_at=_NOW,
            account=HomeAccountSession(posture=HomeSessionPosture.LOCKED, profile_label="Example profile"),
            actions_state=_LOCKED,
            declarations_state=_LOCKED,
            ledger_state=_LOCKED,
            ledger=HomeLedgerReadiness(entries=0, requiring_review=0, unclassified=0, missing_evidence=0),
            agenda_state=_LOCKED,
            messages_state=_LOCKED,
        )


def test_never_captured_zone_refuses_a_false_observation_time() -> None:
    with pytest.raises(ValidationError, match="never-captured"):
        HomeZoneState(
            availability=HomeAvailability.NEVER_CAPTURED,
            observed_at=_NOW,
            reason_code="messages.never_captured",
        )


def test_ledger_issue_counts_cannot_exceed_entries() -> None:
    with pytest.raises(ValidationError, match="cannot exceed"):
        HomeLedgerReadiness(entries=1, requiring_review=2, unclassified=0, missing_evidence=0)


def test_selected_profile_posture_requires_a_label() -> None:
    with pytest.raises(ValidationError, match="requires a profile label"):
        HomeAccountSession(posture=HomeSessionPosture.ACTIVE)
