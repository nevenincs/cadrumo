"""Real payload-boundary tests for portable bundle schema versions."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from ....domain.user_profile import UserProfileFact, UserProfilePortableExport, UserProfileRecord
from .._bundle import (
    BUNDLE_SCHEMA_VERSION,
    UnsupportedBundleSchemaVersionError,
    validate_bundle_payload,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_INSTANT = datetime(2026, 7, 8, 9, 30, 0, tzinfo=UTC)
_BUCKET_ID = "88888888-8888-4888-8888-888888888888"


def _bundle() -> UserProfilePortableExport:
    return UserProfilePortableExport(
        bundle_schema_version=BUNDLE_SCHEMA_VERSION,
        exported_at=_INSTANT,
        profile=UserProfileRecord(
            profile_id=_BUCKET_ID,
            display_name="Bundle version boundary",
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            created_at=_INSTANT,
            updated_at=_INSTANT,
        ),
    )


def test_validate_accepts_a_current_version_payload() -> None:
    bundle = _bundle()
    assert validate_bundle_payload(bundle.model_dump_json()) == bundle


def test_validate_refuses_a_future_version_as_newer_application() -> None:
    payload = _bundle().model_dump(mode="json")
    payload["bundle_schema_version"] = BUNDLE_SCHEMA_VERSION + 1
    with pytest.raises(UnsupportedBundleSchemaVersionError) as excinfo:
        validate_bundle_payload(json.dumps(payload))
    assert "newer application" in str(excinfo.value)
    assert excinfo.value.context == {
        "bundle_schema_version": str(BUNDLE_SCHEMA_VERSION + 1),
        "supported_versions": str(BUNDLE_SCHEMA_VERSION),
    }


def test_validate_refuses_a_pre_current_version_without_migration() -> None:
    payload = _bundle().model_dump(mode="json")
    payload["bundle_schema_version"] = BUNDLE_SCHEMA_VERSION - 1
    with pytest.raises(UnsupportedBundleSchemaVersionError) as excinfo:
        validate_bundle_payload(json.dumps(payload))
    assert f"supported version: {BUNDLE_SCHEMA_VERSION}" in str(excinfo.value)
    assert excinfo.value.context == {
        "bundle_schema_version": str(BUNDLE_SCHEMA_VERSION - 1),
        "supported_versions": str(BUNDLE_SCHEMA_VERSION),
    }


def test_validate_refuses_a_payload_without_an_integer_version() -> None:
    payload = _bundle().model_dump(mode="json")
    del payload["bundle_schema_version"]
    with pytest.raises(UnsupportedBundleSchemaVersionError):
        validate_bundle_payload(json.dumps(payload))


def test_validate_refuses_a_stamp_that_contradicts_the_transport_envelope() -> None:
    bundle = _bundle()
    with pytest.raises(UnsupportedBundleSchemaVersionError) as excinfo:
        validate_bundle_payload(
            bundle.model_dump_json(),
            expected_written_version=BUNDLE_SCHEMA_VERSION + 1,
        )
    assert "transport envelope declares" in str(excinfo.value)
