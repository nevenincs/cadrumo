"""MCP action capabilities projected onto the CLI's per-verb input schemas.

``cadrumo`` is the CLI implementation, not an MCP facade: it owns the click-tree
projection (:class:`~cadrumo.entrypoints.cli.VerbInputSchema` and
:func:`~cadrumo.entrypoints.cli.build_verb_input_schemas`) and nothing about this
protocol. Everything that makes those schemas an MCP surface -- the capability
DTO, the capability-bearing schema, the resolver that binds catalogue actions to
live verbs, and the ``x-cadrumo-action-capabilities`` JSON-Schema extension --
lives here in the harness that serves them.

:class:`McpVerbInputSchema` extends the CLI's schema rather than replacing it, so
the parameter projection has exactly one home and this module adds only the
capability axis on top.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, override

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from cadrumo.application.operator_actions.catalogue import (
    OPERATOR_ACTION_CATALOGUE,
    ActionArgumentBindingSpecification,
    ActionCatalogue,
)
from cadrumo.application.operator_surface.manifest import (
    CommandSchemaRef,
    InputSchemaInventoryRow,
    LiveLeafInventoryRow,
    OperatorSurfaceReconciliation,
    ReconciledOperatorLeaf,
    ResultSchemaInventoryRow,
    resolve_action_catalogue,
)
from cadrumo.entrypoints.cli.command_api import (
    DECLARED_UNIMPLEMENTED_SURFACES,
    VerbInputSchema,
    build_verb_input_schemas,
)

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")
_ACTION_CAPABILITIES_SCHEMA_KEY = "x-cadrumo-action-capabilities"


class McpActionCapability(BaseModel):
    """One canonical action capability projected onto its target MCP tool.

    The application action catalogue remains the declaration authority and the
    shared operator-surface resolver remains the live-schema authority.  This
    DTO carries only their resolution evidence: the stable action and target
    identities, the resolved Click path, the complete required-input names,
    and the catalogue's argument-source specifications.  It contains no
    applicability predicate, runtime argument value, localized prose, or CLI
    command string.
    """

    model_config = _STRICT_FROZEN

    action_id: str = Field(min_length=1)
    target_command_key: str = Field(min_length=1)
    cli_path: tuple[str, ...]
    required_input_names: tuple[str, ...] = ()
    argument_specifications: tuple[ActionArgumentBindingSpecification, ...] = ()

    @field_validator("required_input_names")
    @classmethod
    def _required_inputs_are_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("MCP action capability required input names must be unique")
        return value


class McpVerbInputSchema(VerbInputSchema):
    """A live verb schema carrying the actions the MCP surface projects onto it.

    The CLI's own schema is the parameter authority; this adds the capability
    axis and the JSON-Schema extension that publishes it, so a verb's click
    projection stays identical whether or not it is served over MCP.
    """

    action_capabilities: tuple[McpActionCapability, ...] = ()

    @field_validator("action_capabilities")
    @classmethod
    def _action_ids_are_unique_and_ordered(
        cls,
        value: tuple[McpActionCapability, ...],
    ) -> tuple[McpActionCapability, ...]:
        action_ids = tuple(capability.action_id for capability in value)
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("MCP action capability IDs must be unique per target command")
        return tuple(sorted(value, key=lambda capability: capability.action_id))

    @model_validator(mode="after")
    def _capabilities_target_this_live_schema(self) -> VerbInputSchema:
        required_input_names = tuple(parameter.name for parameter in self.required_inputs)
        for capability in self.action_capabilities:
            if capability.target_command_key != self.command_key:
                raise ValueError(
                    f"MCP action capability target mismatch: schema={self.command_key}, "
                    f"action={capability.action_id}, target={capability.target_command_key}"
                )
            if capability.cli_path != self.cli_path:
                raise ValueError(
                    f"MCP action capability Click-path mismatch for {capability.action_id}: "
                    f"schema={' '.join(self.cli_path)}, action={' '.join(capability.cli_path)}"
                )
            if capability.required_input_names != required_input_names:
                raise ValueError(
                    f"MCP action capability required-input mismatch for {capability.action_id}: "
                    f"schema={required_input_names}, action={capability.required_input_names}"
                )
        return self

    @override
    def json_schema(self) -> dict[str, Any]:
        """Return the CLI projection plus the capability extension."""
        schema = super().json_schema()
        if self.action_capabilities:
            schema[_ACTION_CAPABILITIES_SCHEMA_KEY] = [
                capability.model_dump(mode="json") for capability in self.action_capabilities
            ]
        return schema


def resolve_mcp_action_capabilities(
    *,
    catalogue: ActionCatalogue,
    command_schemas: tuple[CommandSchemaRef, ...],
    verb_schemas: Mapping[str, VerbInputSchema],
) -> dict[str, tuple[McpActionCapability, ...]]:
    """Resolve catalogue actions through the shared live-surface resolver.

    ``command_schemas`` and ``verb_schemas`` must describe the same already
    MCP-exposed command-key set.  The function builds only the pure inventory
    rows accepted by :func:`resolve_action_catalogue`; it does not claim a
    profile-policy, mounted-family, or applicability projection.  Any stale
    result/input identity, ambiguous Click path, orphan target, or insufficient
    argument source fails in the shared resolver before an MCP capability is
    emitted.
    """
    schema_ref_by_key: dict[str, CommandSchemaRef] = {}
    for schema_ref in command_schemas:
        if schema_ref.command in schema_ref_by_key:
            raise ValueError(f"duplicate MCP result-schema identity: {schema_ref.command}")
        schema_ref_by_key[schema_ref.command] = schema_ref

    # A declared-unimplemented surface has a result schema and, by construction,
    # no input schema: there is no verb to read parameters from. Excluding it
    # here is the same declaration honoured a second time rather than a second
    # exemption -- were it demanded, the build would still fail on the very keys
    # the declaration exists to hold open, and the gap would have to be hidden
    # by deleting the result schema, which is the outcome it prevents.
    result_keys = frozenset(schema_ref_by_key) - frozenset(DECLARED_UNIMPLEMENTED_SURFACES)
    input_keys = frozenset(verb_schemas)
    if result_keys != input_keys:
        missing_input = tuple(sorted(result_keys - input_keys))
        missing_result = tuple(sorted(input_keys - result_keys))
        raise ValueError(
            "MCP action projection requires an exact result/input schema join; "
            f"missing input schemas={missing_input}, missing result schemas={missing_result}"
        )
    for command_key, verb_schema in verb_schemas.items():
        if verb_schema.command_key != command_key:
            raise ValueError(
                f"MCP input-schema identity mismatch: mapping={command_key}, schema={verb_schema.command_key}"
            )

    reconciliation = OperatorSurfaceReconciliation(
        leaves=tuple(
            ReconciledOperatorLeaf(
                live_leaf=LiveLeafInventoryRow(
                    subject_leaf_key=command_key,
                    canonical_cli_path=verb_schema.resolved_leaf.cli_path,
                    alias_cli_paths=verb_schema.resolved_leaf.alias_paths,
                    provenance="MCP production Click input-schema projection",
                ),
                result_schema=ResultSchemaInventoryRow(
                    subject_leaf_key=command_key,
                    schema_name=schema_ref_by_key[command_key].schema_name,
                    provenance="MCP production graph result-schema projection",
                ),
                input_schema=InputSchemaInventoryRow(
                    subject_leaf_key=command_key,
                    required_input_names=tuple(parameter.name for parameter in verb_schema.required_inputs),
                    provenance="MCP production Click required-input projection",
                ),
                mounted_family=None,
                profile_policy=None,
                surface_exposure=None,
                exclusions=(),
            )
            for command_key, verb_schema in sorted(verb_schemas.items())
        )
    )
    resolved_actions = resolve_action_catalogue(
        catalogue=catalogue,
        reconciliation=reconciliation,
    )

    capabilities_by_target: dict[str, list[McpActionCapability]] = {}
    for resolved_action in resolved_actions:
        input_schema = resolved_action.target_leaf.input_schema
        if input_schema is None:
            raise ValueError(f"resolved MCP action target lacks input-schema evidence: {resolved_action.action_id}")
        capability = McpActionCapability(
            action_id=resolved_action.action_id,
            target_command_key=resolved_action.target_command_key,
            cli_path=resolved_action.target_leaf.live_leaf.canonical_cli_path,
            required_input_names=input_schema.required_input_names,
            argument_specifications=resolved_action.declaration.argument_specifications,
        )
        capabilities_by_target.setdefault(capability.target_command_key, []).append(capability)

    return {
        target_key: tuple(sorted(capabilities, key=lambda capability: capability.action_id))
        for target_key, capabilities in sorted(capabilities_by_target.items())
    }


def build_mcp_action_input_schemas(
    command_schemas: tuple[CommandSchemaRef, ...],
    *,
    catalogue: ActionCatalogue = OPERATOR_ACTION_CATALOGUE,
) -> dict[str, McpVerbInputSchema]:
    """Build live MCP input schemas enriched by resolver-backed capabilities."""
    verb_schemas = build_verb_input_schemas(tuple(schema_ref.command for schema_ref in command_schemas))
    capabilities_by_target = resolve_mcp_action_capabilities(
        catalogue=catalogue,
        command_schemas=command_schemas,
        verb_schemas=verb_schemas,
    )
    return {
        command_key: McpVerbInputSchema(
            **{field_name: getattr(verb_schema, field_name) for field_name in VerbInputSchema.model_fields},
            action_capabilities=capabilities_by_target.get(command_key, ()),
        )
        for command_key, verb_schema in verb_schemas.items()
    }


__all__ = [
    "McpActionCapability",
    "McpVerbInputSchema",
    "build_mcp_action_input_schemas",
    "resolve_mcp_action_capabilities",
]
