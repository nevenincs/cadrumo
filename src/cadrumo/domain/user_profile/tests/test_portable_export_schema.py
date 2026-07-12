"""Schema contracts for the v3 portable-export payload."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from types import MappingProxyType

import pytest
from pydantic import ValidationError

from ....core.classification import SensitivityClass
from .._portable_export import CarriedSecureObject, CoverageManifest, UserProfilePortableExport
from .._values import UserProfileFact, UserProfileRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_INSTANT = datetime(2026, 6, 30, 10, 0, 0, tzinfo=UTC)
_BUCKET_ID = "88888888-8888-4888-8888-888888888888"
_OBJECT_KEY = "catalogue"
_BINARY_PAYLOAD = b"\x00not-json\xffattachment-bytes"
_BINARY_PAYLOAD_B64 = base64.b64encode(_BINARY_PAYLOAD).decode("ascii")


def _profile() -> UserProfileRecord:
    return UserProfileRecord(
        profile_id=_BUCKET_ID,
        display_name="Portable schema",
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
        created_at=_INSTANT,
        updated_at=_INSTANT,
    )


def test_portable_export_v3_defaults_keep_empty_custody_fields_json_valid() -> None:
    bundle = UserProfilePortableExport(profile=_profile(), exported_at=_INSTANT)

    assert bundle.bundle_schema_version == 3
    assert bundle.carried_objects == ()
    assert bundle.coverage_manifest == CoverageManifest()

    reloaded = UserProfilePortableExport.model_validate_json(bundle.model_dump_json())
    assert reloaded.bundle_schema_version == 3
    assert reloaded.profile == bundle.profile
    assert reloaded.carried_objects == ()
    assert reloaded.coverage_manifest == CoverageManifest()


def test_carried_secure_object_and_coverage_manifest_round_trip_binary_payload() -> None:
    carried = CarriedSecureObject(
        namespace="cadrumo.domain.buckets.event_history",
        object_key=_OBJECT_KEY,
        classification=SensitivityClass.FINANCIAL,
        schema_version=1,
        written_at=_INSTANT,
        payload_b64=_BINARY_PAYLOAD_B64,
    )
    coverage = CoverageManifest(
        custody_profile="full",
        carried_namespaces=("cadrumo.domain.buckets.event_history",),
        row_counts_by_namespace={"cadrumo.domain.buckets.event_history": 1},
    )

    bundle = UserProfilePortableExport(
        profile=_profile(),
        exported_at=_INSTANT,
        carried_objects=(carried,),
        coverage_manifest=coverage,
    )

    reloaded = UserProfilePortableExport.model_validate_json(bundle.model_dump_json())

    assert reloaded.carried_objects == (carried,)
    assert reloaded.carried_objects[0].object_key == _OBJECT_KEY
    assert reloaded.carried_objects[0].payload == _BINARY_PAYLOAD
    assert reloaded.coverage_manifest.custody_profile == "full"
    assert reloaded.coverage_manifest.carried_namespaces == ("cadrumo.domain.buckets.event_history",)
    assert reloaded.coverage_manifest.row_counts_by_namespace["cadrumo.domain.buckets.event_history"] == 1


def test_portable_export_schema_rejects_extra_fields_and_is_frozen() -> None:
    with pytest.raises(ValidationError, match="extra_forbidden"):
        UserProfilePortableExport.model_validate(
            {
                "profile": _profile(),
                "unexpected": True,
            },
        )

    bundle = UserProfilePortableExport(profile=_profile(), exported_at=_INSTANT)
    with pytest.raises(ValidationError, match="frozen"):
        bundle.bundle_schema_version = 4


def test_carried_secure_object_rejects_invalid_fields() -> None:
    cases = (
        (_OBJECT_KEY, "{not-base64", "payload_b64 must be canonical base64"),
        ("   ", _BINARY_PAYLOAD_B64, None),
    )

    for object_key, payload_b64, expected_message in cases:
        with pytest.raises(ValidationError, match=expected_message):
            CarriedSecureObject(
                namespace="cadrumo.domain.buckets.event_history",
                object_key=object_key,
                classification=SensitivityClass.FINANCIAL,
                schema_version=1,
                written_at=_INSTANT,
                payload_b64=payload_b64,
            )


def test_coverage_manifest_rejects_negative_row_counts() -> None:
    with pytest.raises(ValidationError, match="row counts must be non-negative"):
        CoverageManifest(
            carried_namespaces=("cadrumo.domain.buckets.event_history",),
            row_counts_by_namespace={"cadrumo.domain.buckets.event_history": -1},
        )


def test_coverage_manifest_row_counts_are_immutable_after_default_and_validation() -> None:
    manifests = (
        CoverageManifest(),
        CoverageManifest(row_counts_by_namespace={"cadrumo.domain.buckets.event_history": 1}),
    )

    for manifest in manifests:
        assert isinstance(manifest.row_counts_by_namespace, MappingProxyType)
        # Immutability is the absence of a mutation method, not a raised exception
        # from one: mappingproxy exposes no `__setitem__` at all, so item
        # assignment (`obj[key] = value`) has no dispatch target to reach.
        assert not hasattr(manifest.row_counts_by_namespace, "__setitem__")
