"""Real-behavior tests for the canonical calc-sheets clock."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from .....core.time.clock import now

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_utc_now_returns_utc_aware_datetime() -> None:
    result = now()
    assert isinstance(result, datetime)
    assert result.tzinfo is not None
    assert result.utcoffset() == timedelta(0)


def test_utc_now_advances_monotonically() -> None:
    t1 = now()
    t2 = now()
    assert t2 >= t1
