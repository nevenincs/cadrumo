"""Create-mode checkpoint port: the profile facts ARE the checkpoint.

The substrate defines the checkpoint PORT
(:class:`~cadrumo.application.flows.CheckpointStore`); this module supplies
the profile domain's implementation. There is no bespoke checkpoint object,
no stored cursor, and no answer-map artefact: the in-progress answers persist
as effective-dated :class:`~cadrumo.domain.user_profile.UserProfileFact` rows
through the profile lifecycle authority, exactly like every committed answer,
and the record's ``SETUP_INCOMPLETE`` lifecycle state is the resume-eligibility
flag.

Lifecycle of a create-mode checkpoint:

* **save** — projects the current canonical answer map to facts and persists
  them through the lifecycle authority. The first save with a validated
  ``tax-id`` mints the profile early in ``SETUP_INCOMPLETE`` state (so
  ``_refuse_duplicate_tax_id`` fires at genuine minting); later saves upsert
  onto the live record. Sensitive answers ride only this authority into the
  encrypted secure-object store — never a plaintext sink, never a log.
* **load** — offers a resume ONLY while the active profile's status is
  ``SETUP_INCOMPLETE``, re-projecting the on-record facts back to a page-keyed
  answer map. ``resume_flow`` recomputes everything derived (cursor, staleness,
  validation) against the *current* definition; a completed or absent profile
  returns ``None`` (no resume).
* **discard** — explicit operator abandonment erases the incomplete profile
  through the existing lifecycle/composition arms (soft tombstone + directory
  erase), never a parallel delete path.

Completion (the ``SETUP_INCOMPLETE`` → ``ACTIVE`` flip at the flow's final
commit) is the domain-owned completion discard: the status flip ends
resume-eligibility, so there is nothing else to erase. It is driven by the
command through :func:`~cadrumo.application.user_profile.complete_setup_with_lifecycle_span`,
not by this store.
"""

from __future__ import annotations

from collections.abc import Mapping

from ...domain.user_profile import UserProfileFact, UserProfileRecord, UserProfileStatus
from ._models import WizardFlow


def checkpoint_facts_from_answers(flow: WizardFlow, answers: Mapping[str, str]) -> tuple[UserProfileFact, ...]:
    """Project a page-keyed canonical answer map into profile facts.

    Only profile-bound questions contribute a fact, keyed by the
    question's ``profile_key`` (the schema fact path). A blank canonical
    token contributes nothing — the persistence layer's drop-blank rule,
    so an unanswered page never writes an empty fact. The answers are
    already engine-validated canonical tokens, so no re-validation runs
    here.
    """
    facts: list[UserProfileFact] = []
    for section in flow.sections:
        for question in section.questions:
            if question.profile_key is None:
                continue
            value = answers.get(question.id)
            if value:
                facts.append(UserProfileFact(path=question.profile_key, value=value))
    return tuple(facts)


def checkpoint_answers_from_record(flow: WizardFlow, record: UserProfileRecord | None) -> dict[str, str]:
    """Re-project a :class:`UserProfileRecord`'s on-record facts into a page-keyed answer map.

    The inverse of :func:`checkpoint_facts_from_answers`: each profile-bound
    question whose ``profile_key`` carries a live fact on the
    :class:`UserProfileRecord` re-appears keyed by page id (the setup flow
    has no repeating groups, so page id equals question id). This is the
    seed :func:`~cadrumo.application.flows.resume_flow` re-validates against
    the current definition.
    """
    from ..user_profile import record_to_path_values

    values = record_to_path_values(record)
    answers: dict[str, str] = {}
    for section in flow.sections:
        for question in section.questions:
            if question.profile_key is not None and question.profile_key in values:
                answers[question.id] = values[question.profile_key]
    return answers


class ProfileFactsCheckpointStore:
    """Create-mode :class:`~cadrumo.application.flows.CheckpointStore` over profile facts.

    Run-scoped: one instance per interactive create invocation, bound to
    the profile's immutable id and operator label. It owns its own storage
    spans (mint or upsert), so the caller never opens a create span around
    it. The store records whether its :meth:`save` port was invoked so the
    command can distinguish a frontend-driven save-and-exit (leave the
    profile ``SETUP_INCOMPLETE``) from a normal submit (complete the setup).
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
        what lets the command leave the profile ``SETUP_INCOMPLETE`` rather
        than completing it.
        """
        del flow_id
        self.persist(answers)
        self._save_exit_persisted = True

    def persist(self, answers: Mapping[str, str]) -> None:
        """Mint-if-absent then persist the answer map's facts through the authority.

        The first persist mints the profile in ``SETUP_INCOMPLETE`` state
        (running the duplicate-tax-id refusal at genuine minting); later
        persists upsert onto the live record. Both routes write through the
        single profile-lifecycle writer into encrypted storage.
        """
        from ..user_profile import (
            profile_create_storage_span,
            register_active_profile,
            set_active_fields,
        )
        from ..workflow import read_profile_bucket_by_id, workflow_state_repository

        facts = checkpoint_facts_from_answers(self._flow, answers)
        pointer = read_profile_bucket_by_id(self._profile_id)
        if pointer is None:
            with profile_create_storage_span(self._profile_id):
                workflow_state_repository().update(
                    lambda state: register_active_profile(
                        state,
                        profile_id=self._profile_id,
                        display_name=self._profile_name,
                        facts=facts,
                        status=UserProfileStatus.SETUP_INCOMPLETE,
                    ),
                )
            return
        if not facts:
            return
        with self._existing_profile_span():
            workflow_state_repository().update(lambda state: set_active_fields(state, facts))

    def load(self, flow_id: str) -> Mapping[str, str] | None:
        """Return the in-progress answer map, or ``None`` when no resume is offered.

        A resume is offered ONLY while the profile is ``SETUP_INCOMPLETE``:
        a completed (``ACTIVE``), tombstoned, or absent profile returns
        ``None``. The returned map is page-keyed and re-projected from the
        on-record facts for :func:`~cadrumo.application.flows.resume_flow`.
        """
        del flow_id
        from ..workflow import read_profile_bucket_by_id, workflow_state_repository

        pointer = read_profile_bucket_by_id(self._profile_id)
        if pointer is None or pointer.status is not UserProfileStatus.SETUP_INCOMPLETE:
            return None
        with self._existing_profile_span():
            record = workflow_state_repository().load().active_profile_record()
        return checkpoint_answers_from_record(self._flow, record)

    def discard(self, flow_id: str) -> None:
        """Erase the in-progress profile through the lifecycle authority.

        Explicit operator abandonment: the incomplete profile is soft
        tombstoned and its bucket directory erased, reusing the existing
        composition arms rather than a parallel delete. A no-op when the
        profile was never minted.
        """
        del flow_id
        from ..user_profile import (
            delete_profile_with_lifecycle_span,
            remove_profile_bucket_directory,
        )
        from ..workflow import read_profile_bucket_by_id

        pointer = read_profile_bucket_by_id(self._profile_id)
        if pointer is None:
            return
        delete_profile_with_lifecycle_span(self._profile_id)
        remove_profile_bucket_directory(self._profile_id)

    def _existing_profile_span(self):
        """Open an application-owned storage session for the minted profile."""
        from ..user_profile import profile_storage_session

        return profile_storage_session(self._profile_id)


__all__ = [
    "ProfileFactsCheckpointStore",
    "checkpoint_answers_from_record",
    "checkpoint_facts_from_answers",
]
