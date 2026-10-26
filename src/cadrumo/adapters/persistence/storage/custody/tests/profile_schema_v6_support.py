"""Publish real capsules as a schema-6 build wrote them, for migration tests.

A schema-6 capsule is published through the production lifecycle under a
record session pinned to the legacy schema, so its row, lineage and history
event are exactly what that build persisted. Nothing is forged after the fact.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from cadrumo.adapters.persistence.storage.custody.sentinel import create_profile_custody_sentinel
from cadrumo.application.user_profile.capsule_record import ProfileRecordSession
from cadrumo.application.user_profile.lifecycle import ProfileCapsuleLifecycle
from cadrumo.domain.calculations.registry.authority_artifact import ProfileCreateContext, ProfileDecodeContext
from cadrumo.domain.user_profile.schema_migration import legacy_profile_schema
from cadrumo.domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    create_user_profile_record,
)

from .profile_record_boundary_support import CREATED_AT, DEK, PROFILE_ID, UPDATED_AT, build_envelope


def record_session(decode_context: ProfileDecodeContext) -> ProfileRecordSession:
    """Return the record authority for the shared envelope under ``decode_context``."""
    return ProfileRecordSession.from_envelope(envelope=build_envelope(), dek=DEK, profile_decode_context=decode_context)


def publish_capsule(
    root: Path,
    *,
    facts: tuple[UserProfileFact, ...],
    create_context: ProfileCreateContext,
    decode_context: ProfileDecodeContext,
) -> UserProfileRecord:
    """Publish a capsule through the production lifecycle under the given schema."""
    envelope = build_envelope()
    record = create_user_profile_record(
        context=create_context,
        profile_id=str(PROFILE_ID),
        facts=facts,
        setup_state=ProfileSetupState.INCOMPLETE,
        created_at=CREATED_AT,
        updated_at=UPDATED_AT,
    )
    session = record_session(decode_context)
    try:
        ProfileCapsuleLifecycle(root=root).create(
            label="Migration operator",
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


def publish_v6_capsule(
    root: Path,
    *,
    facts: tuple[UserProfileFact, ...],
    create_context: ProfileCreateContext,
    decode_context: ProfileDecodeContext,
) -> UserProfileRecord:
    """Publish a capsule whose record is stored under profile schema 6."""
    legacy = legacy_profile_schema(decode_context.schema)
    return publish_capsule(
        root,
        facts=facts,
        create_context=replace(create_context, schema=legacy),
        decode_context=replace(decode_context, schema=legacy),
    )


__all__ = ["publish_capsule", "publish_v6_capsule", "record_session"]
