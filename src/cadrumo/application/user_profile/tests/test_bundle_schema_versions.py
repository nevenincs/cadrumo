"""Version-gate contracts for portable profile bundles."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....domain.user_profile import (
    UserProfileFact,
    UserProfilePortableExport,
    UserProfileRecord,
)
from .._bundle import (
    BUNDLE_SCHEMA_VERSION,
    UnsupportedBundleSchemaVersionError,
    deserialize_profile_bundle,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_INSTANT = datetime(2026, 6, 30, 10, 30, 0, tzinfo=UTC)
_BUCKET_ID = "99999999-9999-4999-8999-999999999999"


def _profile() -> UserProfileRecord:
    return UserProfileRecord(
        profile_id=_BUCKET_ID,
        display_name="Bundle schema gate",
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
        created_at=_INSTANT,
        updated_at=_INSTANT,
    )


def test_deserialize_profile_bundle_refuses_v2_shape() -> None:
    bundle = UserProfilePortableExport(
        bundle_schema_version=2,
        exported_at=_INSTANT,
        profile=_profile(),
    )

    with pytest.raises(UnsupportedBundleSchemaVersionError) as excinfo:
        deserialize_profile_bundle(bundle, target_bucket_id=_BUCKET_ID)

    assert "bundle_schema_version 2 is not supported" in str(excinfo.value)
    assert f"supported version: {BUNDLE_SCHEMA_VERSION}" in str(excinfo.value)
