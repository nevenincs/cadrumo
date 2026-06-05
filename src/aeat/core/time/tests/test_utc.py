"""Real-behavior tests for :mod:`aeat.core.time._utc`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from ...errors import CoreValidationError
from .. import coerce_utc_aware, validate_utc_aware

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TZ_PLUS2 = timezone(timedelta(hours=2))
_TZ_MINUS5 = timezone(timedelta(hours=-5))

_NAIVE = datetime(2024, 6, 15, 12, 0, 0)
_UTC_AWARE = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
_PLUS2_AWARE = datetime(2024, 6, 15, 14, 0, 0, tzinfo=_TZ_PLUS2)
_MINUS5_AWARE = datetime(2024, 6, 15, 7, 0, 0, tzinfo=_TZ_MINUS5)


# ---------------------------------------------------------------------------
# coerce_utc_aware
# ---------------------------------------------------------------------------


class TestCoerceUtcAware:
    def test_naive_becomes_utc_aware(self) -> None:
        result = coerce_utc_aware(_NAIVE)
        assert result.tzinfo is UTC
        assert result.replace(tzinfo=None) == _NAIVE

    def test_utc_aware_returned_unchanged(self) -> None:
        result = coerce_utc_aware(_UTC_AWARE)
        assert result == _UTC_AWARE
        assert result.tzinfo is UTC

    @pytest.mark.parametrize(
        "aware_dt, expected_utc",
        [
            (_PLUS2_AWARE, datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)),
            (_MINUS5_AWARE, datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)),
        ],
    )
    def test_offset_aware_converted_to_utc(self, aware_dt: datetime, expected_utc: datetime) -> None:
        result = coerce_utc_aware(aware_dt)
        assert result == expected_utc
        assert result.tzinfo is UTC

    def test_return_type_is_datetime(self) -> None:
        result = coerce_utc_aware(_NAIVE)
        assert isinstance(result, datetime)


# ---------------------------------------------------------------------------
# validate_utc_aware
# ---------------------------------------------------------------------------


class TestValidateUtcAware:
    def test_utc_aware_passes_through(self) -> None:
        result = validate_utc_aware(_UTC_AWARE)
        assert result is _UTC_AWARE

    def test_naive_raises_core_validation_error(self) -> None:
        with pytest.raises(CoreValidationError, match="timezone-aware"):
            validate_utc_aware(_NAIVE)

    @pytest.mark.parametrize(
        "non_utc_dt",
        [_PLUS2_AWARE, _MINUS5_AWARE],
        ids=["plus2", "minus5"],
    )
    def test_non_utc_aware_raises_core_validation_error(self, non_utc_dt: datetime) -> None:
        with pytest.raises(CoreValidationError, match="UTC"):
            validate_utc_aware(non_utc_dt)

    def test_raised_error_is_also_value_error(self) -> None:
        # CoreValidationError inherits from ValueError for pydantic compat.
        with pytest.raises(ValueError):
            validate_utc_aware(_NAIVE)
