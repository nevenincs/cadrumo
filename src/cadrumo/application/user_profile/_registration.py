"""Credential-first profile registration: a label and a passphrase, nothing else.

This is the door behind the terminal's first screen. It exists because
profile creation used to be split across two surfaces that never met: the
operator's chosen label arrived as a shell argument to
``config profile create``, while the passphrase that actually protects the
bucket was only ever collected later, by ``config login``, through a
separate command. Nothing in the setup flow collected a credential at all.

The contract here is deliberately minimal: a profile exists the moment a
label and a passphrase are supplied. No tax id, no régimen, no activity —
those are profile *completeness*, filled in afterwards against a live
record, not preconditions for the record existing. The profile is therefore
born ``SETUP_INCOMPLETE``: real, addressable, and writable, while modelo
work stays refused until the facts that filing depends on are present.

Registration is the sole creation path. It stages the first encrypted record
and then commits the capsule, label projection, and pointer transaction. The
bucket's key-encryption key is derived from the credential the operator chose
rather than from an ambient environment value.

See Also:
    :func:`~cadrumo.application.user_profile.login_profile`
        The returning-operator counterpart; this module is the first-time
        path that has no key material to unwrap yet.
"""

from __future__ import annotations

from base64 import b64encode
from datetime import UTC, datetime
from secrets import token_bytes
from typing import TYPE_CHECKING, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ...core import NIST_PASSPHRASE_MIN_LENGTH, PassphraseStrength, assess_passphrase_strength
from ...core.errors import CadrumoError
from ...core.identity import BucketId, ProfileId
from ...domain.user_profile import ProfileSetupState, UserProfileRecord, new_profile_id
from ..filing import try_record_filing_retention_snapshot
from ..profile_custody import create_profile_custody_registration_material
from ._capsule_record import ProfileRecordSession
from ._custody_service import ProfileCustodyDisplacedSessionRetirementError
from ._custody_transactions import ProfileCustodyTransactionConflictError
from ._lifecycle import ProfileCapsuleLifecycle
from ._validation import reject_invalid_profile_facts

if TYPE_CHECKING:
    from ...domain.user_profile import UserProfileFact


PASSPHRASE_MINIMUM_LENGTH: Final[int] = NIST_PASSPHRASE_MIN_LENGTH
"""The enforced verifier minimum, re-exposed for operator-facing surfaces.

A credential screen needs this to give live feedback while the operator
types. Re-exposing it on the application facade keeps the inbound adapter
off :mod:`cadrumo.core` internals for a value it only ever reads through a
registration flow; the policy itself is owned by
:data:`~cadrumo.core.NIST_PASSPHRASE_MIN_LENGTH`.
"""


class ProfileRegistrationError(CadrumoError):
    """Raised when a registration request cannot be honoured as supplied."""


class PassphraseAssessment(BaseModel):
    """Advisory verdict on a candidate passphrase, for live field feedback.

    Carries no secret: only the derived length and band, so a surface can
    render guidance without holding the candidate anywhere but the widget.
    """

    model_config = ConfigDict(frozen=True)

    length: int = Field(ge=0)
    minimum_length: int = Field(ge=1)
    strength: PassphraseStrength

    @property
    def acceptable(self) -> bool:
        """Whether this candidate clears the enforced minimum.

        The only hard gate. Every band above ``TOO_SHORT`` is acceptable —
        a ``WEAK`` passphrase is guidance, not a refusal (NIST SP 800-63B
        §5.1.1.2 advises against composition requirements).
        """
        return self.strength is not PassphraseStrength.TOO_SHORT


class ProfileRegistrationOutcome(BaseModel):
    """Typed result of one successful registration.

    Carries no key material. The unlocked bucket session is bound to the
    process by the create span, exactly as :func:`login_profile` leaves it.
    """

    model_config = ConfigDict(frozen=True)

    profile_id: ProfileId
    bucket_id: BucketId
    label: str
    setup_state: ProfileSetupState


def assess_passphrase(candidate: str) -> PassphraseAssessment:
    """Band ``candidate`` against the enforced minimum for live UI feedback.

    Pure and side-effect free: safe to call on every keystroke. Nothing is
    persisted, logged, or hashed, and the returned model deliberately holds
    the length rather than the candidate.
    """
    return PassphraseAssessment(
        length=len(candidate),
        minimum_length=PASSPHRASE_MINIMUM_LENGTH,
        strength=assess_passphrase_strength(candidate, minimum_length=PASSPHRASE_MINIMUM_LENGTH),
    )


