"""Operator projections of the sole immutable :class:`CommandSpecGraph`.

Core types:
:class:`~cadrumo.core.json_contract.OutputSchema`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from functools import cache
from types import MappingProxyType
from typing import TYPE_CHECKING, cast

from cadrumo_client.commands.parameters import OptionSpec
from cadrumo_client.commands.shared_contracts import DefaultKind, SchemaState
from cadrumo_client.commands.target import resolve_deferred_target
from cadrumo_client.contracts.command_ports import (
    CommandCapabilityClass,
    CommandNodeKind,
    CommandParameterDefault,
    CommandParameterMetadata,
    CommandPolicyMetadata,
    CommandRegistrationMetadata,
    JsonType,
    MachineSecretFieldMetadata,
    MachineSecretPayloadMetadata,
    MachineSecretVariantConditionMetadata,
    ProfileAuthenticationContractMetadata,
)

from ...core.errors.hierarchy import InternalInvariantError
from ...core.i18n.render import output_language, tr
from ...core.type_guards import is_object_list_or_tuple

if TYPE_CHECKING:
    from cadrumo_client.commands.graph import CommandSpecGraph
    from cadrumo_client.commands.parameters import ParameterSpec
    from cadrumo_client.commands.spec import CommandSpec, CommandSpecNode

    from ...application.operator_surface.manifest import CommandSchemaRef
    from ...core.json_contract import RegisteredSchema
    from ._command_policy import CommandExecutionPolicy


def machine_secret_payload_metadata(spec: CommandSpec) -> tuple[MachineSecretPayloadMetadata, ...]:
    """Project value-free secret shapes directly from their owning command spec."""
    from cadrumo_client.commands.secure_input import MACHINE_SECRET_MAX_BYTES

    contract = spec.machine_secret
    if contract is None:
        return ()
    return tuple(
        MachineSecretPayloadMetadata(
            variant.key,
            tuple(MachineSecretFieldMetadata(field.name, field.json_type) for field in variant.fields),
            MachineSecretVariantConditionMetadata(variant.condition.option_name, variant.condition.presence)
            if variant.condition is not None
            else None,
            MACHINE_SECRET_MAX_BYTES,
            True,
            True,
            True,
        )
        for variant in contract.variants
    )


@dataclass(frozen=True, slots=True)
class LiveNodeRegistrationMetadata:
    """One executable CLI node projected without importing its handler."""

    path: tuple[str, ...]
    kind: CommandNodeKind
    loader_owner: str | None
    handler_owner: str
    source_sha256: str | None
    policy: CommandPolicyMetadata | None


@dataclass(frozen=True, slots=True)
class CommandRegistrationProjection:
    """Complete command and node metadata projected from the canonical graph."""

    commands: tuple[CommandRegistrationMetadata, ...]
    nodes: tuple[LiveNodeRegistrationMetadata, ...]
    profile_authentication_contract: ProfileAuthenticationContractMetadata


def _policy(spec: CommandSpec) -> CommandPolicyMetadata:
    value = spec.policy
    return CommandPolicyMetadata(
        value.capabilities,
        value.side_effects,
        value.performance,
        value.write_route,
        value.destructive,
        value.handoff,
        value.live_write,
    )


def _json_type(parameter: ParameterSpec) -> JsonType:
    qualname = parameter.value.annotation.qualname
    return (
        JsonType.INTEGER
        if qualname == "int"
        else JsonType.NUMBER
        if qualname == "float"
        else JsonType.BOOLEAN
        if qualname == "bool"
        else JsonType.STRING
    )


def _choices(parameter: ParameterSpec) -> tuple[str, ...]:
    if parameter.value.choices:
        return parameter.value.choices
    target = parameter.value.click_type or parameter.value.annotation
    try:
        value = resolve_deferred_target(target)
    except (ImportError, AttributeError, InternalInvariantError):
        return ()
    if isinstance(value, type) and issubclass(value, Enum):
        return tuple(str(member.value) for member in value)
    # The Enum branch above leaves a partially-narrowed `type[Unknown]` in the
    # negative arm; restate the plain object the remaining lookup runs against.
    resolved = cast("object", value)
    # A click type's ``choices`` is whatever the type declares; only a real
    # sequence of tokens is a choice set.
    declared: object = getattr(resolved, "choices", ())
    if not is_object_list_or_tuple(declared):
        return ()
    return tuple(str(choice) for choice in declared)


def parameter_is_required(parameter: ParameterSpec) -> bool:
    """Return whether a caller must supply ``parameter`` to invoke its command."""
    return parameter.default.kind is DefaultKind.REQUIRED


def operator_parameters(spec: CommandSpec) -> tuple[ParameterSpec, ...]:
    """Return the parameters a command exposes to operators, in declared order."""
    return tuple(parameter for parameter in spec.parameters if not parameter.hidden)


def command_required_input_names(spec: CommandSpec) -> tuple[str, ...]:
    """Return the operator input names ``spec`` requires, in declared order."""
    return tuple(parameter.name for parameter in operator_parameters(spec) if parameter_is_required(parameter))


def _parameter(parameter: ParameterSpec) -> CommandParameterMetadata:
    cli_flag, off_flag = _parameter_flags(parameter)
    json_type = _json_type(parameter)
    return CommandParameterMetadata(
        parameter.name,
        parameter.kind,
        cli_flag,
        off_flag,
        json_type,
        parameter_is_required(parameter),
        isinstance(parameter, OptionSpec) and (parameter.is_flag or json_type == "boolean"),
        isinstance(parameter, OptionSpec) and parameter.multiple,
        _choices(parameter),
        cast(
            "CommandParameterDefault",
            parameter.default.literal if parameter.default.kind is DefaultKind.LITERAL else None,
        ),
        "" if parameter.help_key is None else tr(parameter.help_key.value),
    )


def _parameter_flags(parameter: ParameterSpec) -> tuple[str, str]:
    """Project the positive and negative long flags from an option declaration."""
    declarations = parameter.declarations if isinstance(parameter, OptionSpec) else ()
    return (
        next((token for token in declarations if token.startswith("--") and not token.startswith("--no-")), ""),
        next((token for token in declarations if token.startswith("--no-")), ""),
    )


def _operator_path(path: tuple[str, ...], *, root_segment: str = "aeat") -> tuple[str, ...]:
    return path[1:] if path and path[0] == root_segment else path


def command_registration_projection(
    graph: CommandSpecGraph | None = None,
) -> CommandRegistrationProjection:
    """Project one command graph in the currently selected output language.

    With no graph, this projects the AEAT command surface. A caller composing
    another frontend can supply its graph without coupling this projector to
    that frontend's host or command package.
    """
    if graph is None:
        from .command_specs import COMMAND_GRAPH

        graph = COMMAND_GRAPH
    return _command_registration_projection(output_language(), graph)


def _handler_owner(spec: CommandSpec) -> str | None:
    """Return the authored handler identity when a node has executable ownership."""
    if spec.handler is None or spec.handler.target is None:
        return None
    return spec.handler.target.identity


def _live_node_registration_metadata(
    node: CommandSpecNode,
    *,
    path: tuple[str, ...],
    policy: CommandPolicyMetadata,
    owner: str | None,
) -> LiveNodeRegistrationMetadata:
    """Project one graph node into the live-node registration inventory."""
    return LiveNodeRegistrationMetadata(path, node.spec.kind, None, owner or "<metadata>", None, policy)


def _target_command_registration_metadata(
    node: CommandSpecNode,
    *,
    language: str,
    path: tuple[str, ...],
    policy: CommandPolicyMetadata,
    owner: str | None,
) -> CommandRegistrationMetadata | None:
    """Project a target result schema into :class:`CommandRegistrationMetadata`, if exposed."""
    from ._profile_authentication_contract import profile_authentication_posture

    spec = node.spec
    schema = spec.result_schema
    if schema.state is not SchemaState.TARGET or schema.identity is None or schema.target is None:
        return None
    parameters = tuple(_parameter(parameter) for parameter in operator_parameters(spec))
    return CommandRegistrationMetadata(
        schema.identity,
        schema.target.qualname,
        schema.target.identity,
        "",
        path,
        ((language, parameters),),
        ((language, tr(spec.help_key.value)),),
        spec.invocation.hidden,
        policy,
        owner,
        None,
        machine_secret_payload_metadata(spec),
        profile_authentication_posture(node),
    )


def profile_authentication_contract(
    graph: CommandSpecGraph | None = None,
) -> ProfileAuthenticationContractMetadata:
    """Project the root profile-secret shape without exposing any secret value."""
    from cadrumo_client.commands.secure_input import MACHINE_SECRET_MAX_BYTES

    if graph is None:
        from .command_specs import COMMAND_GRAPH

        graph = COMMAND_GRAPH
    root_profile_secret = graph.root().profile_secret
    if root_profile_secret is None:
        raise InternalInvariantError("root command spec must declare profile-secret metadata authority")
    return ProfileAuthenticationContractMetadata(
        fields=tuple(MachineSecretFieldMetadata(field.name, field.json_type) for field in root_profile_secret.fields),
        maximum_bytes=MACHINE_SECRET_MAX_BYTES,
        same_scope_exclusive=True,
        stdin_exclusive_across_scopes=True,
        descriptors_must_differ_across_scopes=True,
        duplicate_keys_forbidden=True,
        extra_fields_forbidden=True,
    )


_projection_cache: dict[tuple[str, int], tuple[object, CommandRegistrationProjection]] = {}


def _command_registration_projection(
    language: str,
    graph: CommandSpecGraph,
) -> CommandRegistrationProjection:
    cache_key = (language, id(graph))
    cached = _projection_cache.get(cache_key)
    if cached is not None and cached[0] is graph:
        return cached[1]

    contract = profile_authentication_contract(graph)
    commands: list[CommandRegistrationMetadata] = []
    nodes: list[LiveNodeRegistrationMetadata] = []
    root_segment = graph.root().token
    for node in graph.nodes():
        spec = node.spec
        path = _operator_path(node.path, root_segment=root_segment)
        owner = _handler_owner(spec)
        policy = _policy(spec)
        nodes.append(
            _live_node_registration_metadata(
                node,
                path=path,
                policy=policy,
                owner=owner,
            )
        )
        command = _target_command_registration_metadata(
            node,
            language=language,
            path=path,
            policy=policy,
            owner=owner,
        )
        if command is not None:
            commands.append(command)
    projection = CommandRegistrationProjection(
        tuple(sorted(commands, key=lambda row: row.command)),
        tuple(nodes),
        contract,
    )
    _projection_cache[cache_key] = (graph, projection)
    return projection


def command_registration_for_node(
    node: CommandSpecNode,
    *,
    graph: CommandSpecGraph | None = None,
) -> CommandRegistrationMetadata | None:
    """Project one graph node into :class:`CommandRegistrationMetadata` in the output language, if exposed."""
    spec = node.spec
    return _target_command_registration_metadata(
        node,
        language=output_language(),
        path=_operator_path(node.path, root_segment="aeat" if graph is None else graph.root().token),
        policy=_policy(spec),
        owner=_handler_owner(spec),
    )


def command_registration_metadata() -> tuple[CommandRegistrationMetadata, ...]:
    """Return deterministic metadata for every executable command."""
    return command_registration_projection().commands


@cache
def command_registration_policy(command: str) -> CommandExecutionPolicy:
    """Return the execution policy declared for ``command``."""
    from ._command_policy import CommandExecutionPolicy
    from .command_specs import COMMAND_GRAPH

    spec = COMMAND_GRAPH.by_schema_identity().get(command)
    if spec is None:
        raise LookupError(f"unknown command schema identity: {command}")
    value = spec.policy
    return CommandExecutionPolicy(
        CommandCapabilityClass(value.capabilities, value.side_effects, value.performance),
        value.write_route,
        value.destructive,
        value.handoff,
        value.live_write,
    )


@cache
def command_schema_refs() -> tuple[CommandSchemaRef, ...]:
    """Return registered result-schema references for executable commands."""
    from ...application.operator_surface.manifest import CommandSchemaRef
    from .command_specs import COMMAND_GRAPH

    return tuple(
        CommandSchemaRef(command=identity, schema_name=spec.result_schema.target.qualname)
        for identity, spec in sorted(COMMAND_GRAPH.by_schema_identity().items())
        if spec.result_schema.target is not None
    )


@cache
def command_schema_type(command: str) -> RegisteredSchema:
    """Resolve the authored result-schema target for one command identity."""
    from cadrumo_client.commands.target import resolve_deferred_target

    from .command_specs import COMMAND_GRAPH

    spec = COMMAND_GRAPH.by_schema_identity().get(command)
    if spec is None or spec.result_schema.target is None:
        raise LookupError(f"unknown command schema identity: {command}")
    target = resolve_deferred_target(spec.result_schema.target)
    if not isinstance(target, type):
        raise TypeError(f"command schema target is not a type: {command}")
    from ...core.json_contract import OutputRootSchema, OutputSchema

    if not issubclass(target, OutputSchema | OutputRootSchema):
        raise TypeError(f"command schema target is not an output schema: {command}")
    return cast("type[OutputSchema] | type[OutputRootSchema[object]]", target)


@cache
def command_schema_types() -> Mapping[str, RegisteredSchema]:
    """Return the immutable graph-derived result-schema type projection."""
    from .command_specs import COMMAND_GRAPH

    return MappingProxyType(
        {identity: command_schema_type(identity) for identity in COMMAND_GRAPH.by_schema_identity()}
    )


__all__ = [
    "CommandCapabilityClass",
    "CommandParameterMetadata",
    "CommandPolicyMetadata",
    "CommandRegistrationMetadata",
    "CommandRegistrationProjection",
    "LiveNodeRegistrationMetadata",
    "MachineSecretFieldMetadata",
    "MachineSecretPayloadMetadata",
    "MachineSecretVariantConditionMetadata",
    "ProfileAuthenticationContractMetadata",
    "command_registration_for_node",
    "command_registration_metadata",
    "command_registration_policy",
    "command_registration_projection",
    "command_required_input_names",
    "command_schema_refs",
    "command_schema_type",
    "command_schema_types",
    "machine_secret_payload_metadata",
    "operator_parameters",
    "parameter_is_required",
    "profile_authentication_contract",
]
