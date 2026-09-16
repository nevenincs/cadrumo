"""Live-surface reconciliation projected from the CommandSpec graph.

Collects the protocol-neutral inventory rows the application-owned
reconciliation consumes -- live leaves, result schemas, input schemas, mounted
families, profile policies, surface exposures and declared exclusions -- and
caches one frozen :class:`OperatorSurfaceReconciliation` per CLI invocation on
the Click context ``meta`` mapping. A single action target is reconciled from
the same row projections without loading the command families it cannot reach.

See Also:
    :class:`~cadrumo.application.operator_surface.OperatorSurfaceReconciliation`
        The application-owned reconciliation this module projects into.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

import click

from .command_spec import NON_LEAF_COMMAND_KINDS

if TYPE_CHECKING:
    from ...application.operator_surface.command_ports import VerbInputSchema
    from ...application.operator_surface.manifest import (
        CommandSchemaRef,
        ExplicitExclusionInventoryRow,
        InputSchemaInventoryRow,
        LiveLeafInventoryRow,
        MountedFamilyInventoryRow,
        OperatorSurfaceReconciliation,
        ProfilePolicyInventoryRow,
        ResultSchemaInventoryRow,
        SurfaceExposureInventoryRow,
    )
    from .command_spec import CommandSpec, CommandSpecNode

__all__ = ["current_operator_surface_reconciliation", "operator_surface_target_reconciliation"]

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
    """Collect the live result-schema and verb input-schema projections."""
    from .command_schema import command_schema_refs
    from .verb_input_schema import build_verb_input_schemas

    graph_references = command_schema_refs()
    graph_keys = tuple(reference.command for reference in graph_references)
    if len(set(graph_keys)) != len(graph_keys):
        raise ValueError("current CommandSpec graph has duplicate command identities")
    schema_references = graph_references
    command_keys = tuple(reference.command for reference in schema_references)
    input_schemas = build_verb_input_schemas(tuple(sorted(command_keys)))
    if set(input_schemas) != set(command_keys):
        raise ValueError("current input-schema projection does not exactly match the CommandSpec graph")
    return schema_references, command_keys, input_schemas


def _current_operator_surface_callback_aliases() -> dict[str, set[tuple[str, ...]]]:
    """Return aliases derived from duplicate graph result identities."""
    from .command_specs import COMMAND_GRAPH

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


def _current_operator_surface_root_landing_schema_keys() -> frozenset[str]:
    """Return root/group result identities excluded from mounted leaf families."""
    from .command_specs import COMMAND_GRAPH

    return frozenset(
        identity for identity, spec in COMMAND_GRAPH.by_schema_identity().items() if _is_root_landing(identity, spec)
    )


def _is_root_landing(command_key: str, spec: CommandSpec) -> bool:
    """Return whether a result identity names a root/group landing callback."""
    return spec.kind in NON_LEAF_COMMAND_KINDS and command_key.startswith("root.")


def _current_operator_surface_live_leaf_rows(
    command_keys: tuple[str, ...],
    callback_aliases_by_key: Mapping[str, set[tuple[str, ...]]],
    primary_paths: Mapping[str, tuple[str, ...]],
) -> tuple[LiveLeafInventoryRow, ...]:
    """Project live command identities and their canonical callback paths."""
    return tuple(
        _live_leaf_row(
            command_key,
            canonical_cli_path=primary_paths[command_key],
            alias_cli_paths=callback_aliases_by_key.get(command_key, set()),
        )
        for command_key in sorted(command_keys)
    )


def _live_leaf_row(
    command_key: str,
    *,
    canonical_cli_path: tuple[str, ...],
    alias_cli_paths: set[tuple[str, ...]],
) -> LiveLeafInventoryRow:
    """Project one live command identity and its canonical callback path."""
    from ...application.operator_surface.manifest import LiveLeafInventoryRow

    return LiveLeafInventoryRow(
        subject_leaf_key=command_key,
        canonical_cli_path=canonical_cli_path,
        alias_cli_paths=tuple(sorted(alias_cli_paths)),
        provenance="CommandSpecGraph input-schema resolution",
    )


def _current_operator_surface_result_schema_rows(
    schema_references: tuple[CommandSchemaRef, ...],
) -> tuple[ResultSchemaInventoryRow, ...]:
    """Project each CommandSpec result-schema reference without inference."""
    return tuple(_result_schema_row(reference.command, reference.schema_name) for reference in schema_references)


def _result_schema_row(command_key: str, schema_name: str) -> ResultSchemaInventoryRow:
    """Project one CommandSpec result-schema reference without inference."""
    from ...application.operator_surface.manifest import ResultSchemaInventoryRow

    return ResultSchemaInventoryRow(
        subject_leaf_key=command_key,
        schema_name=schema_name,
        provenance="CommandSpecGraph through command_schema_refs",
    )


def _current_operator_surface_input_schema_rows(
    input_schemas: Mapping[str, VerbInputSchema],
) -> tuple[InputSchemaInventoryRow, ...]:
    """Project required input names from each verified verb input schema."""
    return tuple(
        _input_schema_row(command_key, tuple(parameter.name for parameter in schema.required_inputs))
        for command_key, schema in sorted(input_schemas.items())
    )


def _input_schema_row(command_key: str, required_input_names: tuple[str, ...]) -> InputSchemaInventoryRow:
    """Project one command's required input names."""
    from ...application.operator_surface.manifest import InputSchemaInventoryRow

    return InputSchemaInventoryRow(
        subject_leaf_key=command_key,
        required_input_names=required_input_names,
        provenance="VerbInputSchema.required_inputs",
    )


