"""Absolute-cap enforcement for `BucketSession`.

A `BucketSession` holds an immutable absolute-lifetime deadline fixed at
`open()`; `touch()` clamps the sliding idle deadline to it, and both
`is_expired` and `evaluate_idle` enforce the earlier of the idle window and
the absolute cap. These tests drive a real clock forward past the cap while
touching *within* the idle window, proving a continuously-active session
still seals at the absolute cap rather than living forever.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ...errors import StorageValidationError
from ..bucket_session import DEFAULT_SESSION_ABSOLUTE_MINUTES, BucketSession
from ..idle_timeout import evaluate_idle

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


_NOW = datetime(2026, 7, 24, 12, 0, 0, tzinfo=UTC)
_KEK = bytes(range(32))
_DEK = bytes(range(32, 64))
_BUCKET_ID = "88888888-8888-4888-8888-888888888888"


def _open(*, idle_minutes: int, absolute_minutes: int | None) -> BucketSession:
    return BucketSession.open(
        bucket_id=_BUCKET_ID,
        kek=_KEK,
        dek=_DEK,
        idle_minutes=idle_minutes,
        absolute_minutes=absolute_minutes,
        opened_at=_NOW,
    )


def test_absolute_deadline_is_fixed_at_open() -> None:
    session = _open(idle_minutes=5, absolute_minutes=20)
    assert session.opened_at == _NOW
    assert session.absolute_deadline == _NOW + timedelta(minutes=20)


def test_default_absolute_cap_applies_when_unset() -> None:
    session = _open(idle_minutes=15, absolute_minutes=None)
    assert session.absolute_deadline == _NOW + timedelta(minutes=DEFAULT_SESSION_ABSOLUTE_MINUTES)


def test_continuously_touched_session_still_seals_at_absolute_cap() -> None:
    session = _open(idle_minutes=5, absolute_minutes=20)

    # Touch well within the 5-minute idle window on every step; the session
    # stays alive right up to — but not past — the 20-minute absolute cap.
    for minute in (4, 8, 12, 16):
        now = _NOW + timedelta(minutes=minute)
        session.touch(now)
        assert session.is_expired(now) is False
        assert evaluate_idle(session=session, now=now, configured_minutes=5).expired is False

    # A touch at the cap can only clamp the idle deadline back to the (now
    # reached) absolute deadline: the session seals despite continuous activity.
    at_cap = _NOW + timedelta(minutes=20)
    session.touch(at_cap)
    assert session.idle_deadline == session.absolute_deadline
    assert session.is_expired(at_cap) is True
    assert evaluate_idle(session=session, now=at_cap, configured_minutes=5).expired is True

    # And it stays sealed beyond the cap no matter how often it is touched.
    beyond = _NOW + timedelta(minutes=24)
    session.touch(beyond)
    assert session.is_expired(beyond) is True
    assert evaluate_idle(session=session, now=beyond, configured_minutes=5).expired is True


def test_touch_clamps_idle_deadline_to_absolute_deadline() -> None:
    session = _open(idle_minutes=5, absolute_minutes=20)

    # A touch two minutes before the cap would push the idle deadline to
    # opened+23, which is past the cap; it must clamp to the cap instead.
    session.touch(_NOW + timedelta(minutes=18))
    assert session.idle_deadline == session.absolute_deadline


def test_initial_idle_deadline_clamped_when_window_exceeds_cap() -> None:
    # An idle window wider than the absolute cap is born already bounded by it.
    session = _open(idle_minutes=90, absolute_minutes=60)
    assert session.idle_deadline == session.absolute_deadline == _NOW + timedelta(minutes=60)


def test_evaluate_idle_reports_absolute_cap_as_the_binding_deadline() -> None:
    session = _open(idle_minutes=15, absolute_minutes=20)
    # Touch two minutes before the cap: absent the cap the idle deadline would
    # roll to opened+33, but it clamps to the cap at opened+20. evaluate_idle
    # therefore reports the cap (2 minutes remaining), not the idle window.
    touched_at = _NOW + timedelta(minutes=18)
    session.touch(touched_at)
    evaluation = evaluate_idle(session=session, now=touched_at, configured_minutes=15)
    assert evaluation.expired is False
    assert evaluation.remaining_seconds == 2 * 60


def test_open_rejects_non_positive_absolute_minutes() -> None:
    with pytest.raises(StorageValidationError, match="absolute_minutes must be a strict positive integer"):
        _open(idle_minutes=5, absolute_minutes=0)
