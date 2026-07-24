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


def test_absolute_cap_default_is_four_hours() -> None:
    assert Settings().cadrumo_bucket_default_session_absolute_minutes == 240


@pytest.mark.parametrize("value", [60, 240, 720])
def test_absolute_cap_accepts_in_range_values(value: int) -> None:
    settings = Settings(cadrumo_bucket_default_session_absolute_minutes=value)
    assert settings.cadrumo_bucket_default_session_absolute_minutes == value


@pytest.mark.parametrize("value", [0, 59, 721, 1_000])
def test_absolute_cap_rejects_out_of_range_values(value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(cadrumo_bucket_default_session_absolute_minutes=value)
