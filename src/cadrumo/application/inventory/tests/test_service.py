"""Real-behavior tests for the canonical inventory clock.

The clock is exercised through a direct import and proved UTC-aware.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from ....core.time.clock import now

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_now_utc_returns_utc_aware_datetime() -> None:
    result = now()
    assert isinstance(result, datetime)
    assert result.tzinfo is not None
    assert result.utcoffset() == timedelta(0)


def test_now_utc_advances_monotonically() -> None:
    """Two successive calls must not go backward."""
    t1 = now()
    t2 = now()
    assert t2 >= t1
