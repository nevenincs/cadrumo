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

The fixture material itself lives in
:mod:`_profile_record_boundary_support`, shared with the cross-process suite
so the two prove their claims about the same record rather than about two
fixtures that happen to look alike.

The anti-tautology proofs mutate the persisted payload through the same
encrypted write path and confirm the load side refuses. If either ever
passes with the boundary broken, every roundtrip assertion over this record
is worthless and the suite must be re-audited.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Generator, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from ....core import SecureObjectWrite
from ....domain.user_profile.values import ProfileSetupState, UserProfileRecord
from ..capsule_record import (
    ProfileRecordIntegrityError,
    ProfileRecordSession,
    ProfileRecordStore,
    profile_record_object_key,
)
from ..custody_ports import profile_custody_secure_object_namespace, profile_custody_secure_object_repository
from ._profile_record_boundary_support import (
    CREATED_AT,
    PROFILE_ID,
    RECORD_NAMESPACE,
    REPLACED_AT,
    UPDATED_AT,
    advance_to_revision_two,
    defaultable_fields_at_default,
    open_record_session,
    populated_facts,
    publish_capsule,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _create_capsule(root: Path) -> tuple[ProfileRecordSession, UserProfileRecord]:
    """Publish a real capsule holding the populated revision-one record."""
    session = open_record_session()
    record = publish_capsule(root)
    return session, record


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
        raw = next(row for row in objects.iter_all_records_raw() if row.namespace == RECORD_NAMESPACE)
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
                    written_at=REPLACED_AT,
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
    replacement = advance_to_revision_two(
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
    advance_to_revision_two(session, root, written)
    loaded = _store(session, root).load().record

    at_default = defaultable_fields_at_default(loaded)

    assert not at_default, (
        "these defaultable fields sit at their model default across the boundary, so a "
        "save-drops-field / load-re-defaults-field regression in them would be invisible: "
        f"{sorted(at_default)}"
    )
    # The clock-defaulted pair is proven by exact reproduction instead.
    assert loaded.created_at == CREATED_AT
    assert loaded.updated_at == REPLACED_AT
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
    schema_version_default_factory = UserProfileRecord.model_fields["schema_version"].default_factory
    assert schema_version_default_factory is not None
    canonical_version = schema_version_default_factory()
    assert isinstance(canonical_version, int)
    cases: tuple[tuple[dict[str, object], str], ...] = (
        ({"schema_id": "cadrumo.user_profile.other"}, "is not the canonical profile schema"),
        ({"schema_version": canonical_version + 1}, "is not the canonical profile schema version"),
    )
    for overrides, fragment in cases:
        with pytest.raises(ValidationError) as refusal:
            UserProfileRecord.model_validate(
                {
                    "profile_id": str(PROFILE_ID),
                    "facts": populated_facts(),
                    "setup_state": ProfileSetupState.INCOMPLETE,
                    "created_at": CREATED_AT,
                    "updated_at": UPDATED_AT,
                    **overrides,
                },
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
    advance_to_revision_two(session, root, written)
    _rewrite_persisted_payload(session, root, lambda payload: payload.pop("profile_id"))

    with pytest.raises(ProfileRecordIntegrityError) as refusal:
        _store(session, root).load()

    assert isinstance(refusal.value.__cause__, ValidationError)


def test_load_refuses_a_persisted_payload_with_a_defaultable_field_deleted(
    capsule: tuple[ProfileRecordSession, UserProfileRecord, Path],
) -> None:
    """Anti-tautology: dropping a REQUIRED field must not load cleanly.

    ``setup_state`` no longer carries a default (the silent-COMPLETE hazard was
    removed by making the field required), so a payload with the field deleted
    is refused at the model boundary itself -- the deletion is visible as a
    missing-field ValidationError instead of being re-defaulted. The populated
    fixture still matters: a record written with an explicit non-default state
    is the only honest specimen to mutate.
    """
    session, written, root = capsule
    assert written.setup_state is not ProfileSetupState.COMPLETE, (
        "the fixture must not persist the COMPLETE setup_state, or deleting it proves nothing"
    )
    advance_to_revision_two(session, root, written)
    _rewrite_persisted_payload(session, root, lambda payload: payload.pop("setup_state"))

    with pytest.raises(ProfileRecordIntegrityError) as refusal:
        _store(session, root).load()

    cause = refusal.value.__cause__
    assert isinstance(cause, ValidationError)
    assert "setup_state" in str(cause)
