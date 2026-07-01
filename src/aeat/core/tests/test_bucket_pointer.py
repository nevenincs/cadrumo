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
    for bucket_id, schema_version in (
        ("bucket-001", 1),
        ('bucket "weird" id', 2),
    ):
        pointer = BucketPointer(bucket_id=bucket_id, schema_version=schema_version)
        revived = BucketPointer.from_toml(pointer.to_toml())
        assert revived == pointer


def test_rejects_invalid_constructor_fields() -> None:
    for kwargs in (
        {"bucket_id": "", "schema_version": 1},
        {"bucket_id": "bucket-001", "schema_version": 0},
    ):
        with pytest.raises(ValidationError):
            BucketPointer(**kwargs)


def test_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationError):
        BucketPointer.model_validate(
            {
                "bucket_id": "bucket-001",
                "schema_version": 1,
                "unexpected": "nope",
            },
        )


def test_from_toml_rejects_invalid_payloads() -> None:
    for text in (
        'bucket_id = "bucket-001"\nschema_version = 1\nrogue = "x"\n',
        "schema_version = 1\n",
    ):
        with pytest.raises(ValidationError):
            BucketPointer.from_toml(text)
