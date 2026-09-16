"""The refusal recovery action is reconciled against its target leaf alone."""

from __future__ import annotations

import json
import sys

import pytest

from cadrumo.tests.audited_process import run_audited_process

from ....application.operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE
from ..command_spec import CommandSpecGraph, SchemaState
from ..command_specs import COMMAND_GRAPH
from ..operator_surface_reconciliation import (
    current_operator_surface_reconciliation,
    operator_surface_target_reconciliation,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_target_reconciliation_equals_the_full_leaf_for_every_catalogue_target() -> None:
    full_leaves = {leaf.live_leaf.subject_leaf_key: leaf for leaf in current_operator_surface_reconciliation().leaves}
    targets = sorted({entry.target_command_key for entry in OPERATOR_ACTION_CATALOGUE.entries})

    assert targets
    for target in targets:
        assert operator_surface_target_reconciliation(target).leaves == (full_leaves[target],), target


def test_target_reconciliation_refuses_an_unknown_identity() -> None:
    with pytest.raises(LookupError, match=r"unknown command schema identity: config\.no_such_verb"):
        operator_surface_target_reconciliation("config.no_such_verb")


def test_schema_identity_search_matches_the_complete_graph_and_reports_absence() -> None:
    graph = CommandSpecGraph(COMMAND_GRAPH.declared, COMMAND_GRAPH.families)
    nodes_by_key = {node.spec.key: node for node in COMMAND_GRAPH.nodes()}
    complete = COMMAND_GRAPH.by_schema_identity()

    assert complete
    assert graph.find_schema_identity("config.no_such_verb") is None
    for identity, spec in complete.items():
        assert spec.result_schema.state is SchemaState.TARGET
        assert graph.find_schema_identity(identity) == nodes_by_key[spec.key], identity


def test_no_profile_refusal_loads_only_the_recovery_target_family() -> None:
    source = """
import json
import sys
from cadrumo.application.operator_actions.models import ActionArgumentBinding, ActionReference, ConditionEvidence, PreconditionVerdict
from cadrumo.core.operator_action_enums import ActionArgumentStatus, ActionConditionality, ActionEvidenceProvenance
from cadrumo.entrypoints.cli.command_schema import command_schema_refs
from cadrumo.entrypoints.cli.command_specs import COMMAND_GRAPH
from cadrumo.entrypoints.cli.common import resolve_cli_precondition_action

verdict = PreconditionVerdict(
    failed_condition_id="profile.active.available",
    evidence=(
        ConditionEvidence(
            condition_id="profile.active.available",
            evidence_id="profile.active.state",
            provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            values={"active_profile_present": False, "registered_profile_count": 0},
        ),
    ),
    action=ActionReference(action_id="operator.profile.create"),
    argument_bindings=(
        ActionArgumentBinding(argument_name="profile_name", status=ActionArgumentStatus.MISSING),
    ),
    missing_argument_names=("profile_name",),
    conditionality=ActionConditionality.REQUIRES_ARGUMENTS,
)
projected = resolve_cli_precondition_action(verdict)
print(json.dumps({
    "cli_path": projected.action.cli_path,
    "loaded_families": sorted(
        {family.source.module for family in COMMAND_GRAPH.families if family.source.module in sys.modules}
    ),
    "all_families": sorted({family.source.module for family in COMMAND_GRAPH.families}),
    "full_schema_projection_built": command_schema_refs.cache_info().currsize > 0,
}))
"""
    completed = run_audited_process([sys.executable, "-c", source], check=True, capture_output=True, text=True)
    result = json.loads(completed.stdout)

    assert result["cli_path"] == ["config", "profile", "create"]
    assert result["loaded_families"] == ["cadrumo.entrypoints.cli.config.command_specs"]
    assert len(result["all_families"]) > len(result["loaded_families"])
    assert result["full_schema_projection_built"] is False
