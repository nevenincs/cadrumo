"""Validation contract tests for the operator profile identity aliases.

These primitives gate every profile / bucket reference that crosses
a persisted boundary; rejecting invalid inputs at construction is
the entire purpose of the typed alias.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from ..constants import ProfileName

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _ProfileNameHolder(BaseModel):
    """Single-field model used to exercise the alias's pydantic validators."""

    value: ProfileName


def test_profile_name_rejects_empty_or_whitespace() -> None:
    for invalid in ("", "   ", "\t"):
        with pytest.raises(ValidationError):
            _ProfileNameHolder(value=invalid)


def test_profile_name_rejects_overlong_input() -> None:
    too_long = "x" * 129
    with pytest.raises(ValidationError):
        _ProfileNameHolder(value=too_long)


def test_profile_name_accepts_typical_operator_inputs() -> None:
    for label in ("catering", "personal", "joan-translations", "test-bucket-01"):
        holder = _ProfileNameHolder(value=label)
        assert holder.value == label


def test_profile_name_strips_surrounding_whitespace() -> None:
    holder = _ProfileNameHolder(value="  catering  ")
    assert holder.value == "catering"
