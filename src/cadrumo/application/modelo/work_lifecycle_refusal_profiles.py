"""Declared doors of the refusals that meet a work unit the operator addressed or a revision it holds.

Each family is one cause. A work unit that is absent, or an address whose
coordinates disagree, is found again from the work list. A mutation refused
because the unit changed after it was read, or a revision whose state does not
admit the request, is read again from the unit's status or revisions. An
amendment that restates nothing is the operator's decision. A modelo whose tax
is administered elsewhere, and an address the application itself resolved
incoherently, are beyond the operator and name no command.
"""

from __future__ import annotations

from typing import Final

from ...core.operator_action_enums import NoRecoveryOutcome
from ..operator_actions.models import ActionReference
from ..operator_surface.models import ManifestActionProfile

LIST_LEAF: Final[str] = "modelo.work.list"
STATUS_LEAF: Final[str] = "modelo.work.status"
CREATE_LEAF: Final[str] = "modelo.work.create"
REVISIONS_LEAF: Final[str] = "modelo.work.revisions"
AMEND_LEAF: Final[str] = "modelo.work.amend"

UNIT_ABSENT_SCENARIO: Final[str] = "modelo.work.lookup.unit.absent"
SELECTOR_CONTRADICTORY_SCENARIO: Final[str] = "modelo.work.selector.coordinates.contradictory"
SELECTOR_INCOHERENT_SCENARIO: Final[str] = "modelo.work.selector.resolution.incoherent"
MUTATION_STALE_SCENARIO: Final[str] = "modelo.work.mutation.baseline.stale"
CEDED_MODELO_SCENARIO: Final[str] = "modelo.work.create.jurisdiction.ceded_autonomic"
REVISION_STATE_SCENARIO: Final[str] = "modelo.work.revision.state.refused"
AMENDMENT_UNCHANGED_SCENARIO: Final[str] = "modelo.work.amend.content.unchanged"
AMENDMENT_DUPLICATE_SCENARIO: Final[str] = "modelo.work.amend.content.duplicate"


def _door(leaf: str, sound_condition: str, scenario: str, action_id: str) -> ManifestActionProfile:
    return ManifestActionProfile(
        subject_leaf_key=leaf,
        condition_id=sound_condition,
        scenario_id=scenario,
        action=ActionReference(action_id=action_id),
        no_recovery_outcome=None,
    )


def _no_door(leaf: str, sound_condition: str, scenario: str, outcome: NoRecoveryOutcome) -> ManifestActionProfile:
    return ManifestActionProfile(
        subject_leaf_key=leaf,
        condition_id=sound_condition,
        scenario_id=scenario,
        action=None,
        no_recovery_outcome=outcome,
    )


WORK_LIFECYCLE_REFUSAL_PROFILES: Final[tuple[ManifestActionProfile, ...]] = (
    _door(LIST_LEAF, "modelo.work.lookup.unit.present", UNIT_ABSENT_SCENARIO, "operator.modelo.work.list"),
    _door(
        LIST_LEAF,
        "modelo.work.selector.coordinates.consistent",
        SELECTOR_CONTRADICTORY_SCENARIO,
        "operator.modelo.work.list",
    ),
    _no_door(
        LIST_LEAF,
        "modelo.work.selector.resolution.coherent",
        SELECTOR_INCOHERENT_SCENARIO,
        NoRecoveryOutcome.TERMINAL,
    ),
    _door(STATUS_LEAF, "modelo.work.mutation.baseline.current", MUTATION_STALE_SCENARIO, "operator.modelo.work.status"),
    _no_door(
        CREATE_LEAF,
        "modelo.work.create.jurisdiction.state_administered",
        CEDED_MODELO_SCENARIO,
        NoRecoveryOutcome.TERMINAL,
    ),
    _door(
        REVISIONS_LEAF,
        "modelo.work.revision.state.admitted",
        REVISION_STATE_SCENARIO,
        "operator.modelo.work.revisions",
    ),
    _no_door(
        AMEND_LEAF,
        "modelo.work.amend.content.distinct",
        AMENDMENT_UNCHANGED_SCENARIO,
        NoRecoveryOutcome.OPERATOR_DECISION,
    ),
    _no_door(
        AMEND_LEAF,
        "modelo.work.amend.content.new",
        AMENDMENT_DUPLICATE_SCENARIO,
        NoRecoveryOutcome.OPERATOR_DECISION,
    ),
)
"""The work lookup, selector, mutation and revision-state refusal families' declarations."""

__all__ = [
    "AMENDMENT_DUPLICATE_SCENARIO",
    "AMENDMENT_UNCHANGED_SCENARIO",
    "CEDED_MODELO_SCENARIO",
    "MUTATION_STALE_SCENARIO",
    "REVISION_STATE_SCENARIO",
    "SELECTOR_CONTRADICTORY_SCENARIO",
    "SELECTOR_INCOHERENT_SCENARIO",
    "UNIT_ABSENT_SCENARIO",
    "WORK_LIFECYCLE_REFUSAL_PROFILES",
]
