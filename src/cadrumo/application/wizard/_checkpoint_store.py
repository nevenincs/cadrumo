"""Create-mode checkpoint port: the profile facts ARE the checkpoint.

The substrate defines the checkpoint PORT
(:class:`~cadrumo.application.flows.CheckpointStore`); this module supplies
the profile domain's implementation. There is no bespoke checkpoint object,
no stored cursor, and no answer-map artefact: the in-progress answers persist
as effective-dated :class:`~cadrumo.domain.user_profile.UserProfileFact` rows
through the profile lifecycle authority, exactly like every committed answer,
and the record's ``ProfileSetupState.INCOMPLETE`` setup state is the
resume-eligibility flag.
flag.

Lifecycle of a create-mode checkpoint:

* **save** — projects the current canonical answer map to facts and persists
  them through the lifecycle authority. The first save with a validated
  ``tax-id`` mints the profile early in ``incomplete`` state (so
  ``_refuse_duplicate_tax_id`` fires at genuine minting); later saves upsert
  onto the live record. Sensitive answers ride only this authority into the
  encrypted secure-object store — never a plaintext sink, never a log.
* **load** — offers a resume ONLY while the active profile's setup state is
  ``incomplete``, re-projecting the on-record facts back to a page-keyed
  answer map. ``resume_flow`` recomputes everything derived (cursor, staleness,
  validation) against the *current* definition; a completed or absent profile
  returns ``None`` (no resume).
* **discard** — explicit operator abandonment erases the incomplete profile
  through the existing capsule lifecycle, never a parallel delete path.

Completion (the ``incomplete`` → ``complete`` flip at the flow's final commit)
is the domain-owned completion transition: the setup-state flip ends
resume-eligibility, so there is nothing else to erase. It is driven by the
command through
:meth:`~cadrumo.application.user_profile.ProfileRecordRepository.complete_setup`,
not by this store.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ._descendant_group import DESCENDANTS_COUNT_PAGE_ID
from ._models import WizardFlow

# The descendant fact namespace: indexed rows renta_family.descendiente.{n}.*
# plus the one aggregate the projection still stores.
#
# The Art. 81.2 guardería sum used to belong here too. It is now an
# engine-derived path: nothing writes it, the calculate-time injector recomputes
# it from the per-child figures, and the profile write door refuses a value at
# it. Keeping it in this set made the clearing sweep emit a clear for a path
# that can never be present -- dead work pointed at a retired declaration.
_DESCENDANT_ROW_PREFIX = "renta_family.descendiente."
_DESCENDANT_AGGREGATE_PATHS = frozenset({"renta_family.descendientes_count"})


def _in_descendant_namespace(path: str) -> bool:
    """True when ``path`` is an indexed descendant row or a descendant aggregate."""
    return path.startswith(_DESCENDANT_ROW_PREFIX) or path in _DESCENDANT_AGGREGATE_PATHS


def descendant_clearing_facts(
    record: UserProfileRecord | None,
    answers: Mapping[str, str],
) -> tuple[UserProfileFact, ...]:
    """Return value-cleared facts for descendant rows the projection replaces.

    When the descendant group was reached (its count page carries an
    answer), the projection OWNS the entire ``renta_family.descendiente.*``
    namespace plus the two aggregates: any on-record path the fresh
    projection does not set is stale (a shrunk count, a removed optional
    field) and is cleared with a ``value=None`` fact -- the canonical
    fact-removal mechanism. Without the answer (the group was never part of
    this run) nothing is touched, so a prior descendant fact set survives a
    partial re-persist. This closes the count-shrink desync where
    ``descendant_list_from_facts`` would otherwise scan orphaned indices the
    count no longer covers.

    Args:
        record: The :class:`UserProfileRecord` to scan for stale descendant
            paths, or ``None``.
        answers: The page-keyed canonical answer map for the current run.
    """
    if record is None or DESCENDANTS_COUNT_PAGE_ID not in answers:
        return ()
    from ..user_profile import record_to_path_values
    from ._persistence import descendant_facts_from_answers

    projected = {path for path, _ in descendant_facts_from_answers(answers)}
    existing = record_to_path_values(record)
    return tuple(
        UserProfileFact(path=path, value=None)
        for path in existing
        if _in_descendant_namespace(path) and path not in projected
    )


def checkpoint_facts_from_answers(flow: WizardFlow, answers: Mapping[str, str]) -> tuple[UserProfileFact, ...]:
    """Project a page-keyed canonical answer map into profile facts.

    Only profile-bound questions contribute a fact, keyed by the
    question's ``profile_key`` (the schema fact path). A blank canonical
    token contributes nothing — the persistence layer's drop-blank rule,
    so an unanswered page never writes an empty fact. The answers are
    already engine-validated canonical tokens, so no re-validation runs
    here.

    The descendant repeating group's instance answers
    (``descendientes#<index>.<page>``) are not profile-bound questions;
    they project separately through
    :func:`~cadrumo.application.wizard._persistence.descendant_facts_from_answers`
    into the ``renta_family.descendiente.{n}.*`` fact shape and its
    derived aggregates, appended here so the descendant surface persists
    through the one checkpoint writer alongside every other answer.
    """
    from ._persistence import descendant_facts_from_answers

    facts: list[UserProfileFact] = []
    for section in flow.sections:
        for question in section.questions:
            if question.profile_key is None:
                continue
            value = answers.get(question.id)
            if value:
                facts.append(UserProfileFact(path=question.profile_key, value=value))
    facts.extend(UserProfileFact(path=path, value=value) for path, value in descendant_facts_from_answers(answers))
    return tuple(facts)


def checkpoint_answers_from_record(flow: WizardFlow, record: UserProfileRecord | None) -> dict[str, str]:
    """Re-project a :class:`UserProfileRecord`'s on-record facts into a page-keyed answer map.

    The inverse of :func:`checkpoint_facts_from_answers`: each profile-bound
    question whose ``profile_key`` carries a live fact on the
    :class:`UserProfileRecord` re-appears keyed by page id (a top-level setup
    question's page id equals its question id). The descendant repeating group
    is re-seeded separately through
    :func:`~cadrumo.application.wizard._persistence.descendant_answers_from_record`,
    which emits the ``descendientes-count`` answer plus one
    ``descendientes#<index>.<page>`` answer per populated field, so a resumed
    create re-instantiates the group from its persisted
    ``renta_family.descendiente.*`` facts. This whole map is the seed
    :func:`~cadrumo.application.flows.resume_flow` re-validates against the
    current definition (its count answer commits first, revealing the instance
    pages the rest of the map then seeds).
    """
    from ..user_profile import record_to_path_values
    from ._persistence import descendant_answers_from_record

    values = record_to_path_values(record)
    answers: dict[str, str] = {}
    for section in flow.sections:
        for question in section.questions:
            if question.profile_key is not None and question.profile_key in values:
                answers[question.id] = values[question.profile_key]
    answers.update(descendant_answers_from_record(record))
    return answers


class ProfileFactsCheckpointStore:
    """Create-mode :class:`~cadrumo.application.flows.CheckpointStore` over profile facts.

    Run-scoped: one instance per interactive create invocation, bound to
    the profile's immutable id and operator label. It owns its own storage
    spans (mint or upsert), so the caller never opens a create span around
    it. The store records whether its :meth:`save` port was invoked so the
    command can distinguish a frontend-driven save-and-exit (leave the
    profile ``incomplete``) from a normal submit (complete the setup).
    """

    def __init__(self, flow: WizardFlow, *, profile_id: str, profile_name: str) -> None:
        self._flow = flow
        self._profile_id = profile_id
        self._profile_name = profile_name
        self._save_exit_persisted = False

    @property
    def save_exit_persisted(self) -> bool:
        """Whether the frontend's save-and-exit invoked :meth:`save` this run."""
        return self._save_exit_persisted

    def save(self, flow_id: str, answers: Mapping[str, str]) -> None:
        """Persist the current answer map, recording that a save-and-exit fired.

        The substrate's ``save_checkpoint`` calls this from a frontend's
        save-and-exit affordance. The persistence is idempotent with the
        completion path (both upsert the same facts); the recorded flag is
        what lets the command leave the profile ``incomplete`` rather
        than completing it.
        """
        del flow_id
        self.persist(answers)
        self._save_exit_persisted = True

    def persist(self, answers: Mapping[str, str]) -> None:
        """Mint-if-absent then persist the answer map's facts through the authority.

        The first persist mints the profile in ``incomplete`` state
        (running the duplicate-tax-id refusal at genuine minting); later
        persists upsert onto the live record. Both routes write through the
        single profile-lifecycle writer into encrypted storage.
        """
        from ..user_profile import (
            ProfileFactWriteDoor,
            ProfileRecordRepository,
            ProfileRegistrationError,
            apply_profile_fact_changes,
        )
        from ..workflow import read_profile_bucket_by_id

        facts = checkpoint_facts_from_answers(self._flow, answers)
        pointer = read_profile_bucket_by_id(self._profile_id)
        if pointer is None:
            raise ProfileRegistrationError(
                "wizard checkpoint creation is unavailable; register with credentials before setup",
            )
        if not facts:
            return
        record = ProfileRecordRepository.for_current_session(self._profile_id).load(self._profile_id)
        clearing = descendant_clearing_facts(record, answers)
        apply_profile_fact_changes(
            profile_id=self._profile_id,
            changes=(*facts, *clearing),
            door=ProfileFactWriteDoor.CHECKPOINT,
        )

    def load(self, flow_id: str) -> Mapping[str, str] | None:
        """Return the in-progress answer map, or ``None`` when no resume is offered.

        A resume is offered ONLY while the profile is ``incomplete``:
        a completed or absent profile returns
        ``None``. The returned map is page-keyed and re-projected from the
        on-record facts for :func:`~cadrumo.application.flows.resume_flow`.

        Eligibility is decided by the encrypted current record. The committed
        capsule projection may only exclude an absent profile; its label never
        grants a resume capability. A profile resumes only when its current
        record is still ``INCOMPLETE``.
        """
        del flow_id
        from ...domain.user_profile import ProfileNotFoundError
        from ..user_profile import ProfileRecordRepository
        from ..workflow import read_profile_bucket_by_id

        # The committed projection can exclude an absent profile, but the
        # authenticated current record is the sole resume authority.
        if read_profile_bucket_by_id(self._profile_id) is None:
            return None
        try:
            record = ProfileRecordRepository.for_current_session(self._profile_id).load(self._profile_id)
        except ProfileNotFoundError:
            return None
        if record.setup_state is not ProfileSetupState.INCOMPLETE:
            return None
        return checkpoint_answers_from_record(self._flow, record)

    def discard(self, flow_id: str) -> None:
        """Erase the in-progress profile through the lifecycle authority.

        Current-capsule discard is unavailable until its deletion flow is
        rebuilt. A no-op when the profile was never minted.
        """
        del flow_id
        from ..user_profile import ProfileRegistrationError

        raise ProfileRegistrationError(
            "wizard checkpoint discard is unavailable until current-capsule deletion is rebuilt",
        )


__all__ = [
    "ProfileFactsCheckpointStore",
    "checkpoint_answers_from_record",
    "checkpoint_facts_from_answers",
    "descendant_clearing_facts",
]
