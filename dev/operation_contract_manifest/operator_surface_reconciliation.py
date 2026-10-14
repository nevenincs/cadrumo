"""Compose live operator action evidence from each command program's graph."""

from __future__ import annotations

from cadrumo.application.operator_actions.catalogue import OPERATOR_ACTION_CATALOGUE
from cadrumo.application.operator_surface.action_targets import ACTION_TARGETS, ActionTarget
from cadrumo.application.operator_surface.errors import OperatorSurfaceContractError
from cadrumo.application.operator_surface.manifest import (
    InputSchemaInventoryRow,
    LiveLeafInventoryRow,
    MountedFamilyInventoryRow,
    OperatorSurfaceReconciliation,
    ProfilePolicyInventoryRow,
    ResultSchemaInventoryRow,
    SurfaceExposureInventoryRow,
    reconcile_operator_surface_inventory,
    resolve_action_catalogue,
)
from cadrumo.entrypoints.cli.command_schema import command_registration_for_node, command_required_input_names
from cadrumo.entrypoints.cli.operator_surface_reconciliation import current_operator_surface_reconciliation
from cadrumo.entrypoints.cli.verb_input_schema import is_exposable_command_spec
from cadrumo_client.commands.graph import CommandSpecGraph
from cadrumo_client.commands.spec import NON_LEAF_COMMAND_KINDS
from cadrumo_client.contracts.command_program import CommandProgram
from cadrumo_runtime.commands.command_specs import RUNTIME_COMMAND_GRAPH


def _graph_action_target(target: ActionTarget, graph: CommandSpecGraph) -> OperatorSurfaceReconciliation:
    """Project one declared target from its actual program, schema, policy and parents."""
    if graph.root().token != target.program.executable_name:
        raise OperatorSurfaceContractError("operator_action_program", reason=f"wrong executable for {target.command_key}")
    matches = tuple(node for node in graph.nodes() if node.spec.result_schema.identity == target.command_key)
    if len(matches) != 1:
        raise OperatorSurfaceContractError(
            "operator_action_program", reason=f"missing or duplicate graph action target: {target.command_key}"
        )
    node = matches[0]
    metadata = command_registration_for_node(node, graph=graph)
    if metadata is None or metadata.cli_path is None or metadata.policy is None:
        raise OperatorSurfaceContractError("operator_action_program", reason=f"unregistered action target: {target.command_key}")
    if not node.path or node.path[0] != target.program.executable_name or metadata.cli_path != node.path[1:]:
        raise OperatorSurfaceContractError("operator_action_program", reason=f"wrong projected program path for {target.command_key}")
    path = metadata.cli_path
    if len(path) < 2:
        raise OperatorSurfaceContractError("operator_action_program", reason=f"unmounted action target: {target.command_key}")
    parent = graph.resolve_path(node.path[:2])
    family = graph.resolve_path(node.path[:3])
    if parent.kind not in NON_LEAF_COMMAND_KINDS or family.kind not in NON_LEAF_COMMAND_KINDS or family.parent_key != parent.key:
        raise OperatorSurfaceContractError("operator_action_program", reason=f"invalid mounted parents for {target.command_key}")
    provenance = f"{target.program.executable_name} CommandSpecGraph metadata"
    root_landing = node.spec.kind in NON_LEAF_COMMAND_KINDS and metadata.command.startswith("root.")
    return reconcile_operator_surface_inventory(
        live_leaves=(LiveLeafInventoryRow(
            subject_leaf_key=metadata.command, canonical_cli_path=path, program=target.program, provenance=provenance
        ),),
        result_schemas=(ResultSchemaInventoryRow(
            subject_leaf_key=metadata.command, schema_name=metadata.schema_name, provenance=provenance
        ),),
        input_schemas=(InputSchemaInventoryRow(
            subject_leaf_key=metadata.command, required_input_names=command_required_input_names(node.spec), provenance=provenance
        ),),
        mounted_families=(MountedFamilyInventoryRow(root=parent.token, child=family.token, provenance=provenance),),
        profile_policies=(ProfilePolicyInventoryRow(
            subject_leaf_key=metadata.command,
            classification="profile_bound_write" if not root_landing and metadata.policy.write_route == "profile-bound" else "non_profile_bound",
            should_expose_externally=not root_landing,
            provenance=provenance,
        ),),
        surface_exposures=(SurfaceExposureInventoryRow(
            subject_leaf_key=metadata.command, exposed=is_exposable_command_spec(node.spec), provenance=provenance
        ),),
    )


def current_program_action_reconciliation() -> OperatorSurfaceReconciliation:
    """Prove every canonical action target using its owning live command program.

    Tax supplies its complete existing reconciliation. Authentication supplies
    the catalogue targets that its live graph owns; recorded targets only state
    the claims checked against those projections, never supply live evidence.
    """
    leaves = list(current_operator_surface_reconciliation().leaves)
    graphs = {CommandProgram.AUTHENTICATION: RUNTIME_COMMAND_GRAPH}
    for target in ACTION_TARGETS:
        if target.program is not CommandProgram.AEAT:
            leaves.extend(_graph_action_target(target, graphs[target.program]).leaves)
    reconciliation = OperatorSurfaceReconciliation(leaves=tuple(leaves))
    # This existing join retains missing/duplicate identities, path ambiguity,
    # required-input sufficiency and exposure/result/input accounting controls.
    resolve_action_catalogue(catalogue=OPERATOR_ACTION_CATALOGUE, reconciliation=reconciliation)
    live_by_key = {leaf.live_leaf.subject_leaf_key: leaf for leaf in reconciliation.leaves}
    for target in ACTION_TARGETS:
        leaf = live_by_key.get(target.command_key)
        if leaf is None or ActionTarget.of_leaf(leaf) != target:
            raise OperatorSurfaceContractError(
                "operator_action_program", reason=f"recorded action target differs from live program evidence: {target.command_key}"
            )
    return reconciliation


__all__ = ["current_program_action_reconciliation"]
