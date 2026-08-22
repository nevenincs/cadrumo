"""Per-profile recovery custody: enrollment, portable artifact, restore doors.

This module is the application's whole recovery surface, and it is
deliberately narrow. A profile's data-encryption key may be wrapped a second
time under a recovery secret; that second wrapper can be exported as a
portable artifact; and a capsule can be republished under a named, proven
authority. Nothing here mints, rotates, replaces, or re-derives a key
schedule, and nothing here installs recovery onto a capsule that is already
committed.

**A recovery artifact is a second door to the same records.** It leaves the
encrypted store by design, so every decision about it is an exposure
decision. Three properties carry that weight, and none of them is advisory.

The secret is a 24-word BIP-39 mnemonic over 256 bits of entropy, never an
operator-typed string. Once an artifact is off the machine its only remaining
barrier is the KDF cost applied to the secret's entropy, and a human-chosen
string does not survive offline guessing at any cost a login can afford to
spend. The mnemonic makes that attack infeasible; it also makes the secret a
BEARER credential, which is why the export's store-separately and
retained-copy warnings are mandatory rather than cosmetic.

The destination is refused rather than warned about. An artifact written
inside the Cadrumo storage root sits with the ciphertext it unwraps; a
relative destination resolves against a directory the operator did not
choose. Both are refused by the custody owner before any secret is spent.

The artifact is identity-BOUND while being machine-PORTABLE. It carries the
profile UUID and DEK epoch it was minted for, and every read of it checks
both against the target it is being used against, so it moves to another
machine for the same profile and refuses to become a different profile's
authority.

:class:`~cadrumo.application.user_profile.CommittedProfileView` is what a
successful restore projects; :data:`ProfileRestoreAuthority` is the axis that
records which door proved it.
"""

from __future__ import annotations

from dataclasses import dataclass
from secrets import token_bytes
from typing import TYPE_CHECKING

from ...adapters.persistence.storage.custody import ProfileCustodyRecoveryArtifactWarning
from ._capsule_record import ProfileRecordSession
from ._custody_ports import (
    create_profile_recovery_enrollment_material,
    prove_profile_recovery_artifact,
    unlock_profile_custody_password,
)
from ._custody_ports import (
    export_profile_recovery_artifact as _export_recovery_artifact,
)
from ._lifecycle import ProfileCapsuleLifecycle

if TYPE_CHECKING:
    from pathlib import Path
    from uuid import UUID

    from ...adapters.persistence.storage import RecoveryKey
    from ._aggregate import CommittedProfileView, ProfileRestoreAuthority
    from ._custody_ports import (
        ProfileCustodyEnvelopePort,
        ProfileCustodyRecoveryEnvelopePort,
        ProfileCustodySentinelPort,
    )

_RECOVERY_KDF_SALT_BYTES = 16


@dataclass(frozen=True, slots=True)
class ProfileRecoveryEnrollment:
    """One optional recovery wrapper and the secret that opens it.

    The secret rides in its wipeable container rather than as a ``str``: the
    operator holds it across an interactive confirmation lasting as long as
    it takes a human to copy down 24 words, and a string copy is unreachable
    by any wipe primitive for its whole lifetime. The caller owns the wipe
    and should take it as early as the flow allows.
    """

    envelope: ProfileCustodyRecoveryEnvelopePort
    recovery_key: RecoveryKey


@dataclass(frozen=True, slots=True)
class ProfileRecoveryArtifactReceipt:
    """Non-secret record of one durable artifact export.

    Carries no key material -- the wrapped DEK is in the file, not here --
    so this can be rendered, logged by an operator surface, or returned
    across a command boundary without widening exposure.
    """

    profile_id: UUID
    dek_epoch: str
    artifact_digest: str
    target: Path
    warnings: tuple[ProfileCustodyRecoveryArtifactWarning, ...]


@dataclass(frozen=True, slots=True)
class _SuppliedPasswordMaterial:
    """The envelope and sentinel of a capsule that is not committed yet.

    The committed-capsule loader cannot serve a restore: the capsule being
    restored is by definition not published, so its material arrives from
    the caller and is proved here instead of being read from a path.
    """

    envelope: ProfileCustodyEnvelopePort
    sentinel: ProfileCustodySentinelPort


def enroll_profile_recovery(
    *,
    profile_id: UUID,
    dek: bytes,
    dek_epoch: str,
) -> ProfileRecoveryEnrollment:
    """Mint one optional recovery wrapper over a profile's existing key.

    Enrollment wraps the DEK the caller already holds; it does not generate,
    replace, or re-derive one. That is what makes it additive rather than a
    key-management action: the password path is untouched, so a failed or
    abandoned enrollment can strand nothing.

    Call this only while creating a profile. A capsule that is already
    committed has no in-place recovery installation path, and inventing one
    would mean a second writer into a published capsule.
    """
    material = create_profile_recovery_enrollment_material(
        profile_id=profile_id,
        dek=dek,
        dek_epoch=dek_epoch,
        salt=token_bytes(_RECOVERY_KDF_SALT_BYTES),
    )
    return ProfileRecoveryEnrollment(envelope=material.envelope, recovery_key=material.recovery_key)


