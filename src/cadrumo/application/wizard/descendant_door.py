"""The paged descendant door onto the setup flow's repeating group.

A dedicated, descendant-only :class:`~cadrumo.application.flows.definition.FlowDefinition`
that hosts the exact count page and
:class:`~cadrumo.application.flows.definition.FlowRepeatingGroup` the full setup flow uses
(:func:`~cadrumo.application.wizard.descendant_group.build_descendant_group` and the
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

The caller seeds the flow from the authorized profile facts through
:func:`~cadrumo.application.flows.resume.resume_flow`, whose walk commits the
count answer first and then seeds each instance answer, and projects the
submitted answers back through
:func:`~cadrumo.application.wizard.persistence.descendant_facts_from_answers`.

The door declares checkpointing UNAVAILABLE in both modes: the commit is owned
by the caller, not by a frontend save-and-exit, so no checkpoint store is wired.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core.flows import CheckpointAvailability, FlowMode
from ...core.models import STRICT_FROZEN_CONFIG
from ..flows.definition import FlowDefinition, FlowSection
from ..flows.definition import locale_copy_ref as _locale_ref
from .catalogue import FAMILIA_SECTION_ID as _FAMILIA_SECTION_ID
from .descendant_group import (
    DESCENDANT_ENTRY_EVENT_VALIDATOR_ID,
    build_descendant_count_page,
    build_descendant_group,
)

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

#: The door's flow and familia section ids.
DESCENDANT_DOOR_FLOW_ID = "descendiente-door"

# Copy references — both keys already ship in the four locale catalogues, so the
# door adds no new locale key. Declared as module constants so the static locale
# scanner treats them as live (referenced only inside the frozen literals below,
# never at a ``tr()`` call site).
_FLOW_TITLE_LOCALE_KEY = "wizard.setup.descendientes.title"
_FLOW_DESCRIPTION_LOCALE_KEY = "cli.config.profile.descendiente.help"


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


def build_descendant_door_definition(*, operation: PinnedAuthorityOperation) -> FlowDefinition:
    """Return the descendant-only door :class:`FlowDefinition`.

    Adopts the operation-scoped count page and
    :func:`~cadrumo.application.wizard.descendant_group.build_descendant_group`
    verbatim into a single familia section, and names the entry-event
    cross-field validator on the definition so a bad entry date — or one the
    declared relación cannot carry — blocks submit — the same
    validators the setup flow runs. The count page's ``visible_when`` gate on the
    ``entity-type`` page is stripped: the door has no ``entity-type`` page (an
    operator who opened the descendant surface is declaring descendants), and a
    gate naming a page absent from the definition would fail the definition's
    earlier-page-reference validator at construction.
    """
    count_page = build_descendant_count_page(operation).model_copy(update={"visible_when": None})
    descendant_group = build_descendant_group(operation)
    section = FlowSection(
        id=_FAMILIA_SECTION_ID,
        title=_locale_ref(_FLOW_TITLE_LOCALE_KEY),
        items=(count_page, descendant_group),
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


__all__ = [
    "DESCENDANT_DOOR_FLOW_ID",
    "DescendantDoorAnswers",
    "build_descendant_door_definition",
]
