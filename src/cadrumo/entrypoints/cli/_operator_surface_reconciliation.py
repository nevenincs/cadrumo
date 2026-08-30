"""Live-surface reconciliation projected from the CommandSpec graph.

Collects the protocol-neutral inventory rows the application-owned
reconciliation consumes -- live leaves, result schemas, input schemas, mounted
families, profile policies, surface exposures and declared exclusions -- and
caches one frozen :class:`OperatorSurfaceReconciliation` per CLI invocation on
the Click context ``meta`` mapping.

See Also:
    :class:`~cadrumo.application.operator_surface.OperatorSurfaceReconciliation`
        The application-owned reconciliation this module projects into.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from ...application.operator_surface.manifest import CommandSchemaRef, ExplicitExclusionInventoryRow, InputSchemaInventoryRow, LiveLeafInventoryRow, MountedFamilyInventoryRow, OperatorSurfaceReconciliation, ProfilePolicyInventoryRow, ResultSchemaInventoryRow, SurfaceExposureInventoryRow
    from ._verb_input_schema import VerbInputSchema

__all__ = ["current_operator_surface_reconciliation"]

_OPERATOR_SURFACE_RECONCILIATION_META_KEY = "cadrumo.operator_surface_reconciliation"


@dataclass(frozen=True, slots=True)
class _CurrentOperatorSurfaceSchemaInventory:
    """Protocol-neutral projections collected from the live CLI command surface."""

    command_keys: tuple[str, ...]
    live_leaves: tuple[LiveLeafInventoryRow, ...]
    result_schemas: tuple[ResultSchemaInventoryRow, ...]
    input_rows: tuple[InputSchemaInventoryRow, ...]
    mounted_families: tuple[MountedFamilyInventoryRow, ...]
    profile_policies: tuple[ProfilePolicyInventoryRow, ...]


def _current_operator_surface_input_schemas() -> tuple[
    tuple[CommandSchemaRef, ...],
    tuple[str, ...],
    Mapping[str, VerbInputSchema],
]:
    """Collect the live result-schema and verb input-schema projections.

    A key in :data:`~._verb_input_schema.DECLARED_UNIMPLEMENTED_SURFACES` carries
    a graph-declared result schema while its verb is knowingly absent, so the live
    tree walk resolves no leaf for it and it takes part in no live
    reconciliation row. Those keys are dropped from BOTH projections here rather
    than half-dropped downstream; every OTHER divergence between the graph
    and the walk is drift and still raises.
    """
    from ._command_schema import command_schema_refs
    from ._verb_input_schema import DECLARED_UNIMPLEMENTED_SURFACES, build_verb_input_schemas

    graph_references = command_schema_refs()
    graph_keys = tuple(reference.command for reference in graph_references)
    if len(set(graph_keys)) != len(graph_keys):
        raise ValueError("current CommandSpec graph has duplicate command identities")
    schema_references = tuple(
        reference for reference in graph_references if reference.command not in DECLARED_UNIMPLEMENTED_SURFACES
    )
    command_keys = tuple(reference.command for reference in schema_references)
    input_schemas = build_verb_input_schemas(tuple(sorted(command_keys)))
    if set(input_schemas) != set(command_keys):
        raise ValueError("current input-schema projection does not exactly match the CommandSpec graph")
    return schema_references, command_keys, input_schemas


def _current_operator_surface_callback_aliases() -> dict[str, set[tuple[str, ...]]]:
    """Return aliases derived from duplicate graph result identities."""
    from ._command_specs import COMMAND_GRAPH

    paths: dict[str, list[tuple[str, ...]]] = {}
    for node in COMMAND_GRAPH.nodes():
        identity = node.spec.result_schema.identity
        if identity is not None:
            paths.setdefault(identity, []).append(node.path[1:])
    return {identity: set(rows[1:]) for identity, rows in paths.items() if len(rows) > 1}


def _current_operator_surface_primary_paths(
    input_schemas: Mapping[str, VerbInputSchema],
) -> dict[str, tuple[str, ...]]:
    """Require each verb input schema to retain its result-schema command identity."""
    primary_paths: dict[str, tuple[str, ...]] = {}
    for command_key, schema in input_schemas.items():
        resolved_leaf = schema.resolved_leaf
        if resolved_leaf.subject_leaf_key != command_key:
            raise ValueError(
                f"input-schema projection changed command identity: {command_key} -> {resolved_leaf.subject_leaf_key}",
            )
        primary_paths[command_key] = resolved_leaf.cli_path
    return primary_paths


def _current_operator_surface_schema_rows(
    *,
    schema_references: tuple[CommandSchemaRef, ...],
    command_keys: tuple[str, ...],
    input_schemas: Mapping[str, VerbInputSchema],
    callback_aliases_by_key: Mapping[str, set[tuple[str, ...]]],
    primary_paths: Mapping[str, tuple[str, ...]],
) -> _CurrentOperatorSurfaceSchemaInventory:
    """Build application-owned reconciliation rows from the verified live sources."""
    from ...application.operator_surface.contract import get_operator_surface_contract
    from ...application.operator_surface.manifest import InputSchemaInventoryRow, LiveLeafInventoryRow, MountedFamilyInventoryRow, ProfilePolicyInventoryRow, ResultSchemaInventoryRow
    from ._command_schema import command_registration_policy
    from ._command_specs import COMMAND_GRAPH

    root_landing_schema_keys = frozenset(
        identity
        for identity, spec in COMMAND_GRAPH.by_schema_identity().items()
        if spec.kind in {"root", "group"} and identity.startswith("root.")
    )

    return _CurrentOperatorSurfaceSchemaInventory(
        command_keys=command_keys,
        live_leaves=tuple(
            LiveLeafInventoryRow(
                subject_leaf_key=command_key,
                canonical_cli_path=primary_paths[command_key],
                alias_cli_paths=tuple(sorted(callback_aliases_by_key.get(command_key, set()))),
                provenance="CommandSpecGraph input-schema resolution",
            )
            for command_key in sorted(command_keys)
        ),
        result_schemas=tuple(
            ResultSchemaInventoryRow(
                subject_leaf_key=reference.command,
                schema_name=reference.schema_name,
                provenance="CommandSpecGraph through command_schema_refs",
            )
            for reference in schema_references
        ),
        input_rows=tuple(
            InputSchemaInventoryRow(
                subject_leaf_key=command_key,
                required_input_names=tuple(parameter.name for parameter in schema.required_inputs),
                provenance="VerbInputSchema.required_inputs",
            )
            for command_key, schema in sorted(input_schemas.items())
        ),
        mounted_families=tuple(
            MountedFamilyInventoryRow(
                root=family.root.value,
                child=family.child,
                provenance="OperatorSurfaceContract.command_families",
                unimplemented_reason=family.unimplemented_reason,
            )
            for family in get_operator_surface_contract().command_families
        ),
        profile_policies=tuple(
            ProfilePolicyInventoryRow(
                subject_leaf_key=command_key,
                classification=(
                    "non_profile_bound"
                    if command_key in root_landing_schema_keys
                    else (
                        "profile_bound_write"
                        if command_registration_policy(command_key).write_route == "profile-bound"
                        else "non_profile_bound"
                    )
                ),
                should_expose_externally=command_key not in root_landing_schema_keys,
                provenance="CommandSpec policy plus root landing graph classification",
            )
            for command_key in sorted(command_keys)
        ),
    )


def _current_operator_surface_schema_inventory() -> _CurrentOperatorSurfaceSchemaInventory:
    """Collect the schema, Click, family, and policy projections without inference."""
    schema_references, command_keys, input_schemas = _current_operator_surface_input_schemas()
    callback_aliases_by_key = _current_operator_surface_callback_aliases()
    primary_paths = _current_operator_surface_primary_paths(input_schemas)
    return _current_operator_surface_schema_rows(
        schema_references=schema_references,
        command_keys=command_keys,
        input_schemas=input_schemas,
        callback_aliases_by_key=callback_aliases_by_key,
        primary_paths=primary_paths,
    )


def _current_operator_surface_exposures(
    command_keys: tuple[str, ...],
) -> tuple[SurfaceExposureInventoryRow, ...]:
    """Project which registry command keys an operator surface may expose."""
    from ...application.operator_surface.manifest import SurfaceExposureInventoryRow
    from ._verb_input_schema import is_exposable_command

    return tuple(
        SurfaceExposureInventoryRow(
            subject_leaf_key=command_key,
            exposed=is_exposable_command(command_key),
            provenance="is_exposable_command",
        )
        for command_key in sorted(command_keys)
    )


def _current_operator_surface_exclusions() -> tuple[ExplicitExclusionInventoryRow, ...]:
    """Project the declared root-landing omissions into reconciliation evidence."""
    from ...application.operator_surface.manifest import ExplicitExclusionInventoryRow, ReconciliationSurface
    from ._command_specs import COMMAND_GRAPH

    root_landing_schema_keys = frozenset(
        identity
        for identity, spec in COMMAND_GRAPH.by_schema_identity().items()
        if spec.kind in {"root", "group"} and identity.startswith("root.")
    )

    return tuple(
        exclusion
        for command_key in sorted(root_landing_schema_keys)
        for exclusion in (
            ExplicitExclusionInventoryRow(
                subject_leaf_key=command_key,
                surface=ReconciliationSurface.MOUNTED_FAMILY,
                reason="root landing callback has no mounted command family",
                authority="COMMAND_GRAPH",
                provenance="CommandSpec root/group result identity",
            ),
            ExplicitExclusionInventoryRow(
                subject_leaf_key=command_key,
                surface=ReconciliationSurface.SURFACE_EXPOSURE,
                reason="root landing callback is excluded from external command surfaces",
                authority="COMMAND_GRAPH",
                provenance="CommandSpec root/group result identity",
            ),
        )
    )


def current_operator_surface_reconciliation() -> OperatorSurfaceReconciliation:
    """Return one complete live-surface reconciliation per CLI invocation.

    Click and Typer share their context ``meta`` mapping across every nested
    context in one invocation and create a new mapping for the next root
    invocation. Keeping the frozen reconciliation there lets every notice
    action in an overview batch consume the same descriptor-backed inventory
    without giving it a process-global lifetime or weakening any canonical
    resolver gate.

    Direct callers outside an active Click invocation still receive a freshly
    constructed reconciliation, preserving the live inspection semantics used
    by standalone verification code.
    """
    from ...application.operator_surface.manifest import OperatorSurfaceReconciliation, reconcile_operator_surface_inventory

    ctx = click.get_current_context(silent=True)
    if ctx is None:
        # Typer vendors Click and therefore owns a distinct context stack. The
        # real ``aeat`` dispatch runs on that stack; upstream Click remains the
        # first probe for plain-Click embedders of this boundary.
        from typer._click.globals import get_current_context as get_current_typer_context

        ctx = get_current_typer_context(silent=True)
    if ctx is not None:
        cached = ctx.meta.get(_OPERATOR_SURFACE_RECONCILIATION_META_KEY)
        if cached is not None:
            if not isinstance(cached, OperatorSurfaceReconciliation):
                raise TypeError("operator-surface reconciliation context contains an invalid value")
            return cached

    inventory = _current_operator_surface_schema_inventory()
    reconciliation = reconcile_operator_surface_inventory(
        live_leaves=inventory.live_leaves,
        result_schemas=inventory.result_schemas,
        input_schemas=inventory.input_rows,
        mounted_families=inventory.mounted_families,
        profile_policies=inventory.profile_policies,
        surface_exposures=_current_operator_surface_exposures(inventory.command_keys),
        exclusions=_current_operator_surface_exclusions(),
    )
    if ctx is not None:
        ctx.meta[_OPERATOR_SURFACE_RECONCILIATION_META_KEY] = reconciliation
    return reconciliation
