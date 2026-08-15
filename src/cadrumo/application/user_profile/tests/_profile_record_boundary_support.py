"""Shared fixture material for the profile-record persistence boundary.

Two suites prove that boundary and they must prove it about the SAME record:
:mod:`test_profile_record_persistence_roundtrip` drives save and load inside
one interpreter, and :mod:`test_profile_record_cross_process_roundtrip` has a
genuinely separate process publish the capsule that this one reads back. If
each owned its own fixture the two could drift, and the cross-process suite
would stop being the in-process suite plus a boundary.

The publisher below is also imported by the CHILD interpreter, which is why
it lives in a support module rather than inside a test module: the child runs
``python -c`` and imports this by name, so nothing here may depend on a
pytest fixture or on an already-running test session.
"""

from __future__ import annotations

from base64 import b64encode
from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel
from pydantic_core import PydanticUndefined

from ....adapters.persistence.storage.custody import (
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
    create_profile_custody_sentinel,
)
from ....domain.buckets import BucketEventType
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from .._capsule_record import ProfileRecordSession

PROFILE_ID = UUID("3f8b1d42-6c07-4e59-9a13-2b7e5c04d8af")
DEK = bytes(range(100, 132))
RECORD_NAMESPACE = "cadrumo.application.user_profile.value"

CREATED_AT = datetime(2024, 1, 4, 9, 0, 0, tzinfo=UTC)
UPDATED_AT = datetime(2024, 6, 15, 14, 32, 17, tzinfo=UTC)
REPLACED_AT = datetime(2024, 9, 2, 8, 5, 41, tzinfo=UTC)

SCHEMA_PINNED_FIELDS = frozenset({"schema_id", "schema_version"})
"""Fields a record validator pins to the loaded schema's own declaration.

Neither can carry a non-default value: ``_validate_payload_schema_identity``
refuses any ``schema_id`` or ``schema_version`` that is not exactly the
canonical one, in both the future and pre-current directions. Excluding them
from the non-default sweep is a statement about the model, not a concession,
and the roundtrip suite proves the pinning still holds.
"""

FACTORY_DEFAULT_FIELDS = frozenset({"created_at", "updated_at"})
"""Clock-defaulted fields whose non-default proof is equality, not inequality.

Their default factory is ``utc_now``, so comparing a loaded value against a
freshly evaluated default would differ for any record whatsoever and prove
nothing. What does prove it is that the fixture pins distinct fixed instants
and the strict roundtrip reproduces them exactly: a boundary that dropped
either would re-default it to the load instant, which is not the pinned
literal.
"""


def build_envelope() -> ProfileCustodyEnvelope:
    """Return the deterministic password envelope both processes agree on."""
    return ProfileCustodyEnvelope.create(
        profile_id=PROFILE_ID,
        password_generation=4,
        dek_epoch=b64encode(b"epoch-roundtrip!").decode("ascii"),
        kdf=ProfileCustodyKdfParameters(
            algorithm="argon2id",
            version=19,
            memory_mib=19,
            iterations=2,
            parallelism=1,
            salt_b64=b64encode(b"salt-roundtrip!!").decode("ascii"),
            output_bytes=32,
        ),
        wrapped_dek=ProfileCustodyWrappedDek(
            nonce_b64=b64encode(b"nonce-round!").decode("ascii"),
            ciphertext_b64=b64encode(b"c" * 32).decode("ascii"),
            tag_b64=b64encode(b"tag-roundtrip!!!").decode("ascii"),
        ),
    )


def populated_facts() -> tuple[UserProfileFact, ...]:
    """Return facts whose every defaultable field also carries a non-default.

    ``source`` defaults to ``manual_cli`` and both window bounds default to
    ``None``, so each fact declares a different declared provenance token and
    a closed effective-dated window. A boundary that dropped a fact's window
    or re-defaulted its provenance would surface as inequality.
    """
    return (
        UserProfileFact(
            path="activities.cnae",
            value="6201",
            source="setup_wizard",
            valid_from=date(2024, 1, 1),
            valid_to=date(2024, 12, 31),
        ),
        UserProfileFact(
            path="activities.description",
            value="Servicios de programacion informatica",
            source="modelo_036_import",
            valid_from=date(2023, 7, 1),
            valid_to=date(2025, 6, 30),
        ),
        UserProfileFact(
            path="attribution_entity.legal_form",
            value="comunidad_de_bienes",
            source="registry_inference",
            valid_from=date(2022, 4, 15),
            valid_to=date(2026, 3, 31),
        ),
    )


def initial_record() -> UserProfileRecord:
    """Return revision one with every non-lineage defaultable field non-default."""
    return UserProfileRecord(
        profile_id=str(PROFILE_ID),
        facts=populated_facts(),
        setup_state=ProfileSetupState.INCOMPLETE,
        created_at=CREATED_AT,
        updated_at=UPDATED_AT,
    )


