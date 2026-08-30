"""CommandSpec projection proof for canonical action resolution."""

from __future__ import annotations

import pytest

from ....core import NoRecoveryOutcome
from ....entrypoints.cli.command_api import build_verb_input_schemas, command_schema_refs
from ...operator_actions import (
    OPERATOR_ACTION_CATALOGUE,
    ActionReference,
)
from ..manifest import (
    InputSchemaInventoryRow,
    LiveLeafInventoryRow,
    OperatorSurfaceReconciliation,
    ReconciledOperatorLeaf,
    ResultSchemaInventoryRow,
    resolve_manifest_action_profiles,
)
from ..models import ManifestActionProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_canonical_catalogue_resolves_against_real_live_command_and_input_schemas() -> None:
    schema_refs = command_schema_refs()
    schema_ref_by_key = {schema_ref.command: schema_ref for schema_ref in schema_refs}
    input_schemas = build_verb_input_schemas(tuple(sorted(schema_ref_by_key)))
    reconciliation = OperatorSurfaceReconciliation(
        leaves=tuple(
            ReconciledOperatorLeaf(
                live_leaf=LiveLeafInventoryRow(
                    subject_leaf_key=command_key,
                    canonical_cli_path=input_schema.resolved_leaf.cli_path,
                    alias_cli_paths=input_schema.resolved_leaf.alias_paths,
                    provenance="production CommandSpec operator path",
                ),
                result_schema=ResultSchemaInventoryRow(
                    subject_leaf_key=command_key,
                    schema_name=schema_ref_by_key[command_key].schema_name,
                    provenance="production CommandSpec result schema",
                ),
                input_schema=InputSchemaInventoryRow(
                    subject_leaf_key=command_key,
                    required_input_names=tuple(parameter.name for parameter in input_schema.required_inputs),
                    provenance="production CommandSpec input projection",
                ),
                mounted_family=None,
                profile_policy=None,
                surface_exposure=None,
                exclusions=(),
            )
            for command_key, input_schema in sorted(input_schemas.items())
        )
    )
    actionable = ManifestActionProfile(
        subject_leaf_key="overview.status",
        condition_id="operator.profile.missing",
        scenario_id="scenario.profile.absent",
        action=ActionReference(action_id="operator.overview.status"),
    )
    closed = ManifestActionProfile(
        subject_leaf_key="root.status",
        condition_id="operator.safety.boundary",
        scenario_id="scenario.external.mutation",
        no_recovery_outcome=NoRecoveryOutcome.SAFETY,
    )

    resolution = resolve_manifest_action_profiles(
        profiles=(actionable, closed),
        catalogue=OPERATOR_ACTION_CATALOGUE,
        reconciliation=reconciliation,
    )

    assert {action.action_id for action in resolution.catalogue_actions} == {
        declaration.action_id for declaration in OPERATOR_ACTION_CATALOGUE.entries
    }
    for declaration in OPERATOR_ACTION_CATALOGUE.entries:
        resolved = resolution.action_for(declaration.action_id)
        live_schema = input_schemas[declaration.target_command_key]
        assert resolved.declaration == declaration
        assert resolved.target_leaf.live_leaf.canonical_cli_path == live_schema.resolved_leaf.cli_path
        assert resolved.target_leaf.input_schema is not None
        assert resolved.target_leaf.input_schema.required_input_names == tuple(
            parameter.name for parameter in live_schema.required_inputs
        )
    profile_by_identity = {profile.declaration.identity: profile for profile in resolution.profiles}
    assert profile_by_identity[actionable.identity].resolved_action is not None
    assert profile_by_identity[closed.identity].resolved_action is None
    assert profile_by_identity[closed.identity].declaration.no_recovery_outcome is NoRecoveryOutcome.SAFETY
