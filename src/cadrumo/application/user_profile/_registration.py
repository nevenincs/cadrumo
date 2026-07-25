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

No parallel write path is introduced. Registration composes the same
primitives every other create route uses —
:func:`~cadrumo.application.user_profile.profile_create_storage_span` around
:func:`~cadrumo.application.user_profile.register_active_profile`, which
delegates the cross-store unit of work to
:meth:`~cadrumo.application.user_profile.ProfileRepository.create`. The one
thing this module adds is *binding the operator's new passphrase to that
span*, so the bucket's key-encryption key is derived from the credential
the operator just chose rather than from an ambient environment value.

See Also:
    :func:`~cadrumo.application.user_profile.login_profile`
        The returning-operator counterpart; this module is the first-time
        path that has no key material to unwrap yet.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, Field

from ...adapters.persistence.storage.master_key import NIST_PASSPHRASE_MIN_LENGTH
from ...core import PassphraseStrength, assess_passphrase_strength
from ...core.errors import CadrumoError
from ...domain.user_profile import UserProfileStatus, new_profile_id
from ..workflow import workflow_state_repository
from ._orchestration import (
    profile_create_storage_span,
    refuse_duplicate_label,
    register_active_profile,
)

if TYPE_CHECKING:
    from ...domain.user_profile import UserProfileFact


PASSPHRASE_MINIMUM_LENGTH: Final[int] = NIST_PASSPHRASE_MIN_LENGTH
"""The enforced verifier minimum, re-exposed for operator-facing surfaces.

A credential screen needs this to give live feedback while the operator
types. Re-exporting it here keeps the inbound adapter on the application
facade instead of importing from the persistence adapter directly, while
the value itself stays owned by the master-key provider that enforces it.
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

    profile_id: str
    bucket_id: str
    label: str
    status: UserProfileStatus


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

    The profile is born :attr:`UserProfileStatus.SETUP_INCOMPLETE`: it is a
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
        ProfileAlreadyRegisteredError: When the label is already taken.
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

    refuse_duplicate_label(resolved_label)

    profile_id = new_profile_id()
    # Bind the operator's passphrase to the span's own master-key
    # resolution. The span resolves the provider itself (and mints the key
    # material on first use), so the callback must be threaded INTO it —
    # building a provider out here would be discarded and the bucket would
    # silently key off the ambient configured secret instead.
    with profile_create_storage_span(
        profile_id,
        passphrase_callback=lambda: passphrase,
    ) as routing_profile_id:
        workflow_state_repository().update(
            lambda state: register_active_profile(
                state,
                profile_id=profile_id,
                display_name=resolved_label,
                facts=facts,
                routing_profile_id=routing_profile_id,
                status=UserProfileStatus.SETUP_INCOMPLETE,
            ),
        )

    # The create span closes its session on exit, so a bare registration
    # would leave the operator holding a profile they are not logged in to —
    # and the surface that called this opens onto that profile immediately.
    # Delegating to the canonical login door (rather than opening a session
    # here) keeps one authentication path, and with it the throttle, the
    # pointer transaction, and the persisted-session semantics.
    from ._login_session import login_profile

    login_profile(name=resolved_label, passphrase_callback=lambda: passphrase)

    return ProfileRegistrationOutcome(
        profile_id=profile_id,
        bucket_id=profile_id,
        label=resolved_label,
        status=UserProfileStatus.SETUP_INCOMPLETE,
    )


__all__ = [
    "PASSPHRASE_MINIMUM_LENGTH",
    "PassphraseAssessment",
    "ProfileRegistrationError",
    "ProfileRegistrationOutcome",
    "assess_passphrase",
    "register_profile_with_credentials",
]
