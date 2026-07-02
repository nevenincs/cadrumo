"""Real-behavior tests for :mod:`aeat.core.time._utc`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from ...errors import CoreValidationError
from .. import coerce_utc_aware, validate_utc_aware

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_TZ_PLUS2 = timezone(timedelta(hours=2))
_TZ_MINUS5 = timezone(timedelta(hours=-5))

_NAIVE = datetime(2024, 6, 15, 12, 0, 0)
_UTC_AWARE = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
_PLUS2_AWARE = datetime(2024, 6, 15, 14, 0, 0, tzinfo=_TZ_PLUS2)
_MINUS5_AWARE = datetime(2024, 6, 15, 7, 0, 0, tzinfo=_TZ_MINUS5)


def test_utc_helpers_coerce_or_validate_utc_aware_datetime_inputs() -> None:
    cases = (
        ("naive", _NAIVE, _UTC_AWARE),
        ("utc-aware", _UTC_AWARE, _UTC_AWARE),
        ("plus-two", _PLUS2_AWARE, _UTC_AWARE),
        ("minus-five", _MINUS5_AWARE, _UTC_AWARE),
    )

    for label, value, expected_utc in cases:
        result = coerce_utc_aware(value)
        assert isinstance(result, datetime), label
        assert result == expected_utc, label
        assert result.tzinfo is UTC, label

    accepted = validate_utc_aware(_UTC_AWARE)
    assert accepted is _UTC_AWARE

    invalid_cases = (
        ("naive", _NAIVE, "timezone-aware"),
        ("plus-two", _PLUS2_AWARE, "UTC"),
        ("minus-five", _MINUS5_AWARE, "UTC"),
    )

    for label, value, expected_match in invalid_cases:
        with pytest.raises(CoreValidationError, match=expected_match) as exc_info:
            validate_utc_aware(value)
        assert isinstance(exc_info.value, ValueError), label
