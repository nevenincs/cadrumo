"""The operator's acceptance of a disputed figure keeps the finding it answers and accepts no other value."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from ..credit_resolution import CreditResolutionRecord, CreditResolutionState
from ..source_disagreement import SourceDisagreementRole
from .source_disagreement_support import sample_source_disagreement

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_AT = datetime(2026, 4, 2, 9, 0, tzinfo=UTC)
_SESSION = "automation-session-label"


def _record(**changes: object) -> CreditResolutionRecord:
    fact = sample_source_disagreement()
    fields: dict[str, object] = {
        "disagreement": fact,
        "accepted_role": fact.selected_role,
        "reason": "Synthetic reason: the certificate was checked against the payer's own copy.",
        "resolved_at": _AT,
        "resolved_by_session": _SESSION,
    }
    fields.update(changes)
    return CreditResolutionRecord.model_validate(fields)


def test_a_resolution_is_keyed_by_the_finding_it_answers_and_starts_active() -> None:
    record = _record()

    assert record.finding_key == record.disagreement.finding_key
    assert record.identity == ("100", 2025, "0A", record.disagreement.finding_key)
    assert record.state is CreditResolutionState.ACTIVE
    assert record.active
    assert record.revoked_at is None


def test_a_resolution_accepts_only_the_role_the_calculation_selected() -> None:
    other = SourceDisagreementRole.CROSS_CHECK
    assert other is not sample_source_disagreement().selected_role

    with pytest.raises(ValidationError, match="accepts the role the calculation selected"):
        _record(accepted_role=other)


@pytest.mark.parametrize("reason", ["", "   ", "\t\n"])
def test_a_resolution_without_a_reason_is_refused(reason: str) -> None:
    with pytest.raises(ValidationError):
        _record(reason=reason)


def test_a_revoked_resolution_keeps_when_and_by_whom_it_was_taken_back() -> None:
    later = _AT + timedelta(days=1)
    revoked = _record().revoked(later, by_session="other-session")

    assert revoked.state is CreditResolutionState.REVOKED
    assert not revoked.active
    assert (revoked.revoked_at, revoked.revoked_by_session) == (later, "other-session")
    assert revoked.resolved_at == _AT
    assert CreditResolutionRecord.model_validate_json(revoked.model_dump_json()) == revoked


@pytest.mark.parametrize(
    "changes",
    [
        {"state": CreditResolutionState.REVOKED},
        {"revoked_at": _AT + timedelta(days=1)},
        {"revoked_by_session": "other-session"},
        {
            "state": CreditResolutionState.REVOKED,
            "revoked_at": _AT - timedelta(seconds=1),
            "revoked_by_session": "other-session",
        },
    ],
    ids=["revoked-without-instant", "instant-without-state", "session-without-state", "revoked-before-resolved"],
)
def test_the_revocation_fields_are_present_exactly_when_revoked_and_never_before_the_resolution(
    changes: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        _record(**changes)
