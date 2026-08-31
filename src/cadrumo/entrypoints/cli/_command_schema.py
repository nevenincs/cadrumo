"""Operator projections of the sole immutable :class:`CommandSpecGraph`."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from functools import cache
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, cast

from ...core.i18n._render import output_language, tr
from ._command_spec import DefaultKind, OptionSpec, SchemaState

if TYPE_CHECKING:
    from ...application.operator_surface.manifest import CommandSchemaRef
    from ...core.json_contract import RegisteredSchema
    from ._command_policy import CommandExecutionPolicy
    from ._command_spec import CommandSpec, ParameterSpec

CommandCapability = Literal[
    "state-free",
    "local-storage",
    "registry",
    "profile-custody",
    "encrypted-facts",
    "network",
    "browser",
    "google",
    "calculation",
    "filing",
    "crypto",
    "subprocess",
]
CommandSideEffectClass = Literal["none", "local-state", "network", "browser", "google"]
CommandPerformanceClass = Literal["metadata", "local-io", "compute", "external-io", "interactive"]
CommandParameterKind = Literal["argument", "option"]
CommandJsonType = Literal["string", "integer", "number", "boolean"]
CommandParameterDefault = bool | int | float | str | tuple[bool | int | float | str | None, ...] | None


@dataclass(frozen=True, slots=True)
class CommandCapabilityClass:
    capabilities: frozenset[CommandCapability]
    side_effects: frozenset[CommandSideEffectClass]
    performance: CommandPerformanceClass

    @property
    def expanded_capabilities(self) -> frozenset[CommandCapability]:
        implications: dict[CommandCapability, tuple[CommandCapability, ...]] = {
            "encrypted-facts": ("profile-custody",),
            "browser": ("network",),
            "google": ("network",),
            "calculation": ("registry",),
            "filing": ("registry",),
        }
        expanded = set(self.capabilities)
        pending = list(self.capabilities)
        while pending:
            for value in implications.get(pending.pop(), ()):
                if value not in expanded:
                    expanded.add(value)
                    pending.append(value)
        return frozenset(expanded)


@dataclass(frozen=True, slots=True)
class SchemaModuleLoadFailure:
    module: str
    error: str


@dataclass(frozen=True, slots=True)
class CommandParameterMetadata:
    name: str
    kind: CommandParameterKind
    cli_flag: str
    off_flag: str
    json_type: CommandJsonType
    required: bool
    is_flag: bool
    multiple: bool
    choices: tuple[str, ...]
    default: CommandParameterDefault
    help: str


@dataclass(frozen=True, slots=True)
class MachineSecretFieldMetadata:
    name: str
    json_type: Literal["string"]


@dataclass(frozen=True, slots=True)
class MachineSecretVariantConditionMetadata:
    option_name: str
    presence: Literal["absent", "present"]


@dataclass(frozen=True, slots=True)
class MachineSecretPayloadMetadata:
    key: str
    fields: tuple[MachineSecretFieldMetadata, ...]
    condition: MachineSecretVariantConditionMetadata | None
    maximum_bytes: int
    same_scope_exclusive: bool
    duplicate_keys_forbidden: bool
    extra_fields_forbidden: bool


@dataclass(frozen=True, slots=True)
class ProfileAuthenticationContractMetadata:
    """Value-free public shape and collision rules for the root capability."""

    fields: tuple[MachineSecretFieldMetadata, ...]
    maximum_bytes: int
    same_scope_exclusive: bool
    stdin_exclusive_across_scopes: bool
    descriptors_must_differ_across_scopes: bool
    duplicate_keys_forbidden: bool
    extra_fields_forbidden: bool


def machine_secret_payload_metadata(spec: CommandSpec) -> tuple[MachineSecretPayloadMetadata, ...]:
    """Project value-free secret shapes directly from their owning command spec."""
    from ._config._secure_input import MACHINE_SECRET_MAX_BYTES

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
class CommandPolicyMetadata:
    capabilities: frozenset[CommandCapability]
    side_effects: frozenset[CommandSideEffectClass]
    performance: CommandPerformanceClass
    write_route: Literal["none", "profile-bound", "bootstrap-root"]
    destructive: bool
    handoff: bool
    live_write: bool


@dataclass(frozen=True, slots=True)
class CommandRegistrationMetadata:
    command: str
    schema_name: str
    schema_owner: str
    schema_source_sha256: str
    cli_path: tuple[str, ...] | None
    parameters_by_language: tuple[tuple[str, tuple[CommandParameterMetadata, ...] | None], ...]
    help_by_language: tuple[tuple[str, str], ...]
    hidden: bool | None
    policy: CommandPolicyMetadata | None
    handler_owner: str | None
    source_sha256: str | None
    machine_secret_payloads: tuple[MachineSecretPayloadMetadata, ...] = ()
    profile_authentication: Literal["not-applicable", "resume-fallback", "self-authenticating"] = "not-applicable"

    @property
    def help(self) -> dict[str, str]:
        return dict(self.help_by_language)

    @property
    def parameters(self) -> dict[str, tuple[CommandParameterMetadata, ...] | None]:
        return dict(self.parameters_by_language)


@dataclass(frozen=True, slots=True)
class LiveNodeRegistrationMetadata:
    path: tuple[str, ...]
    kind: Literal["root", "group", "leaf"]
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


def _json_type(parameter: ParameterSpec) -> CommandJsonType:
    qualname = parameter.value.annotation.qualname
    return (
        "integer"
        if qualname == "int"
        else "number"
        if qualname == "float"
        else "boolean"
        if qualname == "bool"
        else "string"
    )


def _choices(parameter: ParameterSpec) -> tuple[str, ...]:
    if parameter.value.choices:
        return parameter.value.choices
    target = parameter.value.click_type or parameter.value.annotation
    try:
        value: object = __import__(target.module, fromlist=(target.qualname.split(".", 1)[0],))
        for segment in target.qualname.split("."):
            value = getattr(value, segment)
    except (ImportError, AttributeError):
        return ()
    if isinstance(value, type) and issubclass(value, Enum):
        return tuple(str(member.value) for member in value)
    declared = getattr(value, "choices", ())
    return tuple(str(choice) for choice in declared)


def _parameter(parameter: ParameterSpec) -> CommandParameterMetadata:
    declarations = parameter.declarations if isinstance(parameter, OptionSpec) else ()
    json_type = _json_type(parameter)
    return CommandParameterMetadata(
        parameter.name,
        parameter.kind,
        next((token for token in declarations if token.startswith("--") and not token.startswith("--no-")), ""),
        next((token for token in declarations if token.startswith("--no-")), ""),
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


def _operator_path(path: tuple[str, ...]) -> tuple[str, ...]:
    return path[1:] if path and path[0] == "aeat" else path


def command_registration_projection() -> CommandRegistrationProjection:
    """Project graph metadata in the currently selected output language."""
    return _command_registration_projection(output_language())


@cache
def _command_registration_projection(language: str) -> CommandRegistrationProjection:
    from ._command_specs import COMMAND_GRAPH
    from ._config._secure_input import MACHINE_SECRET_MAX_BYTES
    from ._profile_authentication_contract import profile_authentication_posture

    root_profile_secret = COMMAND_GRAPH.by_key()["root"].profile_secret
    if root_profile_secret is None:
        raise RuntimeError("root command spec must declare profile-secret metadata authority")

    commands: list[CommandRegistrationMetadata] = []
    nodes: list[LiveNodeRegistrationMetadata] = []
    for node in COMMAND_GRAPH.nodes():
        spec = node.spec
        path = _operator_path(node.path)
        owner = spec.handler.target.identity if spec.handler is not None and spec.handler.target is not None else None
        policy = _policy(spec)
        nodes.append(LiveNodeRegistrationMetadata(path, spec.kind, None, owner or "<metadata>", None, policy))
        schema = spec.result_schema
        if schema.state is not SchemaState.TARGET or schema.identity is None or schema.target is None:
            continue
        parameters = tuple(_parameter(parameter) for parameter in spec.parameters if not parameter.hidden)
        commands.append(
            CommandRegistrationMetadata(
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
                profile_authentication_posture(node).value,
            )
        )
    return CommandRegistrationProjection(
        tuple(sorted(commands, key=lambda row: row.command)),
        tuple(nodes),
        ProfileAuthenticationContractMetadata(
            fields=tuple(
                MachineSecretFieldMetadata(field.name, field.json_type) for field in root_profile_secret.fields
            ),
            maximum_bytes=MACHINE_SECRET_MAX_BYTES,
            same_scope_exclusive=True,
            stdin_exclusive_across_scopes=True,
            descriptors_must_differ_across_scopes=True,
            duplicate_keys_forbidden=True,
            extra_fields_forbidden=True,
        ),
    )


def command_registration_metadata() -> tuple[CommandRegistrationMetadata, ...]:
    return command_registration_projection().commands


@cache
def command_registration_policy(command: str) -> CommandExecutionPolicy:
    from ._command_policy import CommandExecutionPolicy
    from ._command_specs import COMMAND_GRAPH

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
    from ._command_specs import COMMAND_GRAPH

    return tuple(
        CommandSchemaRef(command=identity, schema_name=spec.result_schema.target.qualname)
        for identity, spec in sorted(COMMAND_GRAPH.by_schema_identity().items())
        if spec.result_schema.target is not None
    )


@cache
def command_schema_type(command: str) -> RegisteredSchema:
    """Resolve the authored result-schema target for one command identity."""
    from ._command_runtime import resolve_deferred_target
    from ._command_specs import COMMAND_GRAPH

    spec = COMMAND_GRAPH.by_schema_identity().get(command)
    if spec is None or spec.result_schema.target is None:
        raise LookupError(f"unknown command schema identity: {command}")
    target = resolve_deferred_target(spec.result_schema.target)
    if not isinstance(target, type):
        raise TypeError(f"command schema target is not a type: {command}")
    from ...core.json_contract import OutputRootSchema, OutputSchema

    if not issubclass(target, OutputSchema | OutputRootSchema):
        raise TypeError(f"command schema target is not an output schema: {command}")
    return target


@cache
def command_schema_types() -> Mapping[str, RegisteredSchema]:
    """Return the immutable graph-derived result-schema type projection."""
    from ._command_specs import COMMAND_GRAPH

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
    "SchemaModuleLoadFailure",
    "command_registration_metadata",
    "command_registration_policy",
    "command_registration_projection",
    "command_schema_refs",
    "command_schema_type",
    "command_schema_types",
    "machine_secret_payload_metadata",
]
