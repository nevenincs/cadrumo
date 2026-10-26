"""Restore a profile from capsule material an operator can actually point at.

The restore door takes a password envelope, a DEK sentinel and the database
bytes, and is right to: the capsule being restored is by definition not
published, so nothing can load that material through the committed-capsule
reader. But that also makes it uncallable from a command line, because a
command line has a PATH and not three parsed custody records.

This module is the missing half. It reads an unpublished capsule directory --
the shape an operator holds after copying ``buckets/<profile-id>/`` out of a
backup, or after a publication was interrupted -- and hands the parsed material
to the door that proves the key.

Recovery material is deliberately not publication cargo. A source directory
may contain an enrolled recovery wrapper, while a restorative archive never
does; a restore installs neither. The restored profile enrols recovery again
explicitly if the operator wants it, which the restore outcome says out loud.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core.errors.hierarchy import CadrumoError
from ...core.identity.profile import ProfileId
from ...core.models import STRICT_FROZEN_CONFIG
from .aggregate import ProfileRestoreAuthority
from .authentication import ProfilePasswordProofOperation
from .capsule_record import ProfileRecordSession
from .custody_ports import (
    map_profile_authentication_proof_failure,
    read_profile_custody_capsule_source,
    unlock_profile_custody_password,
)
from .lifecycle import ProfileCapsuleLifecycle

if TYPE_CHECKING:
    from pathlib import Path

    from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext
    from .aggregate import CommittedProfileView
    from .custody_ports import (
        ProfileCustodyEnvelopePort,
        ProfileCustodySentinelPort,
    )


class ProfileCapsuleSourceError(CadrumoError):
    """Raised when a restore source is not a readable capsule."""


@dataclass(frozen=True, slots=True)
class ProfileCapsuleSource:
    """Everything a restore needs, parsed from one unpublished capsule."""

    password_envelope: ProfileCustodyEnvelopePort
    sentinel: ProfileCustodySentinelPort
    database_bytes: bytes


class ProfileRestoreOutcome(BaseModel):
    """Typed result of one completed restore.

    Carries no key material: the identity, which door proved it, and whether
    the republished capsule still has a recovery route.
    """

    model_config = STRICT_FROZEN_CONFIG

    profile_id: ProfileId
    label: str
    authority: ProfileRestoreAuthority
    recovery_enrolled: bool
    """Always false: a restore never installs recovery in the destination."""


def read_profile_capsule_source(source: Path) -> ProfileCapsuleSource:
    """Parse an unpublished capsule directory into restorable material.

    Every member is parsed rather than merely read, so a torn or truncated
    file is refused here -- before any publication is attempted -- instead of
    surfacing as a decryption failure against a capsule that has already been
    committed.

    Recovery is not read here. Its presence, absence, or health says nothing
    about whether this password/archive source is restorable.

    Raises:
        ProfileCapsuleSourceError: When a required member is missing or will
            not parse as the record it claims to be.
    """
    try:
        parsed = read_profile_custody_capsule_source(source)
    except (OSError, ValueError) as exc:
        raise ProfileCapsuleSourceError(str(exc)) from exc
    envelope = parsed.password_envelope
    sentinel = parsed.sentinel
    database_bytes = parsed.database_bytes
    if sentinel.profile_id != envelope.profile_id:
        raise ProfileCapsuleSourceError("capsule source sentinel names a different profile than its envelope")
    return ProfileCapsuleSource(
        password_envelope=envelope,
        sentinel=sentinel,
        database_bytes=database_bytes,
    )


def restore_profile_capsule_with_password(
    *,
    label: str,
    capsule: ProfileCapsuleSource,
    password: str,
    root: Path | None = None,
    profile_decode_context: ProfileDecodeContext,
) -> ProfileRestoreOutcome:
    """Publish already-read capsule material under its own password.

    This is the shared publication authority. A directory restore and an
    archive import differ only in how they OBTAIN a
    :class:`ProfileCapsuleSource`; once they have one, both arrive here, so
    there is exactly one thing that knows how to turn capsule material into a
    published profile. Adding a second would be the fork this arrangement
    exists to prevent.
    """
    material = capsule
    view = restore_profile_with_password(
        label=label,
        password=password,
        password_envelope=material.password_envelope,
        sentinel=material.sentinel,
        database_bytes=material.database_bytes,
        root=root,
        profile_decode_context=profile_decode_context,
    )
    return _outcome(view, material, authority="password")


def _outcome(
    view: CommittedProfileView,
    material: ProfileCapsuleSource,
    *,
    authority: ProfileRestoreAuthority,
) -> ProfileRestoreOutcome:
    """Project one published view and its source into the typed outcome."""
    return ProfileRestoreOutcome(
        profile_id=view.profile_id,
        label=view.label,
        authority=authority,
        recovery_enrolled=False,
    )


@dataclass(frozen=True, slots=True)
class _SuppliedPasswordMaterial:
    """The envelope and sentinel of a capsule that is not committed yet.

    The committed-capsule loader cannot serve a restore: the capsule being
    restored is by definition not published, so its material arrives from
    the caller and is proved here instead of being read from a path.
    """

    envelope: ProfileCustodyEnvelopePort
    sentinel: ProfileCustodySentinelPort


def restore_profile_with_password(
    *,
    label: str,
    password: str,
    password_envelope: ProfileCustodyEnvelopePort,
    sentinel: ProfileCustodySentinelPort,
    database_bytes: bytes,
    root: Path | None = None,
    profile_decode_context: ProfileDecodeContext,
) -> CommittedProfileView:
    """Republish one capsule proving nothing but the profile's own password.

    Password-only is a structural claim, not a description of the usual
    case: no shared master key, no ambient provider, no recovery secret and
    no environment value participates. The password unwraps this capsule's
    own envelope, the resulting key is proved against this capsule's own
    committed sentinel, and only then is anything published.

    The session is closed in every exit path, including the failing ones, so
    a refused restore leaves no live key material behind.
    """
    try:
        unlock = unlock_profile_custody_password(
            _SuppliedPasswordMaterial(envelope=password_envelope, sentinel=sentinel),
            password=password,
        )
    except BaseException as exc:
        refusal = map_profile_authentication_proof_failure(exc, operation=ProfilePasswordProofOperation.RESTORE)
        if refusal is None:
            raise
        raise refusal from exc
    session = ProfileRecordSession.from_envelope(
        envelope=password_envelope,
        dek=unlock.dek,
        profile_decode_context=profile_decode_context,
    )
    try:
        return ProfileCapsuleLifecycle(root=root).restore(
            label=label,
            password_envelope=password_envelope,
            sentinel=sentinel,
            data_files={},
            record_session=session,
            database_bytes=database_bytes,
            authority="password",
        )
    finally:
        session.close()


__all__ = [
    "ProfileCapsuleSource",
    "ProfileCapsuleSourceError",
    "ProfileRestoreOutcome",
    "read_profile_capsule_source",
    "restore_profile_capsule_with_password",
    "restore_profile_with_password",
]
