"""Real-behavior tests for the _now_utc clock alias in inventory._service.

These tests verify that the canonical ``cadrumo.core.time.now`` function is
used by the service module rather than a locally-inlined ``datetime.now``
call.  The clock itself is exercised through a direct import so the test
is not tautological — it proves the alias round-trips and is UTC-aware.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from ....core.time.clock import now
from ..service import _now_utc

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_now_utc_alias_is_the_canonical_clock() -> None:
    """_now_utc in _service must be the same callable as cadrumo.core.time.now."""
    assert _now_utc is now


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
