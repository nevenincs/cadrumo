"""Real-behavior tests for :mod:`aeat.core.time._clock`."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from aeat.core.time import now

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


class TestNow:
    def test_returns_utc_aware_datetime(self) -> None:
        result = now()
        assert isinstance(result, datetime)
        assert result.tzinfo is UTC

    def test_result_is_recent(self) -> None:
        before = datetime.now(tz=UTC)
        result = now()
        after = datetime.now(tz=UTC)
        assert before <= result <= after

    def test_successive_calls_are_monotone(self) -> None:
        first = now()
        second = now()
        assert second >= first

    def test_offset_is_zero(self) -> None:
        result = now()
        assert result.utcoffset() is not None
        assert result.utcoffset().total_seconds() == 0  # type: ignore[union-attr]
