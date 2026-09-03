"""Conformance over every enrolled C4 action, checked as one closed set.

The per-action suites each prove their own action deeply. This module proves
the properties that only make sense across ALL of them at once: that no action
is missing a disposition its siblings carry, that a mutating action always has
a registered definition behind it, and that none became available before its
own proof existed.

A per-action suite cannot catch an action that was simply never given one.

See Also:
    :mod:`cadrumo.entrypoints.tui.modelo.actions`
"""

from __future__ import annotations

import pathlib

import pytest

from .....application.modelo import operation_definitions as definitions
from .....application.modelo.operation_definitions import MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID
from .....application.modelo.workspace_models import ModeloWorkspaceCapabilityName
from .....application.operations.registry import OperationDefinition, OperationInteractionKind
from ..actions import MODELO_ACTION_DISPATCH, ModeloActionPort

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_ACTION_ROOT = pathlib.Path(__file__).resolve().parents[1] / "action"


def _built_definitions() -> dict[str, OperationDefinition]:
    """Build every modelo operation definition the application declares."""
    built: dict[str, OperationDefinition] = {}
    for name in dir(definitions):
        if not (name.startswith("build_modelo") and name.endswith("_definition")):
            continue
        definition = getattr(definitions, name)()
        if not isinstance(definition, OperationDefinition):
            raise AssertionError(f"{name} does not build an OperationDefinition: {type(definition).__name__}")
        built[definition.definition_id] = definition
    return built


def test_the_definition_set_is_actually_built() -> None:
    """Anti-vacuity: every check below is vacuous over an empty definition set."""
    built = _built_definitions()

    assert len(built) >= len(MODELO_ACTION_DISPATCH), (
        f"only {len(built)} definitions built for {len(MODELO_ACTION_DISPATCH)} dispatch rows"
    )


def test_every_dispatchable_action_has_a_registered_definition() -> None:
    """A mutating action with no definition behind it would submit into nothing."""
    built = _built_definitions()

    missing = sorted(set(MODELO_ACTION_DISPATCH) - set(built))
    assert not missing, f"dispatch rows with no registered definition: {missing}"


def test_every_action_states_a_capability_disposition_rather_than_omitting_one() -> None:
    """`None` is an answer here; a missing field would not be.

    The row's capability is typed as an optional enum, so an action either
    names the workspace capability that gates it or explicitly states that its
    availability is not a workspace-capability question. What must not happen
    is a row carrying something that is neither.
    """
    for action_id, row in MODELO_ACTION_DISPATCH.items():
        assert row.capability is None or isinstance(row.capability, ModeloWorkspaceCapabilityName), (
            f"{action_id} carries a capability that is neither a declared name nor an explicit None"
        )


def test_the_capability_free_actions_are_exactly_the_work_unit_lifecycle_ones() -> None:
    """Which actions answer `None` is itself a claim, so it is pinned.

    Rename and discard act on the work unit's own lifecycle and are not gated
    by what a workspace projection measured. Any OTHER action answering `None`
    would be an ungated mutation wearing the same shape, so the set is named
    rather than counted.
    """
    ungated = {action_id for action_id, row in MODELO_ACTION_DISPATCH.items() if row.capability is None}

    assert ungated == {"modelo.work.rename", "modelo.work.discard"}, (
        f"the set of capability-free actions changed; an ungated mutation may have been added: {sorted(ungated)}"
    )


def test_only_the_editor_apply_declares_a_mid_flight_interaction() -> None:
    """An interaction means the modal must prompt before the run can settle.

    Every other action carries its operator's decision IN THE REQUEST -- the
    discard baseline, the file approval, the amendment reason -- so it runs to
    settlement without asking anything further. Declaring an interaction an
    action does not have would leave the modal waiting for input nobody will
    give.
    """
    built = _built_definitions()

    interactive = {
        action_id for action_id in MODELO_ACTION_DISPATCH if built[action_id].interaction_kinds
    }
    assert interactive == {MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID}, (
        f"the set of actions declaring an interaction changed: {sorted(interactive)}"
    )
    assert OperationInteractionKind.INPUT in built[MODELO_EDIT_APPLY_OPERATION_DEFINITION_ID].interaction_kinds


def test_every_action_maps_to_a_terminal_destination() -> None:
    """ "Where did this leave me" is asked after every mutation, so every row answers."""
    for action_id, row in MODELO_ACTION_DISPATCH.items():
        assert row.result_destination, f"{action_id} names no destination for a settled run"
        assert row.result_destination.startswith("modelo."), (
            f"{action_id} lands on {row.result_destination!r}, which is not a modelo route identity"
        )


def test_a_destructive_action_never_returns_to_the_surface_it_destroyed() -> None:
    """Checked across the set, so a future destructive action inherits the rule."""
    destructive = {action_id for action_id, row in MODELO_ACTION_DISPATCH.items() if row.destroys_subject}

    assert destructive, "no destructive action is declared; this proof would be vacuous"
    for action_id in destructive:
        destination = MODELO_ACTION_DISPATCH[action_id].result_destination
        assert not destination.startswith("modelo.workspace."), (
            f"{action_id} destroys its subject but lands on {destination}"
        )


def test_every_port_is_a_member_of_the_closed_set() -> None:
    """A row may not describe a reach the cohort has not adjudicated."""
    for row in MODELO_ACTION_DISPATCH.values():
        assert isinstance(row.port, ModeloActionPort)


def test_no_action_is_available_before_its_own_proof_exists() -> None:
    """Availability without a proof is the thing this phase exists to prevent.

    Every enrolment module under `action/` must have a matching per-action
    suite. An action reachable from a surface with nothing asserting how it
    behaves is available on the strength of nobody having checked it.
    """
    enrolled = sorted(path.stem for path in _ACTION_ROOT.glob("*.py") if not path.stem.startswith("_"))
    assert enrolled, "no enrolment modules found; this proof would be vacuous"

    here = pathlib.Path(__file__).parent
    unproven = [name for name in enrolled if not (here / f"test_c4_{name}_action.py").exists()]
    assert not unproven, f"enrolled actions with no per-action proof suite: {unproven}"
