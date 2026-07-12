"""Real-behavior tests for :mod:`aeat.core.time._clock`."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ...config import override_settings
from ...errors import CoreValidationError
from .. import clock_is_frozen, frozen_clock, now

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_now_returns_recent_monotone_utc_datetime() -> None:
    before = datetime.now(tz=UTC)
    first = now()
    second = now()
    after = datetime.now(tz=UTC)

    assert isinstance(first, datetime)
    assert first.tzinfo is UTC
    assert before <= first <= second <= after
    offset = first.utcoffset()
    assert offset is not None
    assert offset.total_seconds() == 0


class TestFrozenClockSeam:
    """The deterministic-output clock seam: default-off, scoped, guarded."""

    _INSTANT = datetime(2026, 4, 14, 9, 30, 0, tzinfo=UTC)

    def test_default_off_returns_real_wall_clock(self) -> None:
        """Outside any scope, ``now()`` is real wall-clock — zero behaviour change."""
        assert not clock_is_frozen()
        before = datetime.now(tz=UTC)
        result = now()
        after = datetime.now(tz=UTC)
        assert before <= result <= after

    def test_frozen_scope_pins_now_to_the_instant(self) -> None:
        with frozen_clock(self._INSTANT) as yielded:
            assert yielded == self._INSTANT
            assert clock_is_frozen()
            assert now() == self._INSTANT
            # Repeated reads inside the scope are identical, not merely close.
            assert now() == now() == self._INSTANT

    def test_scope_restores_on_exit(self) -> None:
        with frozen_clock(self._INSTANT):
            assert now() == self._INSTANT
        assert not clock_is_frozen()
        assert now() != self._INSTANT

    def test_nested_scopes_restore_the_outer_instant(self) -> None:
        outer = datetime(2026, 1, 1, tzinfo=UTC)
        inner = datetime(2026, 12, 31, tzinfo=UTC)
        with frozen_clock(outer):
            assert now() == outer
            with frozen_clock(inner):
                assert now() == inner
            assert now() == outer

    def test_refuses_naive_instant(self) -> None:
        naive = datetime(2026, 4, 14, 9, 30, 0)  # deliberately tz-naive
        with pytest.raises(CoreValidationError), frozen_clock(naive):
            pass
        assert not clock_is_frozen()

    def test_refuses_under_live_test_opt_in(self) -> None:
        """The seam must stay off in live-marked test runs (no global freeze)."""
        with (
            override_settings(aeat_live_tests_enabled="1"),
            pytest.raises(CoreValidationError, match="live-test opt-in"),
            frozen_clock(self._INSTANT),
        ):
            pass
        # Guard did not leave a dangling frozen instant.
        assert not clock_is_frozen()

    def test_calc_sheets_utc_now_alias_follows_the_seam(self) -> None:
        """The calc-sheets ``_utc_now`` alias IS ``now``, so it freezes too."""
        from ....application.storage.calc_sheets._records import _utc_now

        assert _utc_now is now
        with frozen_clock(self._INSTANT):
            assert _utc_now() == self._INSTANT
