"""Validation of the absolute session-cap Settings field.

`cadrumo_bucket_default_session_absolute_minutes` is the fallback absolute
session-lifetime cap (minutes) fixed at login when a bucket manifest omits
`session_absolute_minutes`. It defaults to 240 (4 h) and is validated to the
inclusive 60-720 range (12 h hard ceiling). These tests construct real
`Settings` instances and assert the boundary behaviour directly.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ..config import Settings

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FIELD = "cadrumo_bucket_default_session_absolute_minutes"


def test_absolute_cap_default_is_four_hours() -> None:
    assert getattr(Settings(), _FIELD) == 240


@pytest.mark.parametrize("value", [60, 240, 720])
def test_absolute_cap_accepts_in_range_values(value: int) -> None:
    assert getattr(Settings(**{_FIELD: value}), _FIELD) == value


@pytest.mark.parametrize("value", [0, 59, 721, 1_000])
def test_absolute_cap_rejects_out_of_range_values(value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(**{_FIELD: value})
