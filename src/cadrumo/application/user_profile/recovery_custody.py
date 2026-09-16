"""Optional per-profile recovery: enrol, revoke, inspect, and reset the passphrase.

Recovery is a second wrapper over the same data-encryption key, opened by a
minted recovery code instead of the operator's passphrase. It is off by
default. An operator who wants it enrols after the profile exists, proves the
current passphrase to do so, and copies the code down once; the code is never
persisted, never logged, and never enters a result envelope. The only thing
the code is good for is :func:`reset_profile_passphrase_with_recovery`: it
proves the enrolled wrapper against the capsule's own sentinel and re-wraps
the key under a new passphrase, so a forgotten passphrase is replaced rather
than the records lost.

Every door here works on a COMMITTED capsule under its custody transaction
lock. Nothing mints, rotates, or re-derives a key schedule; the DEK epoch is
preserved throughout, which is what keeps an enrolled code valid across
ordinary passphrase changes.

See Also:
    :func:`~cadrumo.application.user_profile.passphrase_rotation.rotate_profile_passphrase`
        The passphrase-proved sibling of the reset door; both share one
        re-wrap primitive.
"""

from __future__ import annotations

from dataclasses import dataclass
from hmac import compare_digest
from secrets import token_bytes
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...core.credentials import assess_profile_password
from ...core.errors.hierarchy import CadrumoError
from ...core.identity.profile import ProfileId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.paths import effective_storage_root
from .authentication import ProfilePasswordProofOperation
from .custody_ports import (
    create_profile_recovery_enrollment_material,
    install_profile_recovery_envelope,
    load_profile_custody_password_material,
    load_profile_custody_recovery_material,
    map_profile_authentication_proof_failure,
    profile_custody_recovery_envelope_path,
    remove_profile_recovery_envelope,
    unlock_profile_custody_password,
    unlock_profile_custody_recovery,
)
from .custody_repository import profile_custody_transaction_lock
from .passphrase_rotation import rewrap_profile_passphrase_under_lock
from .prospective_password import ProspectiveProfilePasswordRefusal, prospective_profile_password_refusal

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path
    from uuid import UUID

    from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext
    from .custody_ports import (
        ProfileCustodyPasswordMaterialPort,
        ProfileCustodyRecoveryEnvelopePort,
        ProfileCustodyUnlockPort,
        ProfileRecoveryKeyPort,
    )

_RECOVERY_KDF_SALT_BYTES = 16


class ProfileRecoveryError(CadrumoError):
    """Raised when a recovery door cannot be honoured as supplied."""

    def __init__(
        self,
        message: str | None = None,
        *,
        context: dict[str, object] | None = None,
        translated_message: str | None = None,
        password_refusal: ProspectiveProfilePasswordRefusal | None = None,
    ) -> None:
        """Retain a typed prospective refusal without retaining any secret."""
        super().__init__(message, context=context, translated_message=translated_message)
        self._password_refusal = password_refusal

    @property
    def password_refusal(self) -> ProspectiveProfilePasswordRefusal | None:
        """Retain the typed refusal for trusted in-process consumers only."""
        return self._password_refusal


@dataclass(frozen=True, slots=True)
class ProfileRecoveryEnrollment:
    """One minted recovery wrapper and the secret that opens it.

    The secret rides in its wipeable container rather than as a ``str``: the
    operator holds it across an interactive confirmation lasting as long as
    it takes a human to copy a code down, and a string copy is unreachable
    by any wipe primitive for its whole lifetime. The enrolment door owns the
    wipe and takes it as soon as the handover returns.
    """

    envelope: ProfileCustodyRecoveryEnvelopePort
    recovery_key: ProfileRecoveryKeyPort


class ProfileRecoveryStatus(BaseModel):
    """Whether one committed profile currently has recovery enrolled."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: ProfileId
    enrolled: bool


class ProfileRecoveryEnrollmentOutcome(BaseModel):
    """Non-secret result of one completed enrolment or revocation."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: ProfileId
    enrolled: bool
    changed: bool


class ProfilePassphraseResetOutcome(BaseModel):
    """Non-secret result of one passphrase reset proved by the recovery code."""

    model_config = STRICT_FROZEN_CONFIG

    profile_id: ProfileId
    password_generation: int = Field(ge=2)
    dek_epoch_preserved: bool
    recovery_enrollment_retained: bool


