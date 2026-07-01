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
    def test_accepts_valid_values(self) -> None:
        cases = (
            ("profile-7b9c-bucket", "profile-7b9c-bucket"),
            ("x" * 128, "x" * 128),
            ("  profile-bucket  ", "profile-bucket"),
        )

        for bucket_id, expected in cases:
            container = _Container(bucket_id=bucket_id)
            assert container.bucket_id == expected

    def test_rejects_invalid_values(self) -> None:
        for bucket_id in ("", "x" * 129, "   "):
            with pytest.raises(ValidationError):
                _Container(bucket_id=bucket_id)
