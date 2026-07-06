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


@pytest.mark.parametrize(
    ("bucket_id", "expected"),
    (
        pytest.param("profile-7b9c-bucket", "profile-7b9c-bucket", id="label"),
        pytest.param("x" * 128, "x" * 128, id="max-length"),
        pytest.param("  profile-bucket  ", "profile-bucket", id="trimmed"),
    ),
)
def test_bucket_id_constraint_accepts_valid_values(bucket_id: str, expected: str) -> None:
    container = _Container(bucket_id=bucket_id)
    assert container.bucket_id == expected


@pytest.mark.parametrize(
    "bucket_id",
    (
        pytest.param("", id="empty"),
        pytest.param("x" * 129, id="too-long"),
        pytest.param("   ", id="blank-after-trim"),
    ),
)
def test_bucket_id_constraint_rejects_invalid_values(bucket_id: str) -> None:
    with pytest.raises(ValidationError):
        _Container(bucket_id=bucket_id)
