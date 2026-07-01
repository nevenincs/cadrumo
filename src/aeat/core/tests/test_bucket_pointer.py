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


@pytest.mark.parametrize(
    ("bucket_id", "schema_version"),
    (
        pytest.param("bucket-001", 1, id="simple"),
        pytest.param('bucket "weird" id', 2, id="quoted-bucket-id"),
    ),
)
def test_toml_round_trip(bucket_id: str, schema_version: int) -> None:
    pointer = BucketPointer(bucket_id=bucket_id, schema_version=schema_version)
    revived = BucketPointer.from_toml(pointer.to_toml())
    assert revived == pointer


@pytest.mark.parametrize(
    "kwargs",
    (
        pytest.param({"bucket_id": "", "schema_version": 1}, id="empty-bucket-id"),
        pytest.param({"bucket_id": "bucket-001", "schema_version": 0}, id="non-positive-schema-version"),
    ),
)
def test_rejects_invalid_constructor_fields(kwargs: dict[str, object]) -> None:
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


@pytest.mark.parametrize(
    "text",
    (
        pytest.param('bucket_id = "bucket-001"\nschema_version = 1\nrogue = "x"\n', id="unknown-key"),
        pytest.param("schema_version = 1\n", id="missing-bucket-id"),
    ),
)
def test_from_toml_rejects_invalid_payloads(text: str) -> None:
    with pytest.raises(ValidationError):
        BucketPointer.from_toml(text)
