"""Change a profile's password without changing the key it protects.

Rotation re-mints the password envelope over the SAME data-encryption key.
That distinction is the whole design: a re-key would have to re-encrypt every
record the profile holds and would invalidate the committed sentinel and any
recovery code the operator is keeping, while a re-wrap touches exactly one
file and leaves every other custody fact standing.

Two invariants make that safe, and both are enforced rather than assumed.

The DEK epoch is preserved. The committed sentinel and the recovery wrapper
are bound to ``(profile_id, dek_epoch)`` and to neither the password
envelope's digest nor its generation, so holding the epoch keeps an
already-issued recovery code working. Minting a fresh epoch here would
silently destroy the only second door a taxpayer holds, at the moment they
change their password and with no error to show for it.

The record row is re-headed in the same span. A row's write provenance folds
the envelope digest and the password generation, so a bare envelope swap
leaves a profile that authenticates under the new password and then cannot
read its own record.

See Also:
    :func:`~cadrumo.application.user_profile.registration.register_profile_with_credentials`
        The creation door, which mints the first envelope this one replaces.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from secrets import token_bytes
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ...core.credentials import assess_profile_password
from ...core.errors.hierarchy import CadrumoError
from ...core.identity.profile import ProfileId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.paths import effective_storage_root
from ...core.time.clock import now as _now
from ...domain.buckets.event import BucketEventType
from .authentication import ProfilePasswordProofOperation
from .capsule_record import ProfileRecordCommandEvent, ProfileRecordSession, ProfileRecordStore
from .custody_ports import (
    create_profile_custody_registration_material,
    load_profile_custody_password_material,
    map_profile_authentication_proof_failure,
    profile_custody_recovery_envelope_path,
    replace_profile_custody_password_envelope,
    unlock_profile_custody_password,
)
from .custody_repository import profile_custody_transaction_lock
from .prospective_password import ProspectiveProfilePasswordRefusal, prospective_profile_password_refusal

if TYPE_CHECKING:
    from pathlib import Path
    from uuid import UUID

    from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext
    from .custody_ports import ProfileCustodyEnvelopePort

_ENVELOPE_KDF_SALT_BYTES = 16


class ProfilePassphraseReplacementProof(StrEnum):
    """Which proof authorised one passphrase replacement.

    Both doors publish the same lifecycle event -- the password wrapper was
    re-minted over the same data key -- so the proof is a payload descriptor
    rather than a second event type. Without it a profile's history cannot
    tell an operator who knew their passphrase from one who used the recovery
    code because they did not, which is exactly the distinction an audit of
    custody changes needs.
    """

    CURRENT_CREDENTIAL = "current_passphrase"
    RECOVERY_CODE = "recovery_code"


class ProfilePassphraseRotationError(CadrumoError):
    """Raised when a passphrase change cannot be honoured as supplied."""

    def __init__(
        self,
        message: str | None = None,
        *,
        context: Mapping[str, object] | None = None,
        translated_message: str | None = None,
        password_refusal: ProspectiveProfilePasswordRefusal | None = None,
    ) -> None:
        """Retain a typed prospective refusal without retaining the password."""
        super().__init__(message, context=context, translated_message=translated_message)
        self._password_refusal = password_refusal

    @property
    def password_refusal(self) -> ProspectiveProfilePasswordRefusal | None:
        """Retain the typed refusal for trusted in-process consumers only."""
        return self._password_refusal


class ProfilePassphraseRotationOutcome(BaseModel):
    """Typed result of one completed rotation.

    Carries no key material and no passphrase: only the non-secret facts a
    surface needs to tell the operator what changed and what did not.
    """

    model_config = STRICT_FROZEN_CONFIG

    profile_id: ProfileId
    password_generation: int = Field(ge=2)
    dek_epoch_preserved: bool
    recovery_enrollment_retained: bool


def rotate_profile_passphrase(
    *,
    profile_id: UUID,
    current_passphrase: str,
    new_passphrase: str,
    new_passphrase_confirmation: str,
    root: Path | None = None,
    profile_decode_context: ProfileDecodeContext,
) -> ProfilePassphraseRotationOutcome:
    """Re-wrap ``profile_id``'s data key under ``new_passphrase``.

    Fails closed at every step before the swap: a wrong current passphrase, a
    new one outside the profile-password contract, or a confirmation that does not match
    all refuse with the committed envelope untouched and still usable.

    The confirmation is compared here as well as at whatever surface collected
    it. A caller reaching this function directly must not be able to skip the
    check simply by not having a command line.

    Args:
        profile_id: The profile whose password wrapper to replace.
        current_passphrase: Proof of the existing credential. Never logged.
        new_passphrase: The replacement credential. Must satisfy the canonical
            profile-password contract.
        new_passphrase_confirmation: Must equal ``new_passphrase``.
        root: Storage root override; the effective root when omitted.
        profile_decode_context: Decode context supplied by the enclosing
            pinned authority operation for the authenticated record.

    Returns:
        A :class:`ProfilePassphraseRotationOutcome` naming the new generation.

    Raises:
        ProfilePassphraseRotationError: When the confirmation does not match,
            the new passphrase is invalid, or the current one does not open
            the committed envelope.
    """
    if new_passphrase != new_passphrase_confirmation:
        raise ProfilePassphraseRotationError(
            translated_message="application.user_profile.errors.passphrase_confirmation_mismatch",
        )
    password_refusal = prospective_profile_password_refusal(assess_profile_password(new_passphrase))
    if password_refusal is not None:
        raise ProfilePassphraseRotationError(
            translated_message=password_refusal.translated_message,
            context=password_refusal.context,
            password_refusal=password_refusal,
        )

    storage_root = effective_storage_root(root)
    with profile_custody_transaction_lock(storage_root, profile_id):
        material = load_profile_custody_password_material(profile_id, root=storage_root)
        current = material.envelope
        try:
            unlock = unlock_profile_custody_password(material, password=current_passphrase)
        except CadrumoError as exc:
            # Recognised through the custody boundary's own predicate rather
            # than by importing its exception type, which is the arrangement
            # that keeps the adapter's error family off this port. Anything
            # that is not a password-proof refusal is a different fault and
            # travels on unchanged.
            refusal = map_profile_authentication_proof_failure(
                exc,
                operation=ProfilePasswordProofOperation.ROTATION,
            )
            if refusal is None:
                raise
            # Refused before anything is written, so the existing wrapper is
            # byte-identical to what it was and still opens under the password
            # the operator already has.
            raise ProfilePassphraseRotationError(
                translated_message="application.user_profile.errors.passphrase_current_rejected",
            ) from refusal

        rotated = rewrap_profile_passphrase_under_lock(
            profile_id=profile_id,
            dek=unlock.dek,
            current=current,
            new_passphrase=new_passphrase,
            proof=ProfilePassphraseReplacementProof.CURRENT_CREDENTIAL,
            storage_root=storage_root,
            profile_decode_context=profile_decode_context,
        )

    return ProfilePassphraseRotationOutcome(
        profile_id=str(profile_id),
        password_generation=rotated.password_generation,
        dek_epoch_preserved=rotated.dek_epoch == current.dek_epoch,
        recovery_enrollment_retained=profile_custody_recovery_envelope_path(material.capsule_path).exists(),
    )


def rewrap_profile_passphrase_under_lock(
    *,
    profile_id: UUID,
    dek: bytes,
    current: ProfileCustodyEnvelopePort,
    new_passphrase: str,
    proof: ProfilePassphraseReplacementProof,
    storage_root: Path,
    profile_decode_context: ProfileDecodeContext,
) -> ProfileCustodyEnvelopePort:
    """Re-head the record and swap the password envelope over an already-proven DEK.

    The shared second half of every passphrase replacement. The caller holds
    the custody transaction lock and has proven ``dek`` through whichever door
    authorises the change: the current passphrase for a rotation, or the
    enrolled recovery code for a reset. Nothing here re-proves anything, so
    this must not be reachable from a surface that has not. ``proof`` names
    that door, and is recorded on the lifecycle event so the profile's
    history says which one was used.

    The replacement is minted as ``current``'s successor: the next password
    generation, naming ``current``'s self-digest as its predecessor. The
    custody write refuses anything else.

    Returns:
        The committed replacement envelope.
    """
    rotated = create_profile_custody_registration_material(
        profile_id=profile_id,
        password=new_passphrase,
        dek=dek,
        # Held, never re-minted. See the module docstring: a fresh epoch
        # strands the committed sentinel and the enrolled recovery envelope,
        # silently.
        dek_epoch=current.dek_epoch,
        salt=token_bytes(_ENVELOPE_KDF_SALT_BYTES),
        predecessor=current,
    ).envelope

    # Re-head FIRST, then swap. A crash between the two steps must leave a
    # profile that is still openable, and the ordering decides which way
    # that falls: a re-headed row under the old envelope is unreadable
    # until the swap completes, while a swapped envelope over an old row
    # is unreadable until the re-head completes. Neither is worse than the
    # other on its own -- but only one of them can be finished by a
    # recovery that knows the operator's NEW password, and after the swap
    # the old password no longer opens anything. So the step that needs
    # the old credential goes first.
    occurred_at = _now()
    old_session = ProfileRecordSession.from_envelope(
        envelope=current,
        dek=dek,
        profile_decode_context=profile_decode_context,
    )
    new_session = ProfileRecordSession.from_envelope(
        envelope=rotated,
        dek=dek,
        profile_decode_context=profile_decode_context,
    )
    try:
        ProfileRecordStore(session=old_session, root=storage_root).rehead_under_rotated_envelope(
            rotated=new_session,
            event=ProfileRecordCommandEvent(
                event_type=BucketEventType.PROFILE_PASSPHRASE_ROTATED,
                occurred_at=occurred_at.isoformat(),
                payload={"proof": proof.value},
            ),
        )
        replace_profile_custody_password_envelope(
            profile_id=profile_id,
            current=current,
            rotated=rotated,
            root=storage_root,
        )
    finally:
        old_session.close()
        new_session.close()
    return rotated


__all__ = [
    "ProfilePassphraseReplacementProof",
    "ProfilePassphraseRotationError",
    "ProfilePassphraseRotationOutcome",
    "rewrap_profile_passphrase_under_lock",
    "rotate_profile_passphrase",
]
