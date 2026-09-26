"""Shared profile-fact write door.

The interactive wizard, the ``config profile`` manager screens and the
capability and descendiente verbs all publish exact profile-fact
replacements through one shared writer, and each names itself with one
closed :class:`ProfileFactWriteDoor` member.  The door is a payload
descriptor, never an event type: every write emits exactly one
:class:`~cadrumo.domain.buckets.event.BucketEventType.PROFILE_VALUES_UPDATED`
bucket event, and the surface identity travels beside the change in the
event payload.
"""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from ...domain.buckets.event import BucketEventType
from ...domain.user_profile.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from ...domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext


class ProfileFactWriteDoor(StrEnum):
    """Which operator surface published a profile-fact change.

    The door is a payload descriptor, never an event type.  A profile-fact
    write emits exactly one bucket event, that event's id becomes the record
    row's lineage witness, and the event names the DATA CHANGE:
    :attr:`~cadrumo.domain.buckets.event.BucketEventType.PROFILE_VALUES_UPDATED`.
    Which operator surface collected the answers is a separate axis, so it
    travels beside the change rather than displacing its identity — a history
    query asking "when did these values last change" reads the event type,
    and one asking "which surface changed them" reads this key.

    Encoding the door in the event type instead is what broke the edit path:
    every wizard write stamped a surface-shaped string that the closed
    :class:`~cadrumo.domain.buckets.event.BucketEventType` does not contain, and the
    capsule writer refused the whole command rather than recording anything.

    The taxonomy spans every surface that writes profile facts, not only the
    wizard: the command-line manager screens and the ``config profile`` verbs
    publish through this same writer, so their identities belong in the same
    closed set rather than in a second one beside it.  ``CLI_DESCENDIENTE`` is
    deliberately distinct from :attr:`DESCENDANTS` -- the interactive wizard's
    repeating group and the non-interactive descendiente verbs are two surfaces
    an operator can tell apart, and a history query asking which of them last
    rewrote the set would be unable to answer if they shared one value.
    """

    ANSWERS = "wizard.answers"
    PATCH = "wizard.patch"
    DESCENDANTS = "wizard.descendants"
    MANAGER_FIELD = "manager.field"
    MANAGER_ROW = "manager.row"
    CLI_CAPACIDAD = "cli.capacidad"
    CLI_DESCENDIENTE = "cli.descendiente"
    CLI_PLANTILLA_MEDIA = "cli.plantilla_media"
    MANAGER_PLANTILLA_MEDIA = "manager.plantilla_media"


def _effective(record: UserProfileRecord) -> dict[str, object]:
    """Project a record to its effective fact per path for change comparison."""
    from .projections import record_to_effective_facts as _projector

    return dict(_projector(record))