def profile_recovery_status(*, profile_id: UUID, root: Path | None = None) -> ProfileRecoveryStatus:
    """Report whether ``profile_id`` has a recovery wrapper enrolled.

    Reads only the committed capsule's layout; no secret is required and no
    key material is touched.
    """
    material = load_profile_custody_password_material(profile_id, root=effective_storage_root(root))
    return ProfileRecoveryStatus(
        profile_id=str(profile_id),
        enrolled=profile_custody_recovery_envelope_path(material.capsule_path).exists(),
    )


def enroll_profile_recovery(
    *,
    profile_id: UUID,
    current_passphrase: str,
    recovery_handover: Callable[[ProfileRecoveryEnrollment], str],
    root: Path | None = None,
) -> ProfileRecoveryEnrollmentOutcome:
    """Mint a recovery code for a committed profile and install its wrapper.

    The current passphrase is the authorisation: a second door onto the
    records may only be opened by someone who already holds the first. The
    code is delivered through ``recovery_handover`` and nowhere else, and the
    callback must return the exact code it received as possession proof. The
    wrapper is installed only after that proof matches, so an operator who
    could not copy the code down is left exactly where they started rather
    than enrolled under a secret nobody holds.

    Args:
        profile_id: The committed profile to enrol.
        current_passphrase: Proof of the existing credential. Never logged.
        recovery_handover: The one channel the code reaches the operator
            through. It is invoked once, before anything is written, and the
            key is wiped by the time this returns. Raising from the callback
            aborts the enrolment.
        root: Storage root override; the effective root when omitted.

    Raises:
        ProfileRecoveryError: When the profile is already enrolled, the
            passphrase does not open the committed envelope, or the returned
            proof differs from the minted code.
    """
    storage_root = effective_storage_root(root)
    with profile_custody_transaction_lock(storage_root, profile_id):
        material = load_profile_custody_password_material(profile_id, root=storage_root)
        if profile_custody_recovery_envelope_path(material.capsule_path).exists():
            raise ProfileRecoveryError(
                translated_message="application.user_profile.errors.recovery_already_enrolled",
            )
        unlock = _unlock_with_passphrase(
            material,
            passphrase=current_passphrase,
            operation=ProfilePasswordProofOperation.RECOVERY_ENROLL,
        )
        minted = create_profile_recovery_enrollment_material(
            profile_id=profile_id,
            dek=unlock.dek,
            dek_epoch=material.envelope.dek_epoch,
            salt=token_bytes(_RECOVERY_KDF_SALT_BYTES),
        )
        enrollment = ProfileRecoveryEnrollment(envelope=minted.envelope, recovery_key=minted.recovery_key)
        with enrollment.recovery_key:
            supplied_proof = recovery_handover(enrollment)
            try:
                if not compare_digest(supplied_proof, enrollment.recovery_key.code):
                    raise ProfileRecoveryError(
                        translated_message="application.user_profile.errors.recovery_possession_mismatch",
                    )
            finally:
                del supplied_proof
        install_profile_recovery_envelope(profile_id=profile_id, envelope=enrollment.envelope, root=storage_root)
    return ProfileRecoveryEnrollmentOutcome(profile_id=str(profile_id), enrolled=True, changed=True)


def revoke_profile_recovery(
    *,
    profile_id: UUID,
    current_passphrase: str,
    root: Path | None = None,
) -> ProfileRecoveryEnrollmentOutcome:
    """Remove the enrolled recovery wrapper after proving the current passphrase.

    Idempotent: a profile that is not enrolled is reported unchanged rather
    than refused, because the operator's intent ("no recovery on this
    profile") already holds. The passphrase is still proved first, so the
    unchanged answer never discloses enrolment state to someone without it.
    """
    storage_root = effective_storage_root(root)
    with profile_custody_transaction_lock(storage_root, profile_id):
        material = load_profile_custody_password_material(profile_id, root=storage_root)
        _unlock_with_passphrase(
            material,
            passphrase=current_passphrase,
            operation=ProfilePasswordProofOperation.RECOVERY_REVOKE,
        )
        if not profile_custody_recovery_envelope_path(material.capsule_path).exists():
            return ProfileRecoveryEnrollmentOutcome(profile_id=str(profile_id), enrolled=False, changed=False)
        recovery = load_profile_custody_recovery_material(profile_id, root=storage_root)
        remove_profile_recovery_envelope(profile_id=profile_id, current=recovery.recovery_envelope, root=storage_root)
    return ProfileRecoveryEnrollmentOutcome(profile_id=str(profile_id), enrolled=False, changed=True)


