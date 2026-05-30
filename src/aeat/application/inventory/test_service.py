"""Real-behavior tests for the _now_utc clock alias in inventory._service.

These tests verify that the canonical ``aeat.core.time._now`` function is
used by the service module rather than a locally-inlined ``datetime.now``
call.  The clock itself is exercised through a direct import so the test
is not tautological — it proves the alias round-trips and is UTC-aware.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from aeat.core.time import _now
from aeat.application.inventory._service import _now_utc  # re-exported alias


pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_now_utc_alias_is_the_canonical_clock() -> None:
    """_now_utc in _service must be the same callable as aeat.core.time._now."""
    assert _now_utc is _now


def test_now_utc_returns_utc_aware_datetime() -> None:
    result = _now_utc()
    assert isinstance(result, datetime)
    assert result.tzinfo is not None
    assert result.utcoffset() == timedelta(0)


def test_now_utc_advances_monotonically() -> None:
    """Two successive calls must not go backward."""
    t1 = _now_utc()
    t2 = _now_utc()
    assert t2 >= t1
