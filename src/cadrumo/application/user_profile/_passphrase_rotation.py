"""Change a profile's password without changing the key it protects.

Rotation re-mints the password envelope over the SAME data-encryption key.
That distinction is the whole design: a re-key would have to re-encrypt every
record the profile holds and would invalidate the committed sentinel and any
recovery artifact the operator is keeping, while a re-wrap touches exactly one
file and leaves every other custody fact standing.

Two invariants make that safe, and both are enforced rather than assumed.

The DEK epoch is preserved. The committed sentinel and the recovery wrapper
are bound to ``(profile_id, dek_epoch)`` and to neither the password
envelope's digest nor its generation, so holding the epoch keeps an
already-issued recovery phrase working. Minting a fresh epoch here would
silently destroy the only second door a taxpayer holds, at the moment they
change their password and with no error to show for it.

The record row is re-headed in the same span. A row's write provenance folds
the envelope digest and the password generation, so a bare envelope swap
leaves a profile that authenticates under the new password and then cannot
read its own record.

See Also:
    :func:`~cadrumo.application.user_profile.register_profile_with_credentials`
        The creation door, which mints the first envelope this one replaces.
"""

from __future__ import annotations

from secrets import token_bytes
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.persistence.storage import custody
from ...core.errors import CadrumoError
from ...core.hashing import prefixed_digest
from ...core.identity import ProfileId
from ...core.paths import effective_storage_root
from ...core.time import now as _now
from ...domain.buckets import BucketEventType
from ._capsule_record import ProfileRecordCommandEvent, ProfileRecordSession, ProfileRecordStore
from ._custody_ports import (
    create_profile_custody_registration_material,
    profile_custody_recovery_envelope_path,
    profile_is_password_authentication_failure,
    unlock_profile_custody_password,
)
from ._custody_repository import profile_custody_transaction_lock
from ._registration import PASSPHRASE_MINIMUM_LENGTH, assess_passphrase

if TYPE_CHECKING:
    from pathlib import Path
    from uuid import UUID

_ENVELOPE_KDF_SALT_BYTES = 16


class ProfilePassphraseRotationError(CadrumoError):
    """Raised when a passphrase change cannot be honoured as supplied."""


class ProfilePassphraseRotationOutcome(BaseModel):
    """Typed result of one completed rotation.

    Carries no key material and no passphrase: only the non-secret facts a
    surface needs to tell the operator what changed and what did not.
    """

    model_config = ConfigDict(frozen=True)

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
) -> ProfilePassphraseRotationOutcome:
    """Re-wrap ``profile_id``'s data key under ``new_passphrase``.

    Fails closed at every step before the swap: a wrong current passphrase, a
    new one below the verifier minimum, or a confirmation that does not match
    all refuse with the committed envelope untouched and still usable.

    The confirmation is compared here as well as at whatever surface collected
    it. A caller reaching this function directly must not be able to skip the
    check simply by not having a command line.

    Args:
        profile_id: The profile whose password wrapper to replace.
        current_passphrase: Proof of the existing credential. Never logged.
        new_passphrase: The replacement credential. Must clear the NIST
            verifier minimum.
        new_passphrase_confirmation: Must equal ``new_passphrase``.
        root: Storage root override; the effective root when omitted.

    Returns:
        A :class:`ProfilePassphraseRotationOutcome` naming the new generation.

    Raises:
        ProfilePassphraseRotationError: When the confirmation does not match,
            the new passphrase is too short, or the current one does not open
            the committed envelope.
    """
    if new_passphrase != new_passphrase_confirmation:
        raise ProfilePassphraseRotationError(
            translated_message="application.user_profile.errors.passphrase_confirmation_mismatch",
        )
    assessment = assess_passphrase(new_passphrase)
    if not assessment.acceptable:
        raise ProfilePassphraseRotationError(
            translated_message="application.user_profile.errors.registration_passphrase_too_short",
            context={"minimum_length": str(PASSPHRASE_MINIMUM_LENGTH)},
        )

    storage_root = effective_storage_root(root)
    with profile_custody_transaction_lock(storage_root, profile_id):
        material = custody.load_committed_profile_password_material(profile_id, root=storage_root)
        current = material.envelope
        try:
            unlock = unlock_profile_custody_password(material, password=current_passphrase)
        except CadrumoError as exc:
            # Recognised through the custody boundary's own predicate rather
            # than by importing its exception type, which is the arrangement
            # that keeps the adapter's error family off this port. Anything
            # that is not a password-proof refusal is a different fault and
            # travels on unchanged.
            if not profile_is_password_authentication_failure(exc):
                raise
            # Refused before anything is written, so the existing wrapper is
            # byte-identical to what it was and still opens under the password
            # the operator already has.
            raise ProfilePassphraseRotationError(
                translated_message="application.user_profile.errors.passphrase_current_rejected",
            ) from exc

        rotated = create_profile_custody_registration_material(
            profile_id=profile_id,
            password=new_passphrase,
            dek=unlock.dek,
            # Held, never re-minted. See the module docstring: a fresh epoch
            # strands the committed sentinel and every outstanding recovery
            # artifact, silently.
            dek_epoch=current.dek_epoch,
            salt=token_bytes(_ENVELOPE_KDF_SALT_BYTES),
            password_generation=current.password_generation + 1,
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
        old_session = ProfileRecordSession.from_envelope(envelope=current, dek=unlock.dek)
        new_session = ProfileRecordSession.from_envelope(envelope=rotated, dek=unlock.dek)
        try:
            ProfileRecordStore(session=old_session, root=storage_root).rehead_under_rotated_envelope(
                rotated=new_session,
                event=ProfileRecordCommandEvent(
                    event_type=BucketEventType.PROFILE_PASSPHRASE_ROTATED,
                    occurred_at=occurred_at.isoformat(),
                ),
            )
            custody.replace_committed_profile_custody_envelope(
                profile_id,
                rotated.canonical_json_bytes(),
                expected_sha256=prefixed_digest(current.canonical_json_bytes()),
                root=storage_root,
            )
        finally:
            old_session.close()
            new_session.close()

    return ProfilePassphraseRotationOutcome(
        profile_id=str(profile_id),
        password_generation=rotated.password_generation,
        dek_epoch_preserved=rotated.dek_epoch == current.dek_epoch,
        recovery_enrollment_retained=profile_custody_recovery_envelope_path(material.capsule_path).exists(),
    )


__all__ = [
    "ProfilePassphraseRotationError",
    "ProfilePassphraseRotationOutcome",
    "rotate_profile_passphrase",
]
