"""Shared profile-fact write door.

The interactive wizard, the ``config profile`` manager screens and the
capability and descendiente verbs all publish exact profile-fact
replacements through one shared writer, and each names itself with one
closed :class:`ProfileFactWriteDoor` member.  The door is a payload
descriptor, never an event type: every write emits exactly one
:class:`~cadrumo.domain.buckets.BucketEventType.PROFILE_VALUES_UPDATED`
bucket event, and the surface identity travels beside the change in the
event payload.
"""

from __future__ import annotations

from enum import StrEnum

from ...domain.buckets import BucketEventType
from ...domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord


class ProfileFactWriteDoor(StrEnum):
    """Which operator surface published a profile-fact change.

    The door is a payload descriptor, never an event type.  A profile-fact
    write emits exactly one bucket event, that event's id becomes the record
    row's lineage witness, and the event names the DATA CHANGE:
    :attr:`~cadrumo.domain.buckets.BucketEventType.PROFILE_VALUES_UPDATED`.
    Which operator surface collected the answers is a separate axis, so it
    travels beside the change rather than displacing its identity — a history
    query asking "when did these values last change" reads the event type,
    and one asking "which surface changed them" reads this key.

    Encoding the door in the event type instead is what broke the edit path:
    every wizard write stamped a surface-shaped string that the closed
    :class:`~cadrumo.domain.buckets.BucketEventType` does not contain, and the
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
    CHECKPOINT = "wizard.checkpoint"
    DESCENDANTS = "wizard.descendants"
    MANAGER_FIELD = "manager.field"
    MANAGER_AUTH = "manager.auth"
    MANAGER_ROW = "manager.row"
    CLI_CAPACIDAD = "cli.capacidad"
    CLI_DESCENDIENTE = "cli.descendiente"


def apply_profile_fact_changes(
    *,
    profile_id: str,
    changes: tuple[UserProfileFact, ...],
    door: ProfileFactWriteDoor,
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
    :func:`~cadrumo.application.user_profile.reject_invalid_profile_facts`
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
    from . import ProfileRecordRepository, reject_invalid_profile_facts

    repository = ProfileRecordRepository.for_current_session(profile_id)
    current = repository.load(profile_id)
    changed_paths = {fact.path for fact in changes}
    next_facts = (*tuple(fact for fact in current.facts if fact.path not in changed_paths), *changes)
    reject_invalid_profile_facts(
        profile_id,
        next_facts,
        require_complete=current.setup_state is not ProfileSetupState.INCOMPLETE,
    )
    return repository.apply_fact_changes(
        profile_id,
        facts=next_facts,
        expected_revision=current.record_revision,
        expected_content_digest=current.content_digest,
        event_type=BucketEventType.PROFILE_VALUES_UPDATED,
        event_payload={"changed_fact_count": str(len(changes)), "door": door.value},
    )


def apply_manager_profile_field_mutation(
    *,
    profile_id: str,
    path: str,
    value: str,
) -> UserProfileRecord:
    """Apply the manager's one-field trim-or-clear policy through the sole write door."""
    return apply_profile_fact_changes(
        profile_id=profile_id,
        changes=(UserProfileFact(path=path, value=value.strip() or None),),
        door=ProfileFactWriteDoor.MANAGER_FIELD,
    )


__all__ = [
    "ProfileFactWriteDoor",
    "apply_manager_profile_field_mutation",
    "apply_profile_fact_changes",
]
