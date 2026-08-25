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

Recovery material is deliberately not publication cargo. A source directory
may contain its local creation wrapper, while a restorative archive never
does; neither normal password restore nor artifact restore installs that
wrapper in the destination. The artifact is proof for the explicit recovery
door only.

The artifact stays identity-bound. It is proved against the envelope read from
THIS source, so an artifact minted for another profile or another DEK epoch is
refused by the existing checks rather than by a new copy of them here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

from ...core.errors import CadrumoError
from ...core.identity import ProfileId
from .aggregate import ProfileRestoreAuthority
from .custody_ports import read_profile_custody_capsule_source
from .recovery_custody import restore_profile_from_recovery_artifact, restore_profile_with_password

if TYPE_CHECKING:
    from pathlib import Path

    from .aggregate import CommittedProfileView
    from .custody_ports import (
        ProfileCustodyEnvelopePort,
        ProfileCustodySentinelPort,
    )

_ENVELOPE_RELATIVE = ("custody", "envelope.v1.json")
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
    """Always false: restore proofs never install recovery in the destination."""


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
        A :class:`ProfileRestoreOutcome` naming the proving door.
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
        A :class:`ProfileRestoreOutcome` naming the proving door.
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
        recovery_enrolled=False,
    )


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
