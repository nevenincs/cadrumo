"""Restore a profile from capsule material an operator can actually point at.

The two restore doors take a password envelope, a DEK sentinel and the
database bytes, and are right to: the capsule being restored is by definition
not published, so nothing can load that material through the committed-capsule
reader. But that also makes them uncallable from a command line, because a
command line has a PATH and not three parsed custody records.

This module is the missing half. It reads an unpublished capsule directory --
the shape an operator holds after copying ``buckets/<profile-id>/`` out of a
backup, or after a publication was interrupted -- and hands the parsed material
to the door that proves the key.

Two properties are preserved deliberately rather than incidentally.

The recovery wrapper travels with the capsule. Recovery can only be installed
at publication, and a restore IS a publication, so a restore that read the
wrapper and did not republish it would silently close the operator's second
door at the moment they were recovering. The outcome reports whether the
restored profile carries one, for the same reason registration reports it.

The artifact stays identity-bound. It is proved against the envelope read from
THIS source, so an artifact minted for another profile or another DEK epoch is
refused by the existing checks rather than by a new copy of them here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from ...adapters.persistence.storage import custody
from ...adapters.persistence.storage.custody import (
    PROFILE_CUSTODY_DATA_FILE_MAX_BYTES,
    PROFILE_CUSTODY_ENVELOPE_MAX_BYTES,
    PROFILE_CUSTODY_RECOVERY_MAX_BYTES,
    PROFILE_CUSTODY_SENTINEL_MAX_BYTES,
    parse_profile_custody_envelope,
    parse_profile_custody_recovery_envelope,
)
from ...core.errors import CadrumoError
from ...core.identity import ProfileId
from ._aggregate import ProfileRestoreAuthority
from ._recovery_custody import restore_profile_from_recovery_artifact, restore_profile_with_password

if TYPE_CHECKING:
    from pathlib import Path

    from ._aggregate import CommittedProfileView
    from ._custody_ports import (
        ProfileCustodyEnvelopePort,
        ProfileCustodyRecoveryEnvelopePort,
        ProfileCustodySentinelPort,
    )

_ENVELOPE_RELATIVE = ("custody", "envelope.v1.json")
_RECOVERY_RELATIVE = ("custody", "recovery.v1.json")
_SENTINEL_RELATIVE = ("data", "dek.sentinel.v1.json")
_DATABASE_RELATIVE = ("db", "cadrumo.db")


class ProfileCapsuleSourceError(CadrumoError):
    """Raised when a restore source is not a readable capsule."""


@dataclass(frozen=True, slots=True)
class ProfileCapsuleSource:
    """Everything a restore needs, parsed from one unpublished capsule."""

    password_envelope: ProfileCustodyEnvelopePort
    sentinel: ProfileCustodySentinelPort
    database_bytes: bytes
    recovery_envelope: ProfileCustodyRecoveryEnvelopePort | None


class ProfileRestoreOutcome(BaseModel):
    """Typed result of one completed restore.

    Carries no key material: the identity, which door proved it, and whether
    the republished capsule still has a recovery route.
    """

    model_config = ConfigDict(frozen=True)

    profile_id: ProfileId
    label: str
    authority: ProfileRestoreAuthority
    recovery_enrolled: bool
    """Whether the restored capsule was published carrying a recovery wrapper.

    A restore is the only remaining moment recovery could be installed, so a
    profile restored without one has permanently lost its second door. It is
    reported for the same reason registration reports its own: an operator who
    is not told cannot act on it.
    """


def read_profile_capsule_source(source: Path) -> ProfileCapsuleSource:
    """Parse an unpublished capsule directory into restorable material.

    Every member is parsed rather than merely read, so a torn or truncated
    file is refused here -- before any publication is attempted -- instead of
    surfacing as a decryption failure against a capsule that has already been
    committed.

    The recovery wrapper is the one optional member: its absence is a profile
    that never enrolled, which is a legitimate state and not a damaged source.

    Raises:
        ProfileCapsuleSourceError: When a required member is missing or will
            not parse as the record it claims to be.
    """
    envelope = parse_profile_custody_envelope(
        _require_member(source, _ENVELOPE_RELATIVE, "password envelope", PROFILE_CUSTODY_ENVELOPE_MAX_BYTES),
    )
    sentinel = custody.parse_profile_custody_sentinel_record(
        _require_member(source, _SENTINEL_RELATIVE, "DEK sentinel", PROFILE_CUSTODY_SENTINEL_MAX_BYTES),
    )
    database_bytes = _require_member(
        source, _DATABASE_RELATIVE, "profile database", PROFILE_CUSTODY_DATA_FILE_MAX_BYTES
    )
    recovery_payload = custody.read_optional_profile_custody_local_record(
        source.joinpath(*_RECOVERY_RELATIVE), maximum_bytes=PROFILE_CUSTODY_RECOVERY_MAX_BYTES
    )
    recovery = None if recovery_payload is None else parse_profile_custody_recovery_envelope(recovery_payload)
    if sentinel.profile_id != envelope.profile_id:
        raise ProfileCapsuleSourceError("capsule source sentinel names a different profile than its envelope")
    if recovery is not None and recovery.profile_id != envelope.profile_id:
        raise ProfileCapsuleSourceError("capsule source recovery wrapper names a different profile than its envelope")
    return ProfileCapsuleSource(
        password_envelope=envelope,
        sentinel=sentinel,
        database_bytes=database_bytes,
        recovery_envelope=recovery,
    )


def restore_profile_from_source_with_password(
    *,
    label: str,
    source: Path,
    password: str,
    root: Path | None = None,
) -> ProfileRestoreOutcome:
    """Republish the capsule at ``source`` under its own password.

    Args:
        label: Display name for the republished profile.
        source: An unpublished capsule directory.
        password: The profile's existing password. Never logged.
        root: Storage root override; the effective root when omitted.

    Returns:
        A :class:`ProfileRestoreOutcome` naming the proving door and whether
        recovery survived.
    """
    return restore_profile_capsule_with_password(
        label=label,
        capsule=read_profile_capsule_source(source),
        password=password,
        root=root,
    )


def restore_profile_capsule_with_password(
    *,
    label: str,
    capsule: ProfileCapsuleSource,
    password: str,
    root: Path | None = None,
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
        recovery_envelope=material.recovery_envelope,
        root=root,
    )
    return _outcome(view, material, authority="password")


def restore_profile_from_source_with_recovery_artifact(
    *,
    label: str,
    source: Path,
    artifact_source: Path,
    recovery_secret: str,
    root: Path | None = None,
) -> ProfileRestoreOutcome:
    """Republish the capsule at ``source`` proving a portable artifact instead.

    This recovers the DATA path only. The capsule is republished under its
    EXISTING password envelope, so an operator who genuinely lost their
    password gets their records back onto a valid capsule and still cannot log
    in with a password they do not know. Changing that would be credential
    rotation reached through the recovery door.

    Args:
        label: Display name for the republished profile.
        source: An unpublished capsule directory.
        artifact_source: The portable recovery artifact file.
        recovery_secret: The 24-word phrase minted with that artifact.
        root: Storage root override; the effective root when omitted.

    Returns:
        A :class:`ProfileRestoreOutcome` naming the proving door and whether
        recovery survived.
    """
    return restore_profile_capsule_with_recovery_artifact(
        label=label,
        capsule=read_profile_capsule_source(source),
        artifact_source=artifact_source,
        recovery_secret=recovery_secret,
        root=root,
    )


def restore_profile_capsule_with_recovery_artifact(
    *,
    label: str,
    capsule: ProfileCapsuleSource,
    artifact_source: Path,
    recovery_secret: str,
    root: Path | None = None,
) -> ProfileRestoreOutcome:
    """Publish already-read capsule material proving a portable artifact.

    The recovery counterpart of :func:`restore_profile_capsule_with_password`,
    and the same single publication authority for that door.
    """
    material = capsule
    view = restore_profile_from_recovery_artifact(
        label=label,
        artifact_source=artifact_source,
        recovery_secret=recovery_secret,
        password_envelope=material.password_envelope,
        sentinel=material.sentinel,
        database_bytes=material.database_bytes,
        recovery_envelope=material.recovery_envelope,
        root=root,
    )
    return _outcome(view, material, authority="recovery_artifact")


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
        recovery_enrolled=material.recovery_envelope is not None,
    )


def _require_member(source: Path, relative: tuple[str, ...], subject: str, maximum_bytes: int) -> bytes:
    """Return one required capsule member's bytes, or refuse naming it.

    Reads through the same anchored, bounded, no-follow primitive the PUBLISHED
    capsule reader uses. This path is the less trusted of the two -- a
    published capsule sits inside this product's storage root, while a restore
    source is a directory an operator points at -- and it previously took the
    weaker read: ``is_file()`` then ``read_bytes()``, which follows a symlink,
    bounds nothing, and asks about a NAME before reading a FILE.
    """
    payload = custody.read_optional_profile_custody_local_record(
        source.joinpath(*relative), maximum_bytes=maximum_bytes
    )
    if payload is None:
        raise ProfileCapsuleSourceError(f"capsule source is missing its {subject}")
    return payload


__all__ = [
    "ProfileCapsuleSource",
    "ProfileCapsuleSourceError",
    "ProfileRestoreOutcome",
    "read_profile_capsule_source",
    "restore_profile_capsule_with_password",
    "restore_profile_capsule_with_recovery_artifact",
    "restore_profile_from_source_with_password",
    "restore_profile_from_source_with_recovery_artifact",
]
