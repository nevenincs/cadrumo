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
from contextlib import ExitStack
from datetime import UTC, datetime
from secrets import token_bytes
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from ...core import assess_profile_password
from ...core.errors import CadrumoError
from ...core.identity import BucketId, ProfileId
from ...domain.user_profile import ProfileSetupState, UserProfileRecord, new_profile_id
from ..evidence import try_record_legal_hold_snapshot
from ..filing import try_record_filing_retention_snapshot
from ._capsule_record import ProfileRecordSession
from ._custody_ports import create_profile_custody_registration_material
from ._custody_service import ProfileCustodyDisplacedSessionRetirementError
from ._custody_transactions import (
    ProfileCustodyDuplicateLabelError,
    ProfileCustodyTransactionConflictError,
)
from ._lifecycle import ProfileCapsuleLifecycle
from ._prospective_password import ProspectiveProfilePasswordRefusal, prospective_profile_password_refusal
from ._recovery_custody import enroll_profile_recovery
from ._validation import reject_invalid_profile_facts

if TYPE_CHECKING:
    from collections.abc import Callable

    from ...domain.user_profile import UserProfileFact
    from ._recovery_custody import ProfileRecoveryEnrollment


class ProfileRegistrationError(CadrumoError):
    """Raised when a registration request cannot be honoured as supplied."""

    def __init__(
        self,
        message: str | None = None,
        *,
        context: dict[str, object] | None = None,
        translated_message: str | None = None,
        password_refusal: ProspectiveProfilePasswordRefusal | None = None,
    ) -> None:
        """Retain a typed prospective refusal without retaining the password."""
        super().__init__(message, context=context, translated_message=translated_message)
        self.password_refusal = password_refusal


class ProfileRegistrationConflictError(ProfileRegistrationError):
    """Raised when registration lost a race it can win by simply repeating.

    A custody transaction refuses when the witness it captured no longer
    matches live state, which a re-read resolves -- so the identical call may
    succeed. That is a different answer to the operator than "this label is
    taken", which no retry can change, and the two arrive here as the same
    exception family because the permanent case is a SUBCLASS of the transient
    one.

    Split as a subclass for the same reason that one was: every existing
    handler catching :class:`ProfileRegistrationError` keeps catching this,
    and only the published code and its retryability differ.
    """


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
    recovery_enrolled: bool
    """Whether this profile was published carrying a recovery wrapper.

    Not a courtesy field. Recovery can only be installed while the capsule is
    being published, so "not enrolled" is permanent for this profile, and a
    surface that does not tell the operator has silently spent their only
    chance. It carries no secret -- the 24 words never reach this model -- so
    it is safe on every envelope the flag is meant to be reported on.
    """


