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

    def test_rejects_empty_value(self) -> None:
        with pytest.raises(ValidationError):
            _Container(bucket_id="")

    def test_rejects_value_longer_than_max(self) -> None:
        with pytest.raises(ValidationError):
            _Container(bucket_id="x" * 129)

    def test_accepts_value_at_max_length(self) -> None:
        container = _Container(bucket_id="x" * 128)
        assert len(container.bucket_id) == 128

    def test_strips_surrounding_whitespace(self) -> None:
        container = _Container(bucket_id="  profile-bucket  ")
        assert container.bucket_id == "profile-bucket"

    def test_rejects_whitespace_only_value_after_strip(self) -> None:
        with pytest.raises(ValidationError):
            _Container(bucket_id="   ")
