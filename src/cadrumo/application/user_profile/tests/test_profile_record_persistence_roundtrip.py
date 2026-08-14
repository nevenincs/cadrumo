"""Strict roundtrip and anti-tautology proof for the profile-record boundary.

The profile record is the central persisted object of the custody capsule:
one encrypted ``cadrumo.application.user_profile.value`` row inside the
capsule's own SQLite substrate, written and read through
:class:`ProfileRecordStore`. Everything downstream assumes that boundary
preserves the record exactly, and nothing else demonstrates it.

Every adapter here is real. The capsule is published through the production
:class:`ProfileCapsuleLifecycle`, the row is encrypted under a real
:class:`ProfileRecordSession` bound to a real envelope and DEK, the database
is a real on-disk SQLite file, and the serializer is the production
``model_dump_json`` / ``model_validate_json`` pair. Nothing is mocked,
stubbed or patched: a fake returning what the assertion expects is exactly
the false positive this file exists to exclude.

The fixture populates every defaultable field with a non-default value,
because a save-drops-field / load-re-defaults-field regression is invisible
when the fixture uses the default. ``schema_id`` and ``schema_version`` are
the two deliberate exceptions: a model validator pins both to exactly what
the loaded profile schema declares, so a "non-default" value for either is
not a stronger fixture but an unconstructible record. That exclusion is
asserted rather than assumed, so it fails if the pinning is ever relaxed.

The anti-tautology proofs mutate the persisted payload through the same
encrypted write path and confirm the load side refuses. If either ever
passes with the boundary broken, every roundtrip assertion over this record
is worthless and the suite must be re-audited.
"""

from __future__ import annotations

import json
from base64 import b64encode
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from pydantic import ValidationError
from pydantic_core import PydanticUndefined

from ....adapters.persistence.storage.custody import (
    ProfileCustodyEnvelope,
    ProfileCustodyKdfParameters,
    ProfileCustodyWrappedDek,
    create_profile_custody_sentinel,
)
from ....core import SecureObjectWrite
from ....domain.buckets import BucketEventType
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ...profile_custody import (
    profile_custody_secure_object_namespace,
    profile_custody_secure_object_repository,
)
from .._capsule_record import (
    ProfileRecordCommandEvent,
    ProfileRecordIntegrityError,
    ProfileRecordSession,
    ProfileRecordStore,
    profile_record_object_key,
)
from .._lifecycle import ProfileCapsuleLifecycle

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = UUID("3f8b1d42-6c07-4e59-9a13-2b7e5c04d8af")
_DEK = bytes(range(100, 132))
_RECORD_NAMESPACE = "cadrumo.application.user_profile.value"

_CREATED_AT = datetime(2024, 1, 4, 9, 0, 0, tzinfo=UTC)
_UPDATED_AT = datetime(2024, 6, 15, 14, 32, 17, tzinfo=UTC)
_REPLACED_AT = datetime(2024, 9, 2, 8, 5, 41, tzinfo=UTC)

_SCHEMA_PINNED_FIELDS = frozenset({"schema_id", "schema_version"})
"""Fields a record validator pins to the loaded schema's own declaration.

Neither can carry a non-default value: ``_validate_payload_schema_identity``
refuses any ``schema_id`` or ``schema_version`` that is not exactly the
canonical one, in both the future and pre-current directions. Excluding them
from the non-default sweep is a statement about the model, not a concession,
and :func:`test_schema_identity_fields_are_pinned_not_merely_defaulted`
proves the pinning still holds.
"""

_FACTORY_DEFAULT_FIELDS = frozenset({"created_at", "updated_at"})
"""Clock-defaulted fields whose non-default proof is equality, not inequality.

Their default factory is ``utc_now``, so comparing a loaded value against a
freshly evaluated default would differ for any record whatsoever and prove
nothing. What does prove it is that the fixture pins two distinct fixed
instants and the strict roundtrip reproduces both exactly: a boundary that
dropped either would re-default it to the load instant, which is not the
pinned literal.
"""


