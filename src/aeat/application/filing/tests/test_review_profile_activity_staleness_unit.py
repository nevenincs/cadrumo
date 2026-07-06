"""Unit coverage for profile-activity approval-basis fingerprints."""

from __future__ import annotations

import pytest

from .._review import _profile_activity_fingerprint, empty_profile_activity_fingerprint

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