def _current_operator_surface_mounted_family_rows() -> tuple[MountedFamilyInventoryRow, ...]:
    """Project the application-owned mounted command-family contract."""
    from ...application.operator_surface.contract import get_operator_surface_contract
    from ...application.operator_surface.manifest import MountedFamilyInventoryRow

    return tuple(
        MountedFamilyInventoryRow(
            root=family.root.value,
            child=family.child,
            provenance="OperatorSurfaceContract.command_families",
        )
        for family in get_operator_surface_contract().command_families
    )


def _current_operator_surface_profile_policy_rows(
    command_keys: tuple[str, ...],
    root_landing_schema_keys: frozenset[str],
) -> tuple[ProfilePolicyInventoryRow, ...]:
    """Project graph/policy profile classification and external exposure."""
    from .command_schema import command_registration_policy

    return tuple(
        _profile_policy_row(
            command_key,
            root_landing=command_key in root_landing_schema_keys,
            write_route=command_registration_policy(command_key).write_route,
        )
        for command_key in sorted(command_keys)
    )


def _profile_policy_row(command_key: str, *, root_landing: bool, write_route: str) -> ProfilePolicyInventoryRow:
    """Classify one command from the graph root landing and write-route policy."""
    from ...application.operator_surface.manifest import ProfilePolicyInventoryRow

    return ProfilePolicyInventoryRow(
        subject_leaf_key=command_key,
        classification=(
            "profile_bound_write" if not root_landing and write_route == "profile-bound" else "non_profile_bound"
        ),
        should_expose_externally=not root_landing,
        provenance="CommandSpec policy plus root landing graph classification",
    )


