"""Tests for :data:`aeat.core.identity.BucketId`.

Covers the four boundary properties the alias contract pins: a valid
value constructs cleanly, an empty value is rejected, a value longer
than 128 characters is rejected, and surrounding whitespace is stripped
on construction.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel, ValidationError

from .. import BucketId

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


class _Container(BaseModel):
    bucket_id: BucketId


class TestBucketIdConstraint:
    def test_accepts_valid_value(self) -> None:
        container = _Container(bucket_id="profile-7b9c-bucket")
        assert container.bucket_id == "profile-7b9c-bucket"

    def test_accepts_value_at_max_length(self) -> None:
        container = _Container(bucket_id="x" * 128)
        assert len(container.bucket_id) == 128

    def test_strips_surrounding_whitespace(self) -> None:
        container = _Container(bucket_id="  profile-bucket  ")
        assert container.bucket_id == "profile-bucket"

    @pytest.mark.parametrize(
        "bucket_id",
        (
            pytest.param("", id="empty"),
            pytest.param("x" * 129, id="too-long"),
            pytest.param("   ", id="whitespace-only"),
        ),
    )
    def test_rejects_invalid_value(self, bucket_id: str) -> None:
        with pytest.raises(ValidationError):
            _Container(bucket_id=bucket_id)
