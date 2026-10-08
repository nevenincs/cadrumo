"""Create snapshot fixtures for the retained domain decoding and hash contracts."""

from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from ....core.hashing import canonical_json_bytes
from ....core.time.clock import now as _utc_now
from ...calculations.registry.authority_artifact import ProfileCreateContext
from ..errors import UserProfileValidationError
from ..values import (
    ProfileSetupState,
    UserProfileRecord,
    UserProfileSnapshot,
    _authority_context_types,
    _context_for_schema,
    _derive_canonical_hash,
    _typed_profile_facts,
    validate_profile_schema_identity,
)


def new_profile_snapshot_id(profile_id: str, *, created_at: datetime | None = None) -> str:
    """Create a deterministic-shape but unique snapshot id."""
    instant = created_at or _utc_now()
    return f"{profile_id}:{instant.strftime('%Y%m%dT%H%M%S%fZ')}:{uuid4().hex}"


def create_user_profile_snapshot(
    profile: UserProfileRecord,
    *,
    context: ProfileCreateContext,
    snapshot_id: str | None = None,
    created_at: datetime | None = None,
) -> UserProfileSnapshot:
    """Create an immutable encrypted-persistence snapshot under one schema.

    Core types:
    :class:`~cadrumo.domain.user_profile.values.UserProfileRecord`.
    """
    checked = _context_for_schema(context)
    create_context_type, _ = _authority_context_types()
    if not isinstance(checked, create_context_type):
        raise TypeError("creating a profile snapshot requires ProfileCreateContext")
    if profile.setup_state is not ProfileSetupState.COMPLETE:
        raise UserProfileValidationError("cannot snapshot an incomplete profile record")
    validate_profile_schema_identity(
        profile.schema_id,
        profile.schema_version,
        schema=checked.schema,
        surface="user profile record",
    )
    typed_facts = _typed_profile_facts(tuple(profile.facts), schema=checked.schema)
    instant = created_at or _utc_now()
    facts = tuple(
        sorted(
            typed_facts,
            key=lambda fact: (
                fact.path,
                fact.valid_from or date.min,
                fact.valid_to or date.max,
                canonical_json_bytes(fact.model_dump(mode="json")),
            ),
        ),
    )
    digest = _derive_canonical_hash(
        schema_id=checked.schema.id,
        schema_version=checked.schema.version,
        profile_id=profile.profile_id,
        facts=facts,
    )
    snapshot = UserProfileSnapshot.model_validate(
        {
            "snapshot_id": snapshot_id or new_profile_snapshot_id(profile.profile_id, created_at=instant),
            "profile_id": profile.profile_id,
            "schema_id": checked.schema.id,
            "schema_version": checked.schema.version,
            "created_at": instant,
            "facts": facts,
            "canonical_hash": digest,
        },
        context=checked,
    )
    return snapshot
