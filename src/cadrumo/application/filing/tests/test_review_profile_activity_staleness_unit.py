"""Unit coverage for profile-activity approval-basis fingerprints.

See Also:
    :func:`~application.filing.draft_review._profile_activity_fingerprint`
        Order-independent digest helper under test for relation-scoping profile
        facts.
    :func:`~application.filing.empty_profile_activity_fingerprint`
        Public empty-surface sentinel compared against the private digest
        helper.
    :class:`~application.filing.ModeloApprovalStaleReason`
        Staleness reason enum whose ``PROFILE_ACTIVITY_CHANGED`` member is fed
        by this fingerprint.
"""

from __future__ import annotations

import pytest

from ..draft_review import _profile_activity_fingerprint, empty_profile_activity_fingerprint

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_profile_activity_fingerprint_changes_when_a_fact_changes() -> None:
    before = _profile_activity_fingerprint({"censo.activity_start_date": "2024-01-01"})
    after = _profile_activity_fingerprint({"censo.activity_start_date": "2024-06-01"})

    assert before != after


def test_profile_activity_fingerprint_is_order_independent() -> None:
    one = _profile_activity_fingerprint({"a.b": "1", "c.d": "2"})
    other = _profile_activity_fingerprint({"c.d": "2", "a.b": "1"})

    assert one == other


def test_profile_activity_fingerprint_distinguishes_empty_from_populated() -> None:
    empty = _profile_activity_fingerprint(None)
    populated = _profile_activity_fingerprint({"censo.activity_start_date": "2024-01-01"})

    assert empty != populated
    assert empty == empty_profile_activity_fingerprint()
    assert empty == _profile_activity_fingerprint({})
