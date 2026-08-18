"""Schema contracts for the v3 portable-export payload."""

from __future__ import annotations

import base64
from datetime import UTC, date, datetime
from types import MappingProxyType

import pytest
from pydantic import ValidationError

from ....core.classification import SensitivityClass
from ....core.external_constants import PROVENANCE_SOURCE_CENSO_ARTEFACT
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from .._portable_export import CarriedSecureObject, CoverageManifest, UserProfilePortableExport

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: The shape these tests describe, stated once rather than at each call site.
#: It is a fixture value, NOT a mirror of the production write version: the
#: model deliberately has no default, because the current write version belongs
#: to the bundle lineage that also owns the floor and the upgraders, and this
#: layer cannot see it. A detector for the two disagreeing is being built
#: separately; until it exists, this constant pins the shape under test and
#: claims nothing about what production stamps.
_SHAPE_UNDER_TEST = 3
_INSTANT = datetime(2026, 6, 30, 10, 0, 0, tzinfo=UTC)
_BUCKET_ID = "88888888-8888-4888-8888-888888888888"
_OBJECT_KEY = "catalogue"
_BINARY_PAYLOAD = b"\x00not-json\xffattachment-bytes"
_BINARY_PAYLOAD_B64 = base64.b64encode(_BINARY_PAYLOAD).decode("ascii")


def _profile() -> UserProfileRecord:
    return UserProfileRecord(setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET_ID,
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
        created_at=_INSTANT,
        updated_at=_INSTANT,
    )


def _campaign_record() -> UserProfileRecord:
    """A record populated with EVERY schema surface the setup flow added.

    The setup flow added three persisted surfaces: the
    ``censo.divergencia.{n}.*`` cotejo divergence rows, the
    ``renta_family.descendiente.{n}.*`` descendant extensions, and the
    ``INCOMPLETE`` setup state. All three are carried by the
    :class:`UserProfileRecord` -- as ordinary ``UserProfileFact`` rows and
    the ``setup_state`` field -- never by a change to the export model's own
    shape.
    Defaultable fact fields are populated non-default (a censo-artefact
    ``source`` and a real effective-dated window) so a save-drops-field
    regression would break the strict equality the roundtrip asserts.
    """
    return UserProfileRecord(
        profile_id=_BUCKET_ID,
        setup_state=ProfileSetupState.INCOMPLETE,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(
                path="censo.divergencia.0.axis",
                value="activities.description",
                source=PROVENANCE_SOURCE_CENSO_ARTEFACT,
                valid_from=date(2026, 1, 1),
                valid_to=date(2026, 12, 31),
            ),
            UserProfileFact(
                path="censo.divergencia.0.artefact_value",
                value="Consultoria informatica",
                source=PROVENANCE_SOURCE_CENSO_ARTEFACT,
            ),
            UserProfileFact(
                path="censo.divergencia.0.source",
                value=PROVENANCE_SOURCE_CENSO_ARTEFACT,
                source=PROVENANCE_SOURCE_CENSO_ARTEFACT,
            ),
            UserProfileFact(path="renta_family.descendiente.0.birth_date", value="2020-01-15"),
            UserProfileFact(path="renta_family.descendiente.0.custodia_compartida", value="true"),
            UserProfileFact(path="renta_family.descendiente.0.discapacidad", value="65"),
        ),
        created_at=_INSTANT,
        updated_at=_INSTANT,
    )


def test_portable_export_carries_campaign_schema_additions_at_v3() -> None:
    """The export subsumes every recent schema addition with no version bump.

    Because ``UserProfilePortableExport`` composes the
    whole :class:`UserProfileRecord` through the ``profile`` field and pydantic
    serialises it generically, the new divergence facts, descendant facts, and
    the ``INCOMPLETE`` setup state flow through structurally. Under the
    PRE_RELEASE compatibility regime this means no ``bundle_schema_version``
    bump is warranted -- the same v3 bundle round-trips the new surfaces with
    strict equality, and the setup state survives (a dropped state would
    re-default to ``COMPLETE`` and fail the identity check).
    """
    record = _campaign_record()
    bundle = UserProfilePortableExport(bundle_schema_version=_SHAPE_UNDER_TEST, profile=record, exported_at=_INSTANT)
    assert bundle.bundle_schema_version == 3

    reloaded = UserProfilePortableExport.model_validate_json(bundle.model_dump_json())

    assert reloaded.bundle_schema_version == 3
    assert reloaded.profile == record
    assert reloaded.profile.setup_state is ProfileSetupState.INCOMPLETE
    reloaded_paths = {fact.path for fact in reloaded.profile.facts}
    assert "censo.divergencia.0.artefact_value" in reloaded_paths
    assert "renta_family.descendiente.0.discapacidad" in reloaded_paths


def test_portable_export_campaign_roundtrip_is_not_tautological() -> None:
    """Anti-tautology for the export boundary: mangling the payload strictly differs.

    Serialises the campaign record, corrupts one persisted divergence fact
    value in the JSON bytes, then re-parses: the reloaded profile must differ
    from the original, proving the roundtrip equality above reflects the
    serialised payload rather than passing regardless. If the boundary were
    tautological the mangled bundle would still compare equal.
    """
    record = _campaign_record()
    payload = UserProfilePortableExport(
        bundle_schema_version=_SHAPE_UNDER_TEST, profile=record, exported_at=_INSTANT
    ).model_dump_json()

    mangled = payload.replace("Consultoria informatica", "Corrupted on the wire")
    assert "Corrupted on the wire" in mangled, "payload mutation did not apply"

    with pytest.raises(ValidationError, match="content digest does not match"):
        UserProfilePortableExport.model_validate_json(mangled)


def test_portable_export_v3_defaults_keep_empty_custody_fields_json_valid() -> None:
    bundle = UserProfilePortableExport(
        bundle_schema_version=_SHAPE_UNDER_TEST, profile=_profile(), exported_at=_INSTANT
    )

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
        bundle_schema_version=_SHAPE_UNDER_TEST,
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

    bundle = UserProfilePortableExport(
        bundle_schema_version=_SHAPE_UNDER_TEST, profile=_profile(), exported_at=_INSTANT
    )
    with pytest.raises(ValidationError, match="frozen"):
        bundle.bundle_schema_version = 4


def test_the_bundle_version_has_no_default_so_an_unstamped_payload_refuses() -> None:
    """A payload carrying no version must refuse rather than assume one.

    The field previously defaulted to a literal, which did two things at once:
    it declared the current write version a second time, in a layer that cannot
    see the durability floor or the upgrader table that must move with it; and
    it silently accepted a payload with no version at all, parsing it as
    whichever number happened to be written here. A bundle nothing wrote would
    have read as current.

    Asserting the absence of a default is what stops it coming back. A reader
    who sees the field required will look for who stamps it; a reader who sees a
    default will assume it is the answer.
    """
    with pytest.raises(ValidationError, match="bundle_schema_version"):
        UserProfilePortableExport.model_validate({"profile": _profile(), "exported_at": _INSTANT})

    assert UserProfilePortableExport.model_fields["bundle_schema_version"].is_required()


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