def register_profile_with_credentials(
    *,
    label: str,
    passphrase: str,
    facts: tuple[UserProfileFact, ...] = (),
    recovery_handover: Callable[[ProfileRecoveryEnrollment], None] | None = None,
) -> ProfileRegistrationOutcome:
    """Create a profile from a label and a passphrase, and unlock it.

    The profile is born :attr:`ProfileSetupState.INCOMPLETE`: it is a
    real, writable record from this moment, and the operator completes it
    afterwards against a live profile rather than through a gated wizard.

    Recovery enrollment happens HERE or never. A committed capsule has no
    in-place installation path for a second wrapper, so the recovery envelope
    has to be minted before the create transaction and published with the
    capsule; the mint is placed ahead of the transaction for that reason and
    because a failure there must leave no profile behind rather than half of
    one. It is deliberately not best-effort the way the trailing filing and
    legal-hold snapshots are: those record a fact ABOUT a published capsule,
    while this changes what gets published.

    Args:
        label: Operator-chosen display name. Must be non-blank and must not
            collide with an existing profile's label.
        passphrase: The credential protecting the bucket. Must satisfy the
            canonical profile-password contract; never logged, never echoed,
            and held only for the duration of the create span.
        facts: Optional initial facts. Empty by default — the whole point of
            this door is that a profile needs no tax data to exist.
        recovery_handover: The channel the 24 words reach the operator
            through, and the only one — they never touch the returned model,
            an envelope, or a log. Supplying it enrolls recovery; omitting it
            mints no wrapper AT ALL, and :attr:`recovery_enrolled` on the
            result says which happened, so no surface can leave an operator
            unaware that their one chance has passed.

            Minting without a channel would be the worse failure rather than
            the safer one: the words would be wiped unshown, leaving a second
            wrapped copy of the DEK in the capsule that nobody can ever open —
            attack surface with no recovery value. The portable artifact does
            not rescue that case either, because the artifact is unwrapped BY
            the mnemonic; file and phrase are one door, not two.

            The callback is invoked once, BEFORE the capsule is published,
            and the key is wiped by the time this returns — so a caller that
            needs the operator to copy the words down must do that INSIDE the
            call rather than retaining the enrollment past it. Raising from
            the callback is the sanctioned way to report a channel that could
            not deliver: it aborts the creation, so no profile is left holding
            a wrapper nobody received. A caller with no interactive terminal
            should pass no handover at all rather than one that will refuse.

    Returns:
        A :class:`ProfileRegistrationOutcome` for the newly-live profile.

    Raises:
        ProfileRegistrationError: When the label is blank or the passphrase
            does not satisfy the canonical profile-password contract.
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

    password_refusal = prospective_profile_password_refusal(assess_profile_password(passphrase))
    if password_refusal is not None:
        # Refuse here rather than letting the provider raise mid-span: a
        # failure after the bucket directory exists would leave a partially
        # created profile for the operator to clean up by hand.
        raise ProfileRegistrationError(
            translated_message=password_refusal.translated_message,
            context=password_refusal.context,
            password_refusal=password_refusal,
        )

    identity = UUID(new_profile_id())
    dek = token_bytes(32)
    dek_epoch = b64encode(token_bytes(16)).decode("ascii")
    custody_material = create_profile_custody_registration_material(
        profile_id=identity,
        password=passphrase,
        dek=dek,
        dek_epoch=dek_epoch,
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
    with ExitStack() as recovery_scope:
        # Minted ahead of the transaction, and entered on the scope so the
        # 24 words are zeroised on every exit -- the successful one, the
        # refused one, and the one where the handover itself raises.
        enrollment: ProfileRecoveryEnrollment | None = None
        if recovery_handover is not None:
            enrollment = enroll_profile_recovery(profile_id=identity, dek=dek, dek_epoch=dek_epoch)
            recovery_scope.enter_context(enrollment.recovery_key)
            # Delivered BEFORE the capsule is published, and the ordering is
            # the whole safety property. A channel can fail at the moment of
            # writing rather than when it is chosen -- a detached process is
            # handed a fresh console, so the device opens and the write lands
            # on a surface nobody will ever see. Publishing first and
            # discovering that second would leave a live profile carrying a
            # recovery wrapper whose only key went nowhere: enrolled, reported
            # enrolled, and permanently unopenable, with no second chance
            # because a committed capsule cannot be enrolled afterwards.
            #
            # Delivering first inverts which way a failure falls. A refused
            # channel now aborts creation outright, so there is no profile and
            # no orphaned wrapper. The residual cost is the mirror case -- the
            # operator copies down 24 words and the create transaction then
            # refuses -- which leaves them holding a phrase for a profile that
            # does not exist. That is discardable and it is visible, which the
            # undeliverable-wrapper state is neither.
            recovery_handover(enrollment)

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
                    recovery_envelope=None if enrollment is None else enrollment.envelope,
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
            except ProfileCustodyDuplicateLabelError as exc:
                raise ProfileRegistrationError(
                    translated_message="application.user_profile.errors.profile_already_exists",
                    context={"profile": resolved_label},
                ) from exc
            except ProfileCustodyTransactionConflictError as exc:
                # Caught AFTER its duplicate-label subclass: this is the
                # stale-witness conflict, which a repeat of the identical call
                # can win. Reporting it as "that label is taken" tells an agent
                # operator to pick a different name for a profile that does not
                # exist.
                raise ProfileRegistrationConflictError(
                    translated_message="errors.refused.refused_storage_profile_custody",
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

        # Record that this profile has zero known open legal cases, for the same
        # reason and the same best-effort asymmetry as the filing snapshot above.
        # A profile at this instant has no filings and no captured AEAT
        # expedientes -- there is nothing yet for an outside legal hold to be a
        # hold ON, so "zero known cases" is a fact about a brand-new profile
        # rather than an assumption of clearance. It is NOT a standing answer for
        # this profile's later life: a genuinely external hold arising afterwards
        # is unknowable to this system until something (a future expedientes
        # capture, an operator affirmation) records it, and until it does the
        # deletion preflight keeps reading this recorded fact.
        try_record_legal_hold_snapshot(
            bucket_id=str(identity),
            open_case_ids=(),
            observed_at=datetime.now(UTC),
        )

        return ProfileRegistrationOutcome(
            profile_id=str(identity),
            bucket_id=str(identity),
            label=resolved_label,
            setup_state=ProfileSetupState.INCOMPLETE,
            recovery_enrolled=enrollment is not None,
        )


__all__ = [
    "ProfileRegistrationError",
    "ProfileRegistrationOutcome",
    "register_profile_with_credentials",
]