def reset_profile_passphrase_with_recovery(
    *,
    profile_id: UUID,
    recovery_code: str,
    new_passphrase: str,
    new_passphrase_confirmation: str,
    root: Path | None = None,
    profile_decode_context: ProfileDecodeContext,
) -> ProfilePassphraseResetOutcome:
    """Replace a forgotten passphrase by proving the enrolled recovery code.

    The recovery code unwraps the DEK from the enrolled wrapper, the result
    is proved against the capsule's own sentinel, and only then is the
    password envelope re-minted under ``new_passphrase`` through the same
    primitive an ordinary rotation uses. The DEK epoch is preserved, so the
    recovery wrapper stays enrolled and the same code keeps working.

    Fails closed at every step before the swap: a profile without recovery,
    a wrong code, a new passphrase outside the profile-password contract, or
    a mismatched confirmation all refuse with the committed envelope untouched.

    Raises:
        ProfileRecoveryError: When recovery is not enrolled, the confirmation
            does not match, the new passphrase is invalid, or the code does
            not open the enrolled wrapper.
    """
    if new_passphrase != new_passphrase_confirmation:
        raise ProfileRecoveryError(
            translated_message="application.user_profile.errors.passphrase_confirmation_mismatch",
        )
    password_refusal = prospective_profile_password_refusal(assess_profile_password(new_passphrase))
    if password_refusal is not None:
        raise ProfileRecoveryError(
            translated_message=password_refusal.translated_message,
            context=dict(password_refusal.context),
            password_refusal=password_refusal,
        )

    storage_root = effective_storage_root(root)
    with profile_custody_transaction_lock(storage_root, profile_id):
        password = load_profile_custody_password_material(profile_id, root=storage_root)
        if not profile_custody_recovery_envelope_path(password.capsule_path).exists():
            raise ProfileRecoveryError(
                translated_message="application.user_profile.errors.recovery_not_enrolled",
            )
        recovery = load_profile_custody_recovery_material(profile_id, root=storage_root)
        try:
            unlock = unlock_profile_custody_recovery(recovery, recovery_secret=recovery_code)
        except CadrumoError as exc:
            refusal = map_profile_authentication_proof_failure(
                exc,
                operation=ProfilePasswordProofOperation.RECOVERY_RESET,
            )
            if refusal is None:
                raise
            raise ProfileRecoveryError(
                translated_message="application.user_profile.errors.recovery_code_rejected",
            ) from refusal
        current = recovery.password_envelope
        rotated = rewrap_profile_passphrase_under_lock(
            profile_id=profile_id,
            dek=unlock.dek,
            current=current,
            new_passphrase=new_passphrase,
            storage_root=storage_root,
            profile_decode_context=profile_decode_context,
        )
    return ProfilePassphraseResetOutcome(
        profile_id=str(profile_id),
        password_generation=rotated.password_generation,
        dek_epoch_preserved=rotated.dek_epoch == current.dek_epoch,
        recovery_enrollment_retained=profile_custody_recovery_envelope_path(recovery.capsule_path).exists(),
    )


def _unlock_with_passphrase(
    material: ProfileCustodyPasswordMaterialPort,
    *,
    passphrase: str,
    operation: ProfilePasswordProofOperation,
) -> ProfileCustodyUnlockPort:
    """Prove the current passphrase, or refuse without disclosing why."""
    try:
        return unlock_profile_custody_password(material, password=passphrase)
    except CadrumoError as exc:
        refusal = map_profile_authentication_proof_failure(exc, operation=operation)
        if refusal is None:
            raise
        raise ProfileRecoveryError(
            translated_message="application.user_profile.errors.passphrase_current_rejected",
        ) from refusal


__all__ = [
    "ProfilePassphraseResetOutcome",
    "ProfileRecoveryEnrollment",
    "ProfileRecoveryEnrollmentOutcome",
    "ProfileRecoveryError",
    "ProfileRecoveryStatus",
    "enroll_profile_recovery",
    "profile_recovery_status",
    "reset_profile_passphrase_with_recovery",
    "revoke_profile_recovery",
]