def _envelope() -> ProfileCustodyEnvelope:
    return ProfileCustodyEnvelope.create(
        profile_id=_PROFILE_ID,
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


def _populated_facts() -> tuple[UserProfileFact, ...]:
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


def _initial_record() -> UserProfileRecord:
    """Return revision one with every non-lineage defaultable field non-default."""
    return UserProfileRecord(
        profile_id=str(_PROFILE_ID),
        facts=_populated_facts(),
        setup_state=ProfileSetupState.INCOMPLETE,
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
    )


def _create_capsule(root: Path) -> tuple[ProfileRecordSession, UserProfileRecord]:
    """Publish a real capsule holding the populated revision-one record."""
    envelope = _envelope()
    session = ProfileRecordSession.from_envelope(envelope=envelope, dek=_DEK)
    record = _initial_record()
    ProfileCapsuleLifecycle(root=root).create(
        label="Roundtrip operator",
        profile_id=_PROFILE_ID,
        password_envelope=envelope,
        sentinel=create_profile_custody_sentinel(envelope=envelope, dek=_DEK),
        data_files={},
        initial_record=record,
        record_session=session,
    )
    return session, record


def _replacement_of(current: UserProfileRecord) -> UserProfileRecord:
    """Return revision two, populating the two lineage fields non-default."""
    return UserProfileRecord(
        profile_id=str(_PROFILE_ID),
        facts=_populated_facts(),
        setup_state=ProfileSetupState.INCOMPLETE,
        record_revision=current.record_revision + 1,
        previous_record_digest=current.content_digest,
        created_at=_CREATED_AT,
        updated_at=_REPLACED_AT,
    )


def _store(session: ProfileRecordSession, root: Path) -> ProfileRecordStore:
    return ProfileRecordStore(session=session, root=root)


@contextmanager
def _record_objects(session: ProfileRecordSession, root: Path) -> Generator[Any]:
    """Open the capsule's real secure-object repository under the live DEK."""
    with profile_custody_secure_object_repository(
        profile_id=session.profile_id,
        dek=session.encryption_key(),
        root=root,
    ) as objects:
        yield objects


def _advance_to_revision_two(
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
    replacement = _replacement_of(written)
    _store(session, root).replace(
        replacement=replacement,
        event=ProfileRecordCommandEvent(
            event_type=BucketEventType.PROFILE_VALUES_UPDATED.value,
            occurred_at=_REPLACED_AT.isoformat(),
            payload=event_payload or {},
        ),
        expected_revision=written.record_revision,
        expected_content_digest=written.content_digest,
    )
    return replacement


def _rewrite_persisted_payload(
    session: ProfileRecordSession,
    root: Path,
    mutate: Callable[[dict[str, Any]], None],
) -> None:
    """Apply *mutate* to the decrypted payload and write it back encrypted.

    The mutation travels the production write path -- same namespace, same
    object key, same row provenance, same compare-and-swap token -- so the
    only thing that differs on disk is the record payload itself. A mutation
    that bypassed the encryption would prove nothing about the real load.
    """
    namespace = profile_custody_secure_object_namespace()
    object_key = profile_record_object_key(session.profile_id)
    with _record_objects(session, root) as objects:
        raw = next(row for row in objects.iter_all_records_raw() if row.namespace == _RECORD_NAMESPACE)
        loaded = objects.load(
            namespace.namespace,
            object_key,
            expected_class=namespace.sensitivity,
            max_supported_version=namespace.schema_version,
        )
        payload = json.loads(loaded.payload)
        mutate(payload)
        objects.apply_batch(
            (
                SecureObjectWrite(
                    namespace=namespace.namespace,
                    object_key=object_key,
                    classification=namespace.sensitivity,
                    schema_version=namespace.schema_version,
                    written_at=_REPLACED_AT,
                    payload=json.dumps(payload).encode("utf-8"),
                    write_provenance=raw.write_provenance,
                    source_event_id=raw.source_event_id,
                    expected_revision_id=raw.revision_id,
                ),
            ),
        )


@pytest.fixture
def capsule(tmp_path: Path) -> Iterator[tuple[ProfileRecordSession, UserProfileRecord, Path]]:
    session, record = _create_capsule(tmp_path)
    try:
        yield session, record, tmp_path
    finally:
        session.close()


def test_populated_record_survives_the_encrypted_capsule_boundary_unchanged(
    capsule: tuple[ProfileRecordSession, UserProfileRecord, Path],
) -> None:
    """Strict equality across the real save / load cycle at revision one."""
    session, written, root = capsule

    loaded = _store(session, root).load().record

    assert loaded == written


def test_replacement_record_survives_the_boundary_with_its_lineage_intact(
    capsule: tuple[ProfileRecordSession, UserProfileRecord, Path],
) -> None:
    """Strict equality across the compare-and-swap replacement path.

    Revision one cannot populate ``record_revision`` or
    ``previous_record_digest`` with a non-default value -- the model refuses
    a first revision that names a predecessor -- so the only honest way to
    cover those two fields is to drive the real replacement.
    """
    session, written, root = capsule
    replacement = _advance_to_revision_two(
        session,
        root,
        written,
        event_payload={"reason": "persistence-boundary-proof"},
    )

    loaded = _store(session, root).load().record

    assert loaded == replacement


def test_every_defaultable_field_is_populated_non_default_across_the_boundary(
    capsule: tuple[ProfileRecordSession, UserProfileRecord, Path],
) -> None:
    """Keep the fixture honest: no defaultable field may sit at its default.

    Without this the roundtrip degrades silently. Someone simplifies the
    fixture, a field falls back to its default, and the save-drops /
    load-re-defaults regression for that field becomes invisible again while
    the equality assertion still passes. The sweep is derived from the
    model's own fields, so a newly added defaultable field is covered the
    day it lands rather than when someone remembers to extend a list.
    """
    session, written, root = capsule
    _advance_to_revision_two(session, root, written)
    loaded = _store(session, root).load().record

    at_default: list[str] = []
    for name, field in UserProfileRecord.model_fields.items():
        if name in _SCHEMA_PINNED_FIELDS or name in _FACTORY_DEFAULT_FIELDS:
            continue
        if field.default is PydanticUndefined or field.default_factory is not None:
            continue
        if getattr(loaded, name) == field.default:
            at_default.append(name)

    assert not at_default, (
        "these defaultable fields sit at their model default across the boundary, so a "
        "save-drops-field / load-re-defaults-field regression in them would be invisible: "
        f"{sorted(at_default)}"
    )
    # The clock-defaulted pair is proven by exact reproduction instead.
    assert loaded.created_at == _CREATED_AT
    assert loaded.updated_at == _REPLACED_AT
    assert loaded.created_at != loaded.updated_at


def test_schema_identity_fields_are_pinned_not_merely_defaulted() -> None:
    """Prove the two excluded fields are unconstructible, not just untested.

    The non-default sweep above skips ``schema_id`` and ``schema_version``.
    That exclusion is only legitimate while the model genuinely refuses any
    other value; the moment the pinning is relaxed they become ordinary
    defaultable fields the sweep should have been covering.

    The refusal surfaces as a pydantic ``ValidationError`` rather than the
    domain's own ``UserProfileValidationError``: the domain type subclasses
    ``ValueError`` precisely so a validator can raise it, and pydantic wraps
    any ``ValueError`` from a model validator into its own error. The typed
    class is therefore not catchable by callers of this boundary, so the
    message is what the assertion has to bind to.
    """
    canonical_version: int = UserProfileRecord.model_fields["schema_version"].default_factory()  # type: ignore[assignment,misc]
    cases = (
        ({"schema_id": "cadrumo.user_profile.other"}, "is not the canonical profile schema"),
        ({"schema_version": canonical_version + 1}, "is not the canonical profile schema version"),
    )
    for overrides, fragment in cases:
        with pytest.raises(ValidationError) as refusal:
            UserProfileRecord(
                profile_id=str(_PROFILE_ID),
                facts=_populated_facts(),
                setup_state=ProfileSetupState.INCOMPLETE,
                created_at=_CREATED_AT,
                updated_at=_UPDATED_AT,
                **overrides,
            )
        assert fragment in str(refusal.value)


def test_load_refuses_a_persisted_payload_with_a_required_field_deleted(
    capsule: tuple[ProfileRecordSession, UserProfileRecord, Path],
) -> None:
    """Anti-tautology: dropping a required field must not load cleanly.

    ``profile_id`` carries no default, so its absence is unrecoverable and
    the strict decode must refuse. If this ever loads, the boundary is not
    validating on read and every roundtrip assertion above is vacuous.
    """
    session, written, root = capsule
    _advance_to_revision_two(session, root, written)
    _rewrite_persisted_payload(session, root, lambda payload: payload.pop("profile_id"))

    with pytest.raises(ProfileRecordIntegrityError) as refusal:
        _store(session, root).load()

    assert isinstance(refusal.value.__cause__, ValidationError)


def test_load_refuses_a_persisted_payload_with_a_defaultable_field_deleted(
    capsule: tuple[ProfileRecordSession, UserProfileRecord, Path],
) -> None:
    """Anti-tautology: dropping a DEFAULTABLE field must not load cleanly either.

    This is the harder half and the specific regression the populated fixture
    exists for. ``setup_state`` has a default, so a naive strict model would
    happily re-default it and hand back a record that differs from what was
    written without raising -- the silent shape of the bug. The record's
    content digest is what makes that impossible: it is computed over every
    other field, so a dropped field re-derives a digest that no longer
    matches the persisted one and the load refuses instead of lying.
    """
    session, written, root = capsule
    assert written.setup_state is not UserProfileRecord.model_fields["setup_state"].default, (
        "the fixture must not persist the default setup_state, or deleting it proves nothing"
    )
    _advance_to_revision_two(session, root, written)
    _rewrite_persisted_payload(session, root, lambda payload: payload.pop("setup_state"))

    with pytest.raises(ProfileRecordIntegrityError) as refusal:
        _store(session, root).load()

    cause = refusal.value.__cause__
    assert isinstance(cause, ValidationError)
    assert "content digest does not match" in str(cause)
