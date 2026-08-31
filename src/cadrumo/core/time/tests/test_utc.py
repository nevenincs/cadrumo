"""Real-behavior tests for :mod:`~core.time.utc`.

These cases pin the two explicit UTC policies exported by
:mod:`~core.time`: :func:`~core.time.coerce_utc_aware` may normalise naive or
offset-aware datetimes to UTC, while :func:`~core.time.validate_utc_aware`
refuses naive or non-UTC values with :class:`~core.errors.CoreValidationError`.

See Also:
    :mod:`~core.time.utc`
        Canonical UTC helper implementation under test.
    :mod:`~core.time.clock`
        Adjacent wall-clock seam that produces UTC-aware ``now`` values.
    :class:`~datetime.datetime`
        Runtime value type whose ``tzinfo`` and offset semantics are exercised.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from ...errors.hierarchy import CoreValidationError
from ..utc import coerce_utc_aware, validate_utc_aware

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_TZ_PLUS2 = timezone(timedelta(hours=2))
_TZ_MINUS5 = timezone(timedelta(hours=-5))

_NAIVE = datetime(2024, 6, 15, 12, 0, 0)
_UTC_AWARE = datetime(2024, 6, 15, 12, 0, 0, tzinfo=UTC)
_PLUS2_AWARE = datetime(2024, 6, 15, 14, 0, 0, tzinfo=_TZ_PLUS2)
_MINUS5_AWARE = datetime(2024, 6, 15, 7, 0, 0, tzinfo=_TZ_MINUS5)


@pytest.mark.parametrize(
    ("value", "expected_utc"),
    (
        pytest.param(_NAIVE, _UTC_AWARE, id="naive"),
        pytest.param(_UTC_AWARE, _UTC_AWARE, id="utc-aware"),
        pytest.param(_PLUS2_AWARE, _UTC_AWARE, id="plus-two"),
        pytest.param(_MINUS5_AWARE, _UTC_AWARE, id="minus-five"),
    ),
)
def test_coerce_utc_aware_datetime_inputs(value: datetime, expected_utc: datetime) -> None:
    result = coerce_utc_aware(value)

    assert isinstance(result, datetime)
    assert result == expected_utc
    assert result.tzinfo is UTC


def test_validate_utc_aware_accepts_utc_datetime() -> None:
    accepted = validate_utc_aware(_UTC_AWARE)

    assert accepted is _UTC_AWARE


@pytest.mark.parametrize(
    ("value", "expected_match"),
    (
        pytest.param(_NAIVE, "timezone-aware", id="naive"),
        pytest.param(_PLUS2_AWARE, "UTC", id="plus-two"),
        pytest.param(_MINUS5_AWARE, "UTC", id="minus-five"),
    ),
)
def test_validate_utc_aware_rejects_non_utc_or_naive(
    value: datetime,
    expected_match: str,
) -> None:
    with pytest.raises(CoreValidationError, match=expected_match) as exc_info:
        validate_utc_aware(value)

    assert isinstance(exc_info.value, ValueError)