def open_record_session() -> ProfileRecordSession:
    """Return the record authority bound to the shared envelope and DEK."""
    return ProfileRecordSession.from_envelope(envelope=build_envelope(), dek=DEK)


def publish_capsule(root: Path) -> UserProfileRecord:
    """Publish a real capsule at *root* holding the populated revision-one record.

    Imported by the child interpreter of the cross-process suite as well as
    by the in-process one, so the two suites publish byte-identical capsules
    and differ only in which process does the publishing.
    """
    from .._lifecycle import ProfileCapsuleLifecycle

    envelope = build_envelope()
    session = open_record_session()
    record = initial_record()
    try:
        ProfileCapsuleLifecycle(root=root).create(
            label="Roundtrip operator",
            profile_id=PROFILE_ID,
            password_envelope=envelope,
            sentinel=create_profile_custody_sentinel(envelope=envelope, dek=DEK),
            data_files={},
            initial_record=record,
            record_session=session,
        )
    finally:
        session.close()
    return record


def replacement_record(current: UserProfileRecord) -> UserProfileRecord:
    """Return revision two, populating the two lineage fields non-default.

    Revision one cannot carry a non-default ``record_revision`` or
    ``previous_record_digest`` -- the model refuses a first revision that
    names a predecessor -- so the only honest way to cover those two fields
    is to drive a real replacement onto the record.
    """
    return UserProfileRecord(
        profile_id=str(PROFILE_ID),
        facts=populated_facts(),
        setup_state=ProfileSetupState.INCOMPLETE,
        record_revision=current.record_revision + 1,
        previous_record_digest=current.content_digest,
        created_at=CREATED_AT,
        updated_at=REPLACED_AT,
    )


def advance_to_revision_two(
    session: ProfileRecordSession,
    root: Path,
    written: UserProfileRecord,
    *,
    event_payload: dict[str, str] | None = None,
) -> UserProfileRecord:
    """Drive the real replacement so the capsule holds revision two.

    The anti-tautology proofs mutate the payload by writing a further row
    revision, which leaves a revision-ONE record's row carrying a predecessor
    and trips the initial-lineage guard. That guard would refuse the load for
    a reason unrelated to the payload, masking whether the decode validated
    anything. Advancing first removes the confound: at revision two the
    replacement lineage is legitimately satisfied, so a refusal can only come
    from the payload itself.
    """
    from .._capsule_record import ProfileRecordCommandEvent, ProfileRecordStore

    replacement = replacement_record(written)
    ProfileRecordStore(session=session, root=root).replace(
        replacement=replacement,
        event=ProfileRecordCommandEvent(
            event_type=BucketEventType.PROFILE_VALUES_UPDATED,
            occurred_at=REPLACED_AT.isoformat(),
            payload=event_payload or {},
        ),
        expected_revision=written.record_revision,
        expected_content_digest=written.content_digest,
    )
    return replacement


def defaultable_fields_at_default(record: BaseModel, *, excluded: frozenset[str] | None = None) -> list[str]:
    """Return the defaultable field names sitting at their model default.

    Derived from the model's own fields rather than a maintained list, so a
    newly added defaultable field is covered the day it lands rather than
    when someone remembers to extend an enumeration. A non-empty result means
    a save-drops-field / load-re-defaults-field regression in those fields
    would be invisible to an equality assertion.

    Args:
        record: The model instance to sweep.
        excluded: Field names whose non-default proof is carried elsewhere.
            Defaults to the profile record's own pinned and clock-defaulted
            pair. A sibling boundary proving a DIFFERENT model passes its own
            set, so the exclusion stays a statement about the model under
            proof rather than a constant inherited from an unrelated one.
    """
    skip = SCHEMA_PINNED_FIELDS | FACTORY_DEFAULT_FIELDS if excluded is None else excluded
    at_default: list[str] = []
    for name, field in type(record).model_fields.items():
        if name in skip:
            continue
        if field.default is PydanticUndefined or field.default_factory is not None:
            continue
        if getattr(record, name) == field.default:
            at_default.append(name)
    return at_default


__all__ = [
    "CREATED_AT",
    "DEK",
    "FACTORY_DEFAULT_FIELDS",
    "PROFILE_ID",
    "RECORD_NAMESPACE",
    "REPLACED_AT",
    "SCHEMA_PINNED_FIELDS",
    "UPDATED_AT",
    "advance_to_revision_two",
    "build_envelope",
    "defaultable_fields_at_default",
    "initial_record",
    "open_record_session",
    "populated_facts",
    "publish_capsule",
    "replacement_record",
]
