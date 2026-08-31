"""Real-behavior tests for the _utc_now clock alias in calc_sheets._records.

These tests verify that the canonical ``cadrumo.core.time.now`` function is
re-exported as ``_utc_now`` from ``_records`` rather than a locally-inlined
``datetime.now`` call.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from .....core.time.clock import now
from .._records import _utc_now

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_utc_now_alias_is_the_canonical_clock() -> None:
    """_utc_now exported from _records must be the same callable as cadrumo.core.time.now."""
    assert _utc_now is now


def test_utc_now_returns_utc_aware_datetime() -> None:
    result = _utc_now()
    assert isinstance(result, datetime)
    assert result.tzinfo is not None
    assert result.utcoffset() == timedelta(0)


def test_utc_now_advances_monotonically() -> None:
    t1 = _utc_now()
    t2 = _utc_now()
    assert t2 >= t1
