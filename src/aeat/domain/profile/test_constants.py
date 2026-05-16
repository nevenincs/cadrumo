"""Validation contract tests for the operator profile identity aliases.

These primitives gate every profile / bucket reference that crosses
a persisted boundary; rejecting invalid inputs at construction is
the entire purpose of the typed alias.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from aeat.domain.profile import BucketId, ProfileName

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


class _ProfileNameHolder(BaseModel):
    """Single-field model used to exercise the alias's pydantic validators."""

    value: ProfileName


class _BucketIdHolder(BaseModel):
    """Single-field model used to exercise the alias's pydantic validators."""

    value: BucketId


@pytest.mark.parametrize("invalid", ["", "   ", "\t"])
def test_profile_name_rejects_empty_or_whitespace(invalid: str) -> None:
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


@pytest.mark.parametrize("invalid", ["", "   ", "\t"])
def test_bucket_id_rejects_empty_or_whitespace(invalid: str) -> None:
    with pytest.raises(ValidationError):
        _BucketIdHolder(value=invalid)


def test_bucket_id_rejects_overlong_input() -> None:
    too_long = "x" * 129
    with pytest.raises(ValidationError):
        _BucketIdHolder(value=too_long)


def test_bucket_id_accepts_profile_name_values() -> None:
    """ProfileName and BucketId share their constraint by ADR mandate (1:1)."""

    holder = _BucketIdHolder(value="catering")
    assert holder.value == "catering"


def test_profile_name_and_bucket_id_share_constraint() -> None:
    """Construction parity: any valid ProfileName is a valid BucketId."""

    label = "joan-personal"
    p = _ProfileNameHolder(value=label)
    b = _BucketIdHolder(value=label)
    assert p.value == b.value == label
