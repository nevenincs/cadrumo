"""Tests for the :class:`BucketPointer` active-bucket pointer record."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .. import BucketPointer

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_json_round_trip() -> None:
    pointer = BucketPointer(bucket_id="bucket-001", schema_version=1)
    revived = BucketPointer.model_validate_json(pointer.model_dump_json())
    assert revived == pointer


def test_toml_round_trip() -> None:
    pointer = BucketPointer(bucket_id="bucket-001", schema_version=1)
    revived = BucketPointer.from_toml(pointer.to_toml())
    assert revived == pointer


def test_toml_round_trip_quoted_bucket_id() -> None:
    pointer = BucketPointer(bucket_id='bucket "weird" id', schema_version=2)
    revived = BucketPointer.from_toml(pointer.to_toml())
    assert revived == pointer


def test_rejects_empty_bucket_id() -> None:
    with pytest.raises(ValidationError):
        BucketPointer(bucket_id="", schema_version=1)


def test_rejects_non_positive_schema_version() -> None:
    invalid_version: int = 0
    with pytest.raises(ValidationError):
        BucketPointer(bucket_id="bucket-001", schema_version=invalid_version)


def test_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationError):
        BucketPointer.model_validate(
            {
                "bucket_id": "bucket-001",
                "schema_version": 1,
                "unexpected": "nope",
            },
        )


def test_from_toml_rejects_unknown_keys() -> None:
    text = 'bucket_id = "bucket-001"\nschema_version = 1\nrogue = "x"\n'
    with pytest.raises(ValidationError):
        BucketPointer.from_toml(text)


def test_from_toml_rejects_missing_bucket_id() -> None:
    with pytest.raises(ValidationError):
        BucketPointer.from_toml("schema_version = 1\n")