def export_profile_recovery_artifact(
    enrollment: ProfileRecoveryEnrollment,
    *,
    current_password: str,
    password_envelope: ProfileCustodyEnvelopePort,
    sentinel: ProfileCustodySentinelPort,
    target: Path,
) -> ProfileRecoveryArtifactReceipt:
    """Write the portable artifact after proving the operator's current password.

    The password proof is the authorisation, not a formality: an artifact is
    a durable second door, so producing one must require the door that
    already exists. The write is exclusive -- an existing destination is
    refused rather than replaced -- and the destination itself is refused
    outright when it is relative, indirect, or inside the storage root.

    The returned warnings are the artifact's own mandatory set and are not
    optional to surface. They state what an operator cannot infer from a
    successful write: that the file is offline-guessable material, that it
    must not be stored with the data it unwraps, that a copy which has been
    exported cannot be recalled, and that losing it does not lock them out
    while they still have their password.
    """
    receipt = _export_recovery_artifact(
        enrollment.envelope,
        current_password=current_password,
        password_envelope=password_envelope,
        sentinel=sentinel,
        target=target,
    )
    return ProfileRecoveryArtifactReceipt(
        profile_id=receipt.artifact.profile_id,
        dek_epoch=receipt.artifact.dek_epoch,
        artifact_digest=receipt.artifact.self_digest,
        target=receipt.target,
        warnings=receipt.warnings,
    )


def restore_profile_with_password(
    *,
    label: str,
    password: str,
    password_envelope: ProfileCustodyEnvelopePort,
    sentinel: ProfileCustodySentinelPort,
    database_bytes: bytes,
    recovery_envelope: ProfileCustodyRecoveryEnvelopePort | None = None,
    root: Path | None = None,
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
    unlock = unlock_profile_custody_password(
        _SuppliedPasswordMaterial(envelope=password_envelope, sentinel=sentinel),
        password=password,
    )
    return _publish_restored_capsule(
        label=label,
        password_envelope=password_envelope,
        sentinel=sentinel,
        dek=unlock.dek,
        database_bytes=database_bytes,
        authority="password",
        root=root,
        recovery_envelope=recovery_envelope,
    )


def restore_profile_from_recovery_artifact(
    *,
    label: str,
    artifact_source: Path,
    recovery_secret: str,
    password_envelope: ProfileCustodyEnvelopePort,
    sentinel: ProfileCustodySentinelPort,
    database_bytes: bytes,
    recovery_envelope: ProfileCustodyRecoveryEnvelopePort | None = None,
    root: Path | None = None,
) -> CommittedProfileView:
    """Republish one capsule proving a portable artifact instead of the password.

    What this recovers and what it does not are both worth stating, because
    the gap between them is where an operator would otherwise be misled.

    It recovers the DATA path: the artifact's wrapped key is proved against
    the capsule's own sentinel, so the republished capsule is known to be
    openable by the key its database was encrypted under.

    It does NOT recover password access. The capsule is republished under
    its EXISTING password envelope, unchanged, because changing it would be
    credential rotation -- a separate capability this build does not have.
    An operator who has genuinely lost their password gets their records
    back onto a valid capsule and still cannot log in with a password they
    do not know.

    The artifact is refused unless it names this exact profile and DEK
    epoch, checked once on read and again on unlock, so an artifact minted
    for another profile cannot become this one's authority.
    """
    proof = prove_profile_recovery_artifact(
        artifact_source,
        recovery_secret=recovery_secret,
        expected_profile_id=password_envelope.profile_id,
        expected_dek_epoch=password_envelope.dek_epoch,
        sentinel=sentinel,
    )
    return _publish_restored_capsule(
        label=label,
        password_envelope=password_envelope,
        sentinel=sentinel,
        dek=proof.dek,
        database_bytes=database_bytes,
        authority="recovery_artifact",
        root=root,
        recovery_envelope=recovery_envelope,
    )


def _publish_restored_capsule(
    *,
    label: str,
    password_envelope: ProfileCustodyEnvelopePort,
    sentinel: ProfileCustodySentinelPort,
    dek: bytes,
    database_bytes: bytes,
    authority: ProfileRestoreAuthority,
    root: Path | None,
    recovery_envelope: ProfileCustodyRecoveryEnvelopePort | None = None,
) -> CommittedProfileView:
    """Bind a proved key to one record session and publish exactly once.

    ``recovery_envelope`` is carried forward rather than dropped. Recovery is
    installable only at publication, and a restore IS a publication -- so a
    republished capsule that omitted the wrapper it had would leave the
    operator with a working profile whose second door had silently closed,
    with no way to reopen it and nothing said. Passing it through is what
    makes a restore preserve the profile rather than merely reproduce its
    records; the wrapper is unchanged material, so the phrase the operator
    already holds keeps working.
    """
    session = ProfileRecordSession.from_envelope(envelope=password_envelope, dek=dek)
    try:
        return ProfileCapsuleLifecycle(root=root).restore(
            label=label,
            password_envelope=password_envelope,
            sentinel=sentinel,
            data_files={},
            record_session=session,
            database_bytes=database_bytes,
            authority=authority,
            recovery_envelope=recovery_envelope,
        )
    finally:
        session.close()


__all__ = [
    "ProfileRecoveryArtifactReceipt",
    "ProfileRecoveryEnrollment",
    "enroll_profile_recovery",
    "export_profile_recovery_artifact",
    "restore_profile_from_recovery_artifact",
    "restore_profile_with_password",
]