def apply_profile_fact_changes(
    *,
    profile_id: str,
    changes: tuple[UserProfileFact, ...],
    door: ProfileFactWriteDoor,
    expected_record: UserProfileRecord | None = None,
    profile_decode_context: ProfileDecodeContext,
) -> UserProfileRecord:
    """Publish an exact fact replacement through the active session.

    The writer never touches an aggregate or a generic profile row.  It loads
    the authenticated current record, replaces only the paths the validated
    command names, and asks the record repository to CAS-publish the complete
    resulting sequence with one command event.  A ``value=None`` change is
    retained deliberately: it is the explicit current-record representation
    of clearing an answer.

    This is not the only door onto profile facts -- registration opens the
    initial record and the cotejo censal adopts certificate values -- so what
    is shared is not the door but the JUDGE: every one of them refuses through
    :func:`~cadrumo.application.user_profile.validation.reject_invalid_profile_facts`
    before publishing.  An engine-derived path, an unknown path and a value of
    the wrong shape are refused at whichever write reaches them rather than at
    the surface that happened to collect the answer: a check living only in
    the manager's edit dialog binds nobody who writes through the wizard, the
    CLI or a later surface, and a stored value at a derived path silently
    displaces the computation that owns it.

    Every door publishes the same lifecycle event -- the write IS a profile
    value change, whichever surface collected it -- and distinguishes itself
    through ``door`` in the event payload.  See :class:`ProfileFactWriteDoor`
    for why the surface identity cannot live in the event type.

    Returns:
        The published :class:`UserProfileRecord` carrying the replacement.
    """
    from .profile_record_repository import ProfileRecordRepository
    from .validation import reject_invalid_profile_facts

    repository = ProfileRecordRepository.for_current_session(
        profile_id,
        profile_decode_context=profile_decode_context,
    )
    current = expected_record if expected_record is not None else repository.load(profile_id)
    profile_context = repository.session.profile_decode_context
    changed_paths = {fact.path for fact in changes}
    next_facts = (*tuple(fact for fact in current.facts if fact.path not in changed_paths), *changes)
    reject_invalid_profile_facts(
        profile_id,
        next_facts,
        require_complete=current.setup_state is not ProfileSetupState.INCOMPLETE,
        schema=profile_context.schema,
    )
    # A write that changes nothing is not a write. Publishing it anyway bumped
    # the revision and appended a profile.values.updated event, so the evidence
    # chain recorded changes that never happened -- and a caller submitting a
    # value identical to the stored one was told it had updated the record.
    # Effective facts are the comparison, not raw values, so an explicit clear
    # (value=None) still reads as a real change against a set path.
    if _effective(current) == _effective(current.model_copy(update={"facts": next_facts})):
        return current
    published = repository.apply_fact_changes(
        profile_id,
        facts=next_facts,
        expected_revision=current.record_revision,
        expected_content_digest=current.content_digest,
        event_type=BucketEventType.PROFILE_VALUES_UPDATED,
        event_payload={"changed_fact_count": str(len(changes)), "door": door.value},
    )
    if PROFILE_OUTPUT_LANGUAGE_PATH in changed_paths:
        from .language_resolver import refresh_active_profile_output_language

        _mirror_output_language_hint(published)
        refresh_active_profile_output_language()
    return published


def _mirror_output_language_hint(published: UserProfileRecord) -> None:
    """Carry the new preference into the bucket's non-secret language hint.

    Sited at the sole fact-write door because that is the only place the
    preference can change. The hint is what a pre-login surface reads when no
    bucket session is bound; nothing wrote it, so that fallback always found
    nothing and the operator's chosen language could not survive a lock.
    """
    from ...core.bucket_pointer import resolve_active_bucket_id
    from ...core.config_support import coerce_output_language_setting
    from .language_resolver import mirror_profile_output_language_hint
    from .projections import record_to_path_values

    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        return
    stored = record_to_path_values(published).get(PROFILE_OUTPUT_LANGUAGE_PATH)
    mirror_profile_output_language_hint(
        bucket_id,
        None if stored is None else coerce_output_language_setting(stored),
    )


def apply_manager_profile_field_mutation(
    *,
    profile_id: str,
    path: str,
    value: str,
    expected_revision: int | None = None,
    expected_content_digest: str | None = None,
    profile_decode_context: ProfileDecodeContext,
) -> UserProfileRecord:
    """Apply the manager's one-field trim-or-clear policy through the sole write door."""
    from .profile_record_repository import ProfileRecordRepository

    current = ProfileRecordRepository.for_current_session(
        profile_id,
        profile_decode_context=profile_decode_context,
    ).load(profile_id)
    if (
        expected_revision is not None
        and expected_content_digest is not None
        and (current.record_revision != expected_revision or current.content_digest != expected_content_digest)
    ):
        from .capsule_record import ProfileRecordConflictError

        raise ProfileRecordConflictError("profile manager edit baseline is stale")
    return apply_profile_fact_changes(
        profile_id=profile_id,
        changes=(UserProfileFact(path=path, value=value.strip() or None),),
        door=ProfileFactWriteDoor.MANAGER_FIELD,
        expected_record=current,
        profile_decode_context=profile_decode_context,
    )


__all__ = [
    "ProfileFactWriteDoor",
    "apply_manager_profile_field_mutation",
    "apply_profile_fact_changes",
]
