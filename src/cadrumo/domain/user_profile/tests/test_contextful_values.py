"""Context-bound creation and decoding of profile value records."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from ....core.hashing import content_hash_hex
from ....domain.calculations.registry.tests.published_authority import published_profile_schema
from ...calculations.registry.authority_artifact import (
    AuthorityGenerationPin,
    ProfileCreateContext,
    ProfileDecodeContext,
)
from ..errors import UserProfileValidationError
from ..values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    UserProfileSnapshot,
    create_user_profile_record,
    create_user_profile_snapshot,
    decode_user_profile_record,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SCHEMA = published_profile_schema()
_PIN = AuthorityGenerationPin(
    content_hash_hex({"generation": "profile-values-fixture"}),
    content_hash_hex({"reader": "profile-values-fixture"}),
)
_CREATE = ProfileCreateContext(schema=_SCHEMA, generation=_PIN)
_DECODE = ProfileDecodeContext(schema=_SCHEMA, generation=_PIN)
_PROFILE_ID = "8d87424d-0b5a-469e-b802-02ffdad316f1"
_INSTANT = datetime(2026, 5, 7, 10, 0, tzinfo=UTC)
_CUSTOM_SOURCE = "fixture_custom"


def _fact() -> UserProfileFact:
    return UserProfileFact(path="identity.tax_id", value="12345678Z")


def _record() -> UserProfileRecord:
    return create_user_profile_record(
        context=_CREATE,
        profile_id=_PROFILE_ID,
        facts=(_fact(),),
        setup_state=ProfileSetupState.COMPLETE,
        created_at=_INSTANT,
        updated_at=_INSTANT,
    )


def _schema_with_custom_provenance():
    """Build a fixture-only schema variant with one explicitly declared source."""
    provenance = _SCHEMA.section("provenance")
    fields = tuple(
        field.model_copy(update={"enum_values": (*field.enum_values, _CUSTOM_SOURCE)})
        if field.key == "source"
        else field
        for field in provenance.fields
    )
    custom_provenance = provenance.model_copy(update={"fields": fields})
    return _SCHEMA.model_copy(
        update={
            "sections": tuple(
                custom_provenance if section.key == "provenance" else section for section in _SCHEMA.sections
            ),
        },
    )


def test_creation_stamps_the_supplied_schema_identity() -> None:
    record = _record()

    assert record.schema_id == _SCHEMA.id
    assert record.schema_version == _SCHEMA.version


def test_direct_record_construction_requires_context() -> None:
    with pytest.raises(ValidationError, match="pinned profile context"):
        UserProfileRecord(
            schema_id=_SCHEMA.id,
            schema_version=_SCHEMA.version,
            profile_id=_PROFILE_ID,
            facts=(_fact(),),
            setup_state=ProfileSetupState.COMPLETE,
            created_at=_INSTANT,
            updated_at=_INSTANT,
        )


def test_direct_snapshot_construction_requires_context() -> None:
    snapshot = create_user_profile_snapshot(
        context=_CREATE, profile=_record(), snapshot_id="snapshot-1", created_at=_INSTANT
    )

    with pytest.raises(ValidationError, match="pinned profile context"):
        UserProfileSnapshot.model_validate(snapshot.model_dump())


def test_decode_round_trips_record_and_snapshot_with_decode_context() -> None:
    record = _record()
    snapshot = create_user_profile_snapshot(
        context=_CREATE, profile=record, snapshot_id="snapshot-1", created_at=_INSTANT
    )

    decoded_record = decode_user_profile_record(record.model_dump_json(), context=_DECODE)
    decoded_snapshot = UserProfileSnapshot.model_validate_json(snapshot.model_dump_json(), context=_DECODE)

    assert decoded_record == record
    assert decoded_snapshot == snapshot


@pytest.mark.parametrize("version", (_SCHEMA.version - 1, _SCHEMA.version + 1))
def test_decode_refuses_pre_current_and_future_schema_versions(version: int) -> None:
    assert _SCHEMA.version > 1
    payload = _record().model_dump()
    payload["schema_version"] = version

    with pytest.raises(ValidationError, match="is not the canonical profile schema version"):
        decode_user_profile_record(payload, context=_DECODE)


def test_decode_refuses_an_unknown_schema_id() -> None:
    payload = _record().model_dump()
    payload["schema_id"] = "bogus.profile"

    with pytest.raises(ValidationError, match="is not the canonical profile schema"):
        decode_user_profile_record(payload, context=_DECODE)


def test_fact_provenance_is_checked_against_the_supplied_schema() -> None:
    custom_schema = _schema_with_custom_provenance()
    custom_context = ProfileCreateContext(schema=custom_schema, generation=_PIN)
    custom_fact = UserProfileFact(path="identity.tax_id", value="12345678Z", source=_CUSTOM_SOURCE)

    record = create_user_profile_record(
        context=custom_context,
        profile_id=_PROFILE_ID,
        facts=(custom_fact,),
        setup_state=ProfileSetupState.COMPLETE,
        created_at=_INSTANT,
        updated_at=_INSTANT,
    )

    assert record.facts == (custom_fact,)
    with pytest.raises(UserProfileValidationError, match="is not declared by the profile schema"):
        create_user_profile_record(
            context=_CREATE,
            profile_id=_PROFILE_ID,
            facts=(custom_fact,),
            setup_state=ProfileSetupState.COMPLETE,
            created_at=_INSTANT,
            updated_at=_INSTANT,
        )


def test_snapshot_hash_and_serialization_are_canonical_across_fact_order() -> None:
    first = UserProfileFact(path="identity.tax_id", value="12345678Z")
    second = UserProfileFact(path="renta_taxpayer.sex", value="1")
    record_a = create_user_profile_record(
        context=_CREATE,
        profile_id=_PROFILE_ID,
        facts=(first, second),
        setup_state=ProfileSetupState.COMPLETE,
        created_at=_INSTANT,
        updated_at=_INSTANT,
    )
    record_b = create_user_profile_record(
        context=_CREATE,
        profile_id=_PROFILE_ID,
        facts=(second, first),
        setup_state=ProfileSetupState.COMPLETE,
        created_at=_INSTANT,
        updated_at=_INSTANT,
    )
    snapshot_a = create_user_profile_snapshot(
        context=_CREATE,
        profile=record_a,
        snapshot_id="snapshot-canonical",
        created_at=_INSTANT,
    )
    snapshot_b = create_user_profile_snapshot(
        context=_CREATE,
        profile=record_b,
        snapshot_id="snapshot-canonical",
        created_at=_INSTANT,
    )

    assert snapshot_a.facts == snapshot_b.facts
    assert snapshot_a.canonical_hash == snapshot_b.canonical_hash
    assert UserProfileSnapshot.model_validate_json(snapshot_a.model_dump_json(), context=_DECODE) == snapshot_a

    tampered = snapshot_a.model_dump()
    tampered["facts"] = tuple(reversed(tampered["facts"]))
    with pytest.raises(ValidationError, match="canonical_hash"):
        UserProfileSnapshot.model_validate(tampered, context=_DECODE)