def register_profile_with_credentials(
    *,
    label: str,
    passphrase: str,
    facts: tuple[UserProfileFact, ...] = (),
) -> ProfileRegistrationOutcome:
    """Create a profile from a label and a passphrase, and unlock it.

    The profile is born :attr:`ProfileSetupState.INCOMPLETE`: it is a
    real, writable record from this moment, and the operator completes it
    afterwards against a live profile rather than through a gated wizard.

    Args:
        label: Operator-chosen display name. Must be non-blank and must not
            collide with an existing profile's label.
        passphrase: The credential protecting the bucket. Must clear the
            NIST verifier minimum; never logged, never echoed, and held only
            for the duration of the create span.
        facts: Optional initial facts. Empty by default — the whole point of
            this door is that a profile needs no tax data to exist.

    Returns:
        A :class:`ProfileRegistrationOutcome` for the newly-live profile.

    Raises:
        ProfileRegistrationError: When the label is blank or the passphrase
            is shorter than :data:`PASSPHRASE_MINIMUM_LENGTH`.
        ProfileRegistrationError: When the label is already bound.
        ProfileSchemaValidationError: When an initial fact names an unknown or
            engine-derived path, or carries a value its field will not take.
            Missing filing fields are not refused: the profile is born
            incomplete on purpose.
    """
    resolved_label = label.strip()
    if not resolved_label:
        raise ProfileRegistrationError(
            translated_message="application.user_profile.errors.registration_label_blank",
        )

    assessment = assess_passphrase(passphrase)
    if not assessment.acceptable:
        # Refuse here rather than letting the provider raise mid-span: a
        # failure after the bucket directory exists would leave a partially
        # created profile for the operator to clean up by hand.
        raise ProfileRegistrationError(
            translated_message="application.user_profile.errors.registration_passphrase_too_short",
            context={"minimum_length": str(assessment.minimum_length)},
        )

    identity = UUID(new_profile_id())
    dek = token_bytes(32)
    custody_material = create_profile_custody_registration_material(
        profile_id=identity,
        password=passphrase,
        dek=dek,
        dek_epoch=b64encode(token_bytes(16)).decode("ascii"),
        salt=token_bytes(16),
    )
    envelope = custody_material.envelope
    sentinel = custody_material.sentinel
    session = ProfileRecordSession.from_envelope(envelope=envelope, dek=dek)
    # A profile is born incomplete, so missing filing fields are legitimate
    # here -- but an unknown path, an engine-derived path, or a mis-shaped
    # value is not, and refusing them only on later edits would let the create
    # door plant exactly what every edit afterwards is forbidden to write.
    reject_invalid_profile_facts(str(identity), facts, require_complete=False)
    try:
        try:
            ProfileCapsuleLifecycle().create(
                label=resolved_label,
                profile_id=identity,
                password_envelope=envelope,
                sentinel=sentinel,
                data_files={},
                initial_record=UserProfileRecord(
                    profile_id=str(identity),
                    facts=facts,
                    setup_state=ProfileSetupState.INCOMPLETE,
                ),
                record_session=session,
            )
        except ProfileCustodyDisplacedSessionRetirementError as exc:
            # Creating a profile displaces whichever one the pointer named, and
            # the create transaction voids that profile's stored session before
            # it moves the pointer. When that removal cannot complete the
            # transaction refuses with the pointer untouched -- correct, but
            # indistinguishable from a label collision unless it is caught
            # ahead of one, and telling the operator their brand-new label is
            # taken would send them to rename a profile that is not the problem.
            raise ProfileRegistrationError(
                translated_message="application.user_profile.errors.registration_displaced_session_not_retired",
            ) from exc
        except ProfileCustodyTransactionConflictError as exc:
            raise ProfileRegistrationError(
                translated_message="application.user_profile.errors.profile_already_exists",
                context={"profile": resolved_label},
            ) from exc
    finally:
        session.close()

    # Record that this profile has filed NOTHING, rather than leaving the fact
    # absent. The two states are not the same: an empty recorded snapshot says
    # the filing owner was asked and answered, while an absent one says nobody
    # asked -- and the retention assessment refuses on absence, so without this
    # a brand-new profile and one whose snapshot write failed are
    # indistinguishable and both block deletion for the same opaque reason.
    #
    # Best-effort by the same asymmetry that governs the filing-time write: a
    # registration REFUSED because a deletion-support record could not be
    # written is worse than a profile whose snapshot is missing, which merely
    # fails closed later.
    try_record_filing_retention_snapshot(
        bucket_id=str(identity),
        records=(),
        observed_at=datetime.now(UTC),
    )

    return ProfileRegistrationOutcome(
        profile_id=str(identity),
        bucket_id=str(identity),
        label=resolved_label,
        setup_state=ProfileSetupState.INCOMPLETE,
    )


__all__ = [
    "PASSPHRASE_MINIMUM_LENGTH",
    "PassphraseAssessment",
    "ProfileRegistrationError",
    "ProfileRegistrationOutcome",
    "assess_passphrase",
    "register_profile_with_credentials",
]