def _current_operator_surface_schema_rows(
    *,
    schema_references: tuple[CommandSchemaRef, ...],
    command_keys: tuple[str, ...],
    input_schemas: Mapping[str, VerbInputSchema],
    callback_aliases_by_key: Mapping[str, set[tuple[str, ...]]],
    primary_paths: Mapping[str, tuple[str, ...]],
) -> _CurrentOperatorSurfaceSchemaInventory:
    """Build application-owned reconciliation rows from the verified live sources."""
    root_landing_schema_keys = _current_operator_surface_root_landing_schema_keys()

    return _CurrentOperatorSurfaceSchemaInventory(
        command_keys=command_keys,
        live_leaves=_current_operator_surface_live_leaf_rows(
            command_keys,
            callback_aliases_by_key,
            primary_paths,
        ),
        result_schemas=_current_operator_surface_result_schema_rows(
            schema_references,
        ),
        input_rows=_current_operator_surface_input_schema_rows(
            input_schemas,
        ),
        mounted_families=_current_operator_surface_mounted_family_rows(),
        profile_policies=_current_operator_surface_profile_policy_rows(
            command_keys,
            root_landing_schema_keys,
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
    from .verb_input_schema import is_exposable_command

    return tuple(
        _surface_exposure_row(command_key, exposed=is_exposable_command(command_key))
        for command_key in sorted(command_keys)
    )


def _surface_exposure_row(command_key: str, *, exposed: bool) -> SurfaceExposureInventoryRow:
    """Project whether one command key may be exposed by an operator surface."""
    from ...application.operator_surface.manifest import SurfaceExposureInventoryRow

    return SurfaceExposureInventoryRow(
        subject_leaf_key=command_key,
        exposed=exposed,
        provenance="is_exposable_command",
    )


def _current_operator_surface_exclusions() -> tuple[ExplicitExclusionInventoryRow, ...]:
    """Project the declared root-landing omissions into reconciliation evidence."""
    return _root_landing_exclusions(tuple(sorted(_current_operator_surface_root_landing_schema_keys())))


def _root_landing_exclusions(command_keys: tuple[str, ...]) -> tuple[ExplicitExclusionInventoryRow, ...]:
    """Project root-landing omissions for ``command_keys`` into reconciliation evidence."""
    from ...application.operator_surface.manifest import ExplicitExclusionInventoryRow, ReconciliationSurface

    return tuple(
        exclusion
        for command_key in command_keys
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
    from ...application.operator_surface.manifest import (
        OperatorSurfaceReconciliation,
        reconcile_operator_surface_inventory,
    )

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


def _operator_surface_target_node(command_key: str) -> CommandSpecNode:
    """Find the graph node that owns ``command_key``, loading only the families searched."""
    from .command_specs import COMMAND_GRAPH

    node = COMMAND_GRAPH.find_schema_identity(command_key)
    if node is None:
        raise LookupError(f"unknown command schema identity: {command_key}")
    return node


def operator_surface_target_reconciliation(command_key: str) -> OperatorSurfaceReconciliation:
    """Reconcile the one live leaf that owns ``command_key``.

    The rows are the projections :func:`current_operator_surface_reconciliation`
    joins for that leaf, validated by the same application reconciler, so an
    action resolved here carries the identical target. Only the families on the
    search path to the target are loaded; completeness of the whole surface
    remains the concern of the full reconciliation.
    """
    from ...application.operator_surface.manifest import reconcile_operator_surface_inventory
    from .command_schema import command_required_input_names
    from .verb_input_schema import is_exposable_command_spec

    node = _operator_surface_target_node(command_key)
    spec = node.spec
    target = spec.result_schema.target
    if target is None:
        raise LookupError(f"command schema identity has no result-schema target: {command_key}")
    canonical_cli_path = node.path[1:]
    root_landing = _is_root_landing(command_key, spec)
    return reconcile_operator_surface_inventory(
        live_leaves=(_live_leaf_row(command_key, canonical_cli_path=canonical_cli_path, alias_cli_paths=set()),),
        result_schemas=(_result_schema_row(command_key, target.qualname),),
        input_schemas=(_input_schema_row(command_key, command_required_input_names(spec)),),
        mounted_families=tuple(
            family
            for family in _current_operator_surface_mounted_family_rows()
            if family.identity == canonical_cli_path[:2]
        ),
        profile_policies=(
            _profile_policy_row(command_key, root_landing=root_landing, write_route=spec.policy.write_route),
        ),
        surface_exposures=(_surface_exposure_row(command_key, exposed=is_exposable_command_spec(spec)),),
        exclusions=_root_landing_exclusions((command_key,) if root_landing else ()),
    )
