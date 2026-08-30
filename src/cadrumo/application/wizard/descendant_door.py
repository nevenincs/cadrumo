"""The paged descendant door onto the setup flow's repeating group.

A dedicated, descendant-only :class:`~cadrumo.application.flows.definition.FlowDefinition`
that hosts the exact count page and
:class:`~cadrumo.application.flows.definition.FlowRepeatingGroup` the full setup flow uses
(:data:`~cadrumo.application.wizard.descendant_group.DESCENDANTS_COUNT_PAGE`,
:data:`~cadrumo.application.wizard.descendant_group.DESCENDANT_GROUP`, and the
entry-event cross-field validator id) — the pages and validators are *adopted*, not
re-authored, so the door and the setup flow can never diverge on the descendant
surface.

The door exists because modify-mode seeding cannot instantiate the repeating
group inside the main setup flow: instance pages are generated dynamically from
the count answer, so the render-time default-seed mechanism cannot reach them and
the group is withheld from a bridged modify definition. This door closes that gap
by seeding through :func:`~cadrumo.application.flows.resume.resume_flow`, whose walk
commits the count answer first (revealing the instance pages) and then seeds each
instance answer — the one seeding channel that re-instantiates the group from
persisted facts.

Lifecycle of one door invocation:

* **seed** — :func:`build_descendant_door` reads the active
  :class:`~cadrumo.domain.user_profile.values.UserProfileRecord`, re-projects its
  ``renta_family.descendiente.{n}.*`` facts to a page-keyed answer map through
  :func:`~cadrumo.application.wizard.persistence.descendant_answers_from_record`,
  and resumes a MODIFY-mode :class:`~cadrumo.application.flows.engine.FlowState` over the
  door definition so the operator opens on their existing descendants.
* **commit** — :func:`persist_descendant_door_answers` projects the submitted
  answers back through
  :func:`~cadrumo.application.wizard.persistence.descendant_facts_from_answers`
  and clears the orphaned rows a shrunk count leaves behind through
  :func:`~cadrumo.application.wizard._checkpoint_store.descendant_clearing_facts`,
  in one revision-bound record command. The door only commits to an
  already-registered, authenticated profile.

The door declares checkpointing UNAVAILABLE in both modes: the commit is owned
here, not by a frontend save-and-exit, so no checkpoint store is wired.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core.models import STRICT_FROZEN_CONFIG
from ...core.flows import CheckpointAvailability, CopyRefKind, FlowMode
from ..flows.definition import CopyRef, FlowDefinition, FlowSection
from ..flows.engine import FlowState
from ..flows.resume import resume_flow
from ._checkpoint_store import descendant_clearing_facts
from .descendant_group import (
    DESCENDANT_ENTRY_EVENT_VALIDATOR_ID,
    DESCENDANT_GROUP,
    DESCENDANTS_COUNT_PAGE,
)
from .persistence import descendant_answers_from_record, descendant_facts_from_answers

if TYPE_CHECKING:
    from prompt_toolkit.input import Input
    from prompt_toolkit.output import Output

    from ...domain.user_profile.values import UserProfileRecord
    from ..flows.review import ReviewProjection

#: The door's flow and familia section ids.
DESCENDANT_DOOR_FLOW_ID = "descendiente-door"
_FAMILIA_SECTION_ID = "familia"

# Copy references — both keys already ship in the four locale catalogues, so the
# door adds no new locale key. Declared as module constants so the static locale
# scanner treats them as live (referenced only inside the frozen literals below,
# never at a ``tr()`` call site).
_FLOW_TITLE_LOCALE_KEY = "wizard.setup.descendientes.title"
_FLOW_DESCRIPTION_LOCALE_KEY = "cli.config.profile.descendiente.help"

#: Every locale key this module references, for the scaffold gate.
DESCENDANT_DOOR_LOCALE_KEYS: tuple[str, ...] = (
    _FLOW_TITLE_LOCALE_KEY,
    _FLOW_DESCRIPTION_LOCALE_KEY,
)


class DescendantDoorAnswers(BaseModel):
    """The door's declared ``answers_model``: the group carries every answer.

    The descendant surface is entirely a repeating group whose instance answers
    key the canonical map as ``descendientes#<index>.<page-id>`` — none is a
    top-level model field — so the door's typed answer model is empty. The commit
    path reads the engine's committed page-keyed answer map directly (through
    :func:`~cadrumo.application.wizard.persistence.descendant_facts_from_answers`),
    never a projection through this model; it exists only to satisfy the
    :class:`~cadrumo.application.flows.definition.FlowDefinition` contract.
    """

    model_config = STRICT_FROZEN_CONFIG


def _locale_ref(key: str) -> CopyRef:
    return CopyRef(kind=CopyRefKind.LOCALE_KEY, ref=key)


def build_descendant_door_definition() -> FlowDefinition:
    """Return the descendant-only door :class:`FlowDefinition`.

    Adopts :data:`~cadrumo.application.wizard.descendant_group.DESCENDANTS_COUNT_PAGE`
    and :data:`~cadrumo.application.wizard.descendant_group.DESCENDANT_GROUP`
    verbatim into a single familia section, and names the entry-event
    cross-field validator on the definition so a bad entry date — or one the
    declared relación cannot carry — blocks submit — the same
    validators the setup flow runs. The count page's ``visible_when`` gate on the
    ``entity-type`` page is stripped: the door has no ``entity-type`` page (an
    operator who opened the descendant surface is declaring descendants), and a
    gate naming a page absent from the definition would fail the definition's
    earlier-page-reference validator at construction.
    """
    count_page = DESCENDANTS_COUNT_PAGE.model_copy(update={"visible_when": None})
    section = FlowSection(
        id=_FAMILIA_SECTION_ID,
        title=_locale_ref(_FLOW_TITLE_LOCALE_KEY),
        items=(count_page, DESCENDANT_GROUP),
    )
    return FlowDefinition(
        id=DESCENDANT_DOOR_FLOW_ID,
        title=_locale_ref(_FLOW_TITLE_LOCALE_KEY),
        description=_locale_ref(_FLOW_DESCRIPTION_LOCALE_KEY),
        sections=(section,),
        answers_model=DescendantDoorAnswers,
        checkpoint={
            FlowMode.CREATE: CheckpointAvailability.UNAVAILABLE,
            FlowMode.MODIFY: CheckpointAvailability.UNAVAILABLE,
        },
        flow_validator_ids=(DESCENDANT_ENTRY_EVENT_VALIDATOR_ID,),
    )


def build_descendant_door(record: UserProfileRecord | None) -> tuple[FlowDefinition, FlowState]:
    """Return the door definition and a MODIFY-mode state seeded from ``record``.

    Re-projects the record's ``renta_family.descendiente.{n}.*`` facts into the
    page-keyed answer map through
    :func:`~cadrumo.application.wizard.persistence.descendant_answers_from_record`,
    then resumes a fresh :class:`~cadrumo.application.flows.engine.FlowState` over the
    door definition: :func:`~cadrumo.application.flows.resume.resume_flow` commits the
    seeded count answer first (revealing the instance pages) and then seeds each
    instance answer against the current definition, so the operator opens on their
    existing descendants. A childless record seeds an empty map and opens on the
    count page's zero default.

    Args:
        record: The :class:`UserProfileRecord` whose descendant facts seed the
            resumed flow state, or ``None`` for a childless record.
    """
    definition = build_descendant_door_definition()
    seed = descendant_answers_from_record(record)
    resume_state = resume_flow(definition, seed, mode=FlowMode.MODIFY)
    return definition, resume_state


def load_active_descendant_record() -> UserProfileRecord:
    """Load the authoritative record that one descendant-door run will edit."""
    from ...core.bucket_pointer import require_active_bucket_id
    from ..user_profile.profile_record_repository import ProfileRecordRepository

    profile_id = require_active_bucket_id()
    return ProfileRecordRepository.for_current_session(profile_id).load(profile_id)


def persist_descendant_door_answers(
    answers: Mapping[str, str],
    *,
    baseline: UserProfileRecord,
) -> UserProfileRecord:
    """Commit the door's submitted answers as the full descendant fact set.

    Projects the committed page-keyed answers into the canonical
    ``renta_family.descendiente.{n}.*`` facts and aggregates through
    :func:`~cadrumo.application.wizard.persistence.descendant_facts_from_answers`,
    and clears every on-record descendant path the fresh projection no longer
    covers (a shrunk count, a removed optional field) through
    :func:`~cadrumo.application.wizard._checkpoint_store.descendant_clearing_facts`,
    in one authenticated compare-and-swap command. The clearing reads the
    authoritative current record before constructing the replacement, so a
    count-shrink never strands a descendant index above the answered count.
    """
    from ...core.bucket_pointer import require_active_bucket_id
    from ...domain.user_profile.values import UserProfileFact
    from ..user_profile.fact_write import ProfileFactWriteDoor, apply_profile_fact_changes

    profile_id = require_active_bucket_id()
    if str(baseline.profile_id) != profile_id:
        raise ValueError("descendant door baseline does not belong to the active profile")
    facts = tuple(UserProfileFact(path=path, value=value) for path, value in descendant_facts_from_answers(answers))
    clearing = descendant_clearing_facts(baseline, answers)
    return apply_profile_fact_changes(
        profile_id=profile_id,
        changes=(*facts, *clearing),
        door=ProfileFactWriteDoor.DESCENDANTS,
        expected_record=baseline,
    )


def run_descendant_door(
    *,
    input: Input | None = None,
    output: Output | None = None,
) -> tuple[FlowState, ReviewProjection, UserProfileRecord]:
    """Drive and persist one descendant door invocation through the real line frontend.

    The door resolves and loads the authenticated active profile itself before
    prompting, binding the submitted write to that exact revision and digest.
    Headless callers bind prompt-toolkit devices,
    which exercises the same production frontend and the same atomic profile
    writer without replacing either boundary with a test callback.
    """
    from ..flows.line_frontend import LineFlowFrontend

    baseline = load_active_descendant_record()
    definition, resume_state = build_descendant_door(baseline)
    state, projection = LineFlowFrontend(
        definition,
        input=input,
        output=output,
    ).run(
        mode=FlowMode.MODIFY,
        resume_state=resume_state,
    )
    persisted = persist_descendant_door_answers(state.answers, baseline=baseline)
    return state, projection, persisted


__all__ = [
    "DESCENDANT_DOOR_FLOW_ID",
    "DESCENDANT_DOOR_LOCALE_KEYS",
    "DescendantDoorAnswers",
    "build_descendant_door",
    "build_descendant_door_definition",
    "load_active_descendant_record",
    "persist_descendant_door_answers",
    "run_descendant_door",
]
