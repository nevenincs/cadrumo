"""Operator projections of the sole immutable :class:`CommandSpecGraph`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from functools import cache
from types import MappingProxyType
from typing import TYPE_CHECKING, cast

from ...application.operator_surface.command_ports import (
    CommandCapabilityClass,
    CommandParameterDefault,
    CommandParameterMetadata,
    CommandPolicyMetadata,
    CommandRegistrationMetadata,
    MachineSecretFieldMetadata,
    MachineSecretPayloadMetadata,
    MachineSecretVariantConditionMetadata,
    ProfileAuthenticationContractMetadata,
)
from ...core.i18n.render import output_language, tr
from ...core.type_guards import is_object_list_or_tuple
from ._command_target import resolve_deferred_target
from .command_spec import (
    CommandNodeKind,
    DefaultKind,
    JsonType,
    OptionSpec,
    SchemaState,
)

if TYPE_CHECKING:
    from ...application.operator_surface.manifest import CommandSchemaRef
    from ...core.json_contract import RegisteredSchema
    from ._command_policy import CommandExecutionPolicy
    from .command_spec import CommandSpec, CommandSpecNode, ParameterSpec, ProfileSecretSpec


def machine_secret_payload_metadata(spec: CommandSpec) -> tuple[MachineSecretPayloadMetadata, ...]:
    """Project value-free secret shapes directly from their owning command spec."""
    from .config.secure_input import MACHINE_SECRET_MAX_BYTES

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
    path: tuple[str, ...]
    kind: CommandNodeKind
    loader_owner: str | None
    handler_owner: str
    source_sha256: str | None
    policy: CommandPolicyMetadata | None


@dataclass(frozen=True, slots=True)
class CommandRegistrationProjection:
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
    except (ImportError, AttributeError, RuntimeError):
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


def _parameter(parameter: ParameterSpec) -> CommandParameterMetadata:
    cli_flag, off_flag = _parameter_flags(parameter)
    json_type = _json_type(parameter)
    return CommandParameterMetadata(
        parameter.name,
        parameter.kind,
        cli_flag,
        off_flag,
        json_type,
        parameter.default.kind is DefaultKind.REQUIRED,
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


def _operator_path(path: tuple[str, ...]) -> tuple[str, ...]:
    return path[1:] if path and path[0] == "aeat" else path


def command_registration_projection() -> CommandRegistrationProjection:
    """Project graph metadata in the currently selected output language."""
    return _command_registration_projection(output_language())


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
    """Project a target result schema into one command registration, if exposed."""
    from ._profile_authentication_contract import profile_authentication_posture

    spec = node.spec
    schema = spec.result_schema
    if schema.state is not SchemaState.TARGET or schema.identity is None or schema.target is None:
        return None
    parameters = tuple(_parameter(parameter) for parameter in spec.parameters if not parameter.hidden)
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


def _profile_authentication_contract(
    root_profile_secret: ProfileSecretSpec,
    *,
    maximum_bytes: int,
) -> ProfileAuthenticationContractMetadata:
    """Project the root profile-secret shape without exposing any secret value."""
    return ProfileAuthenticationContractMetadata(
        fields=tuple(MachineSecretFieldMetadata(field.name, field.json_type) for field in root_profile_secret.fields),
        maximum_bytes=maximum_bytes,
        same_scope_exclusive=True,
        stdin_exclusive_across_scopes=True,
        descriptors_must_differ_across_scopes=True,
        duplicate_keys_forbidden=True,
        extra_fields_forbidden=True,
    )


@cache
def _command_registration_projection(language: str) -> CommandRegistrationProjection:
    from .command_specs import COMMAND_GRAPH
    from .config.secure_input import MACHINE_SECRET_MAX_BYTES

    root_profile_secret = COMMAND_GRAPH.by_key()["root"].profile_secret
    if root_profile_secret is None:
        raise RuntimeError("root command spec must declare profile-secret metadata authority")

    commands: list[CommandRegistrationMetadata] = []
    nodes: list[LiveNodeRegistrationMetadata] = []
    for node in COMMAND_GRAPH.nodes():
        spec = node.spec
        path = _operator_path(node.path)
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
    return CommandRegistrationProjection(
        tuple(sorted(commands, key=lambda row: row.command)),
        tuple(nodes),
        _profile_authentication_contract(
            root_profile_secret,
            maximum_bytes=MACHINE_SECRET_MAX_BYTES,
        ),
    )


def command_registration_metadata() -> tuple[CommandRegistrationMetadata, ...]:
    return command_registration_projection().commands


@cache
def command_registration_policy(command: str) -> CommandExecutionPolicy:
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
    from ._command_target import resolve_deferred_target
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
    "command_registration_metadata",
    "command_registration_policy",
    "command_registration_projection",
    "command_schema_refs",
    "command_schema_type",
    "command_schema_types",
    "machine_secret_payload_metadata",
]
