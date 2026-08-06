"""Bundle schema-lineage gate and the shared payload validate path.

Companion to the storage-substrate lineage gate: the portable-bundle version
gate is a ceiling with a durability floor, the supported set is derived
from that range, and a future version bump without its registered one-hop
payload upgrader fails here instead of orphaning a taxpayer's exported
bundles.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from ....core import COMPATIBILITY_REGIME, RELEASED_FORMAT_FLOORS, expected_floor
from ....domain.user_profile import (
    UserProfileFact,
    UserProfilePortableExport,
    UserProfileRecord,
)
from .._bundle import (
    BUNDLE_DURABILITY_FLOOR,
    BUNDLE_PAYLOAD_UPGRADERS,
    BUNDLE_SCHEMA_VERSION,
    SUPPORTED_BUNDLE_SCHEMA_VERSIONS,
    UnsupportedBundleSchemaVersionError,
    validate_bundle_payload,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_INSTANT = datetime(2026, 7, 8, 9, 30, 0, tzinfo=UTC)
_BUCKET_ID = "88888888-8888-4888-8888-888888888888"


def _bundle(version: int) -> UserProfilePortableExport:
    return UserProfilePortableExport(
        bundle_schema_version=version,
        exported_at=_INSTANT,
        profile=UserProfileRecord(
            profile_id=_BUCKET_ID,
            display_name="Bundle lineage gate",
            facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
            created_at=_INSTANT,
            updated_at=_INSTANT,
        ),
    )


def test_bundle_upgrade_chain_is_complete_from_floor_to_current() -> None:
    """A bundle version bump without its payload upgrader fails here."""
    assert BUNDLE_DURABILITY_FLOOR <= BUNDLE_SCHEMA_VERSION
    missing = tuple(
        hop for hop in range(BUNDLE_DURABILITY_FLOOR, BUNDLE_SCHEMA_VERSION) if hop not in BUNDLE_PAYLOAD_UPGRADERS
    )
    assert missing == (), (
        f"BUNDLE_SCHEMA_VERSION was raised without registering one-hop payload upgraders for {missing}; "
        "land them in BUNDLE_PAYLOAD_UPGRADERS in the same change"
    )


def test_floor_matches_the_regime_expected_floor() -> None:
    """The bundle floor tracks the regime-switched compatibility policy.

    While ``PRE_RELEASE`` (today) the expected floor IS the current version,
    so this asserts the pre-release floors-chase-current posture: no released
    bundles exist below the current version, so the floor sits at it. Post-
    flip the expected floor becomes the frozen released value and this same
    assertion demands the floor stay pinned there.
    """
    assert (
        expected_floor(
            COMPATIBILITY_REGIME,
            "bundle",
            BUNDLE_SCHEMA_VERSION,
            RELEASED_FORMAT_FLOORS,
        )
        == BUNDLE_DURABILITY_FLOOR
    )


def test_supported_versions_is_the_floor_to_current_range() -> None:
    assert (
        frozenset(
            range(BUNDLE_DURABILITY_FLOOR, BUNDLE_SCHEMA_VERSION + 1),
        )
        == SUPPORTED_BUNDLE_SCHEMA_VERSIONS
    )


def test_validate_accepts_a_current_version_payload() -> None:
    bundle = _bundle(BUNDLE_SCHEMA_VERSION)
    assert validate_bundle_payload(bundle.model_dump_json()) == bundle


def test_validate_refuses_a_future_version_as_newer_application() -> None:
    payload = _bundle(BUNDLE_SCHEMA_VERSION).model_dump(mode="json")
    payload["bundle_schema_version"] = BUNDLE_SCHEMA_VERSION + 1
    with pytest.raises(UnsupportedBundleSchemaVersionError) as excinfo:
        validate_bundle_payload(json.dumps(payload))
    assert "newer application" in str(excinfo.value)
    assert excinfo.value.context == {
        "bundle_schema_version": str(BUNDLE_SCHEMA_VERSION + 1),
        "supported_versions": ",".join(str(v) for v in sorted(SUPPORTED_BUNDLE_SCHEMA_VERSIONS)),
    }


def test_validate_refuses_a_version_below_the_durability_floor() -> None:
    payload = _bundle(BUNDLE_SCHEMA_VERSION).model_dump(mode="json")
    payload["bundle_schema_version"] = BUNDLE_DURABILITY_FLOOR - 1
    with pytest.raises(UnsupportedBundleSchemaVersionError) as excinfo:
        validate_bundle_payload(json.dumps(payload))
    assert "is not supported" in str(excinfo.value)


def test_validate_refuses_a_payload_without_an_integer_version() -> None:
    payload = _bundle(BUNDLE_SCHEMA_VERSION).model_dump(mode="json")
    del payload["bundle_schema_version"]
    with pytest.raises(UnsupportedBundleSchemaVersionError):
        validate_bundle_payload(json.dumps(payload))


def test_validate_refuses_a_stamp_that_contradicts_the_transport_envelope() -> None:
    bundle = _bundle(BUNDLE_SCHEMA_VERSION)
    with pytest.raises(UnsupportedBundleSchemaVersionError) as excinfo:
        validate_bundle_payload(
            bundle.model_dump_json(),
            expected_written_version=BUNDLE_SCHEMA_VERSION + 1,
        )
    assert "transport envelope declares" in str(excinfo.value)
