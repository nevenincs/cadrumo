"""Credential-first profile registration.

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
    :func:`~cadrumo.application.user_profile.login_session.login_profile`
        The returning-operator counterpart; this module is the first-time
        path that has no key material to unwrap yet.
"""

from __future__ import annotations

from base64 import b64encode
from secrets import token_bytes
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel

from ...core.credentials import assess_profile_password
from ...core.errors.hierarchy import CadrumoError
from ...core.identity.bucket import BucketId
from ...core.identity.profile import ProfileId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time.clock import now as _utc_now
from ...domain.user_profile.values import (
    ProfileSetupState,
    create_user_profile_record,
    new_profile_id,
)
from ..evidence.profile_legal_hold import try_record_legal_hold_snapshot
from ..filing.retention import try_record_filing_retention_snapshot
from .capsule_record import ProfileRecordSession
from .custody_ports import create_profile_custody_registration_material
from .custody_service import ProfileCustodyDisplacedSessionRetirementError
from .custody_transactions import (
    ProfileCustodyDuplicateLabelError,
    ProfileCustodyTransactionConflictError,
)
from .lifecycle import ProfileCapsuleLifecycle
from .login_session import publish_created_profile_session
from .prospective_password import ProspectiveProfilePasswordRefusal, prospective_profile_password_refusal
from .validation import reject_invalid_profile_facts

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority_artifact import ProfileCreateContext, ProfileDecodeContext
    from ...domain.user_profile.values import UserProfileFact


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
        self._password_refusal = password_refusal

    @property
    def password_refusal(self) -> ProspectiveProfilePasswordRefusal | None:
        """Retain the typed refusal for trusted in-process consumers only."""
        return self._password_refusal


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

    Carries no key material. The created profile is left UNLOCKED: the
    create span publishes its live bucket session and record authority
    process-wide through
    :func:`~cadrumo.application.user_profile.login_session.publish_created_profile_session`,
    exactly as :func:`login_profile` leaves them, so the operator is not asked
    for the passphrase they just chose. No acceleration receipt is minted, so
    the next process authenticates normally.
    """

    model_config = STRICT_FROZEN_CONFIG

    profile_id: ProfileId
    bucket_id: BucketId
    label: str
    setup_state: ProfileSetupState


def _refuse_a_label_already_taken(label: str) -> None:
    """Refuse a label that is visibly taken before deriving any key.

    Deriving the password key is the slow step of creation, and the custody
    transaction only meets the label collision after it -- so repeating a
    create, the ordinary re-run of a setup script, waited out a full key
    derivation just to be told the name is taken. This check is advisory: it
    reads the same committed label projections the transaction does, with the
    same case-insensitive comparison, and the transaction's own check under
    the root lock stays the authority for a label claimed in between.
    """
    from ..workflow.errors import ProfileLabelAmbiguousError
    from ..workflow.profile_bucket_scan import read_profile_bucket

    try:
        taken = read_profile_bucket(label) is not None
    except ProfileLabelAmbiguousError:
        taken = True
    if taken:
        raise ProfileRegistrationError(
            translated_message="application.user_profile.errors.profile_already_exists",
            context={"profile": label},
        )


def register_profile_with_credentials(
    *,
    label: str,
    passphrase: str,
    facts: tuple[UserProfileFact, ...] = (),
    profile_create_context: ProfileCreateContext,
    profile_decode_context: ProfileDecodeContext,
) -> ProfileRegistrationOutcome:
    """Create a profile from a label and a passphrase, and unlock it.

    The profile is born :attr:`ProfileSetupState.INCOMPLETE`: it is a
    real, writable record from this moment, and the operator completes it
    afterwards against a live profile rather than through a gated wizard.

    Recovery is not part of creation. A profile is born with its passphrase
    as its only door; the operator may enrol a recovery code afterwards
    through :func:`~cadrumo.application.user_profile.recovery_custody.enroll_profile_recovery`,
    and every surface that creates a profile offers that step as an explicit,
    skippable follow-up rather than a precondition.

    Args:
        label: Operator-chosen display name. Must be non-blank and must not
            collide with an existing profile's label.
        passphrase: The credential protecting the bucket. Must satisfy the
            canonical profile-password contract; never logged, never echoed,
            and held only for the duration of the create span.
        facts: Optional initial facts. Empty by default — the whole point of
            this door is that a profile needs no tax data to exist.
        profile_create_context: Schema context pinned for the new record.
        profile_decode_context: Schema context pinned for the authenticated
            record session. It must share the authority generation with
            ``profile_create_context``.

    The created profile is left unlocked for this process: its live bucket
    session and record authority are published exactly as a login publishes
    them. The operator has just chosen and proven this passphrase, so asking
    for it again before the profile can be used answers a question they have
    already answered.

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
    if (
        profile_create_context.schema != profile_decode_context.schema
        or profile_create_context.generation != profile_decode_context.generation
    ):
        raise ProfileRegistrationError(
            "profile registration requires create and decode contexts from one authority generation",
        )
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
            context=dict(password_refusal.context),
            password_refusal=password_refusal,
        )
    _refuse_a_label_already_taken(resolved_label)

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
    session = ProfileRecordSession.from_envelope(
        envelope=envelope,
        dek=dek,
        profile_decode_context=profile_decode_context,
    )
    # A profile is born incomplete, so missing filing fields are legitimate
    # here -- but an unknown path, an engine-derived path, or a mis-shaped
    # value is not, and refusing them only on later edits would let the create
    # door plant exactly what every edit afterwards is forbidden to write.
    reject_invalid_profile_facts(
        str(identity),
        facts,
        require_complete=False,
        schema=profile_create_context.schema,
    )
    try:
        try:
            ProfileCapsuleLifecycle().create(
                label=resolved_label,
                profile_id=identity,
                password_envelope=envelope,
                sentinel=sentinel,
                data_files={},
                initial_record=create_user_profile_record(
                    context=profile_create_context,
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

    # Publish before the best-effort snapshots below, not after: they write
    # through the profile's encrypted store, so they need the session this
    # call binds. Registration is also the moment the operator's credential
    # has just been proven, and leaving the profile locked until they retype
    # it is the defect this closes.
    publish_created_profile_session(
        bucket_id=str(identity),
        dek=dek,
        profile_decode_context=profile_decode_context,
    )

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
        observed_at=_utc_now(),
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
        observed_at=_utc_now(),
    )

    return ProfileRegistrationOutcome(
        profile_id=str(identity),
        bucket_id=str(identity),
        label=resolved_label,
        setup_state=ProfileSetupState.INCOMPLETE,
    )


__all__ = [
    "ProfileRegistrationError",
    "ProfileRegistrationOutcome",
    "register_profile_with_credentials",
]
