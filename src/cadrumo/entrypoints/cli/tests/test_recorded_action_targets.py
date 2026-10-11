"""The recorded action targets say of every catalogue action's command what the command graph says.

A process that holds no command graph resolves a recovery action against the
record. These tests hold the record to the graph for every action in the
catalogue, and hold the resolver that reads the record to the one the command
line uses.
"""

from __future__ import annotations

import pytest

from ....application.operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE, ActionCatalogueEntry
from ....application.operator_actions.models import (
    ActionArgumentBinding,
    ActionReference,
    ConditionEvidence,
    PreconditionVerdict,
)
from ....application.operator_surface.action_targets import (
    ACTION_TARGETS,
    ActionTarget,
    recorded_action_target_reconciliation,
    resolve_recorded_precondition_action,
)
from ....application.operator_surface.manifest import ReconciledOperatorLeaf
from ....core.operator_action_enums import ActionArgumentStatus, ActionConditionality, ActionEvidenceProvenance
from ..common import resolve_cli_precondition_action
from ..operator_surface_reconciliation import operator_surface_target_reconciliation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CONDITION = "synthetic.condition.holds"


def _targets() -> tuple[str, ...]:
    return tuple(sorted({entry.target_command_key for entry in OPERATOR_ACTION_CATALOGUE.entries}))


def _graph_leaf(command_key: str) -> ReconciledOperatorLeaf:
    (leaf,) = operator_surface_target_reconciliation(command_key).leaves
    return leaf


def _facts(leaf: ReconciledOperatorLeaf) -> object:
    """Return everything a leaf says apart from where each row was read from."""

    def without_provenance(value: object) -> object:
        if isinstance(value, dict):
            return {key: without_provenance(item) for key, item in value.items() if key != "provenance"}
        if isinstance(value, list):
            return [without_provenance(item) for item in value]
        return value

    return without_provenance(leaf.model_dump(mode="json"))


def _verdict(entry: ActionCatalogueEntry) -> PreconditionVerdict:
    """Build a verdict that recommends ``entry`` and leaves every declared argument to the operator."""
    names = tuple(sorted({specification.argument_name for specification in entry.argument_specifications}))
    return PreconditionVerdict(
        failed_condition_id=_CONDITION,
        evidence=(
            ConditionEvidence(
                condition_id=_CONDITION,
                evidence_id="synthetic.condition.observed",
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                values={"holds": False},
            ),
        ),
        action=ActionReference(action_id=entry.action_id),
        argument_bindings=tuple(
            ActionArgumentBinding(argument_name=name, status=ActionArgumentStatus.MISSING) for name in names
        ),
        missing_argument_names=names,
        conditionality=ActionConditionality.REQUIRES_ARGUMENTS if names else ActionConditionality.IMMEDIATE,
    )


def test_the_record_is_exactly_what_the_command_graph_declares_for_every_catalogue_target() -> None:
    derived = tuple(ActionTarget.of_leaf(_graph_leaf(command_key)) for command_key in _targets())

    assert derived
    assert derived == ACTION_TARGETS, (
        "the recorded action targets no longer match the command graph; record these instead:\n"
        + "\n".join(repr(target) for target in derived)
    )


def test_a_recorded_leaf_reconciles_to_the_leaf_the_command_graph_reconciles() -> None:
    for command_key in _targets():
        (recorded,) = recorded_action_target_reconciliation(command_key).leaves

        assert _facts(recorded) == _facts(_graph_leaf(command_key)), command_key


def test_the_recorded_resolver_prints_the_action_the_command_line_prints_for_every_catalogue_action() -> None:
    for entry in OPERATOR_ACTION_CATALOGUE.entries:
        verdict = _verdict(entry)

        recorded = resolve_recorded_precondition_action(verdict)
        printed = resolve_cli_precondition_action(verdict)

        assert recorded == printed, entry.action_id
        assert recorded.action is not None and recorded.action.cli_path, entry.action_id
        assert recorded.action.target_command_key == entry.target_command_key


def test_the_record_refuses_a_command_no_catalogue_action_targets() -> None:
    with pytest.raises(LookupError, match=r"unknown command schema identity: config\.no_such_verb"):
        recorded_action_target_reconciliation("config.no_such_verb")


def test_a_leaf_the_record_cannot_hold_is_refused_rather_than_recorded_in_part() -> None:
    leaf = _graph_leaf(_targets()[0])
    aliased = leaf.model_copy(
        update={"live_leaf": leaf.live_leaf.model_copy(update={"alias_cli_paths": (("synthetic", "alias"),)})}
    )
    unaccounted = leaf.model_copy(update={"input_schema": None})

    for unrecordable in (aliased, unaccounted):
        with pytest.raises(ValueError, match="action target leaf cannot be recorded"):
            ActionTarget.of_leaf(unrecordable)
