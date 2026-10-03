"""Inward command-surface ports consumed by outer composition roots.

The command graph is an outer concern, but the values exchanged with another
composition root are application contracts.  Keeping these records here lets
the CLI and the retained harness share one schema, policy, and dispatch
vocabulary without either side importing the other.  Implementations remain
free to resolve their own command graph; this module contains no Typer, Click,
entrypoint, or process-launching code.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any, Literal, NotRequired, TypedDict

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from ...core.errors.hierarchy import CadrumoError
from ...core.type_guards import is_object_list_or_tuple

if TYPE_CHECKING:
    pass

#: ``defer_build`` keeps these records out of the import cost every process
#: pays: only the surface manifest, the reconciliation projection and the verb
#: input schema validate them, and pydantic builds each on its first use.
_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid", defer_build=True)


class CommandNodeKind(StrEnum):
    """The position a command node occupies in an outer command graph."""

    ROOT = "root"
    GROUP = "group"
    LEAF = "leaf"


class ParameterKind(StrEnum):
    """Whether a command input is positional or option-shaped."""

    ARGUMENT = "argument"
    OPTION = "option"


class JsonType(StrEnum):
    """The JSON scalar represented by a command input."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"


class VerbParameterJsonSchema(TypedDict):
    """JSON Schema a consumer reads for one command parameter."""

    type: str
    items: NotRequired[VerbParameterJsonSchema]
    enum: NotRequired[list[str]]
    description: NotRequired[str]
    default: NotRequired[JsonValue]


class VerbInputJsonSchema(TypedDict):
    """Strict JSON object schema a consumer reads for one command's inputs."""

    type: Literal["object"]
    properties: dict[str, VerbParameterJsonSchema]
    required: list[str]
    additionalProperties: bool


class CommandWriteRoute(StrEnum):
    """The storage scope through which a command may write."""

    NONE = "none"
    PROFILE_BOUND = "profile-bound"
    BOOTSTRAP_ROOT = "bootstrap-root"


class ProfileAuthenticationPosture(StrEnum):
    """The authentication posture declared by a command registration."""

    NOT_APPLICABLE = "not-applicable"
    RESUME_FALLBACK = "resume-fallback"
    SELF_AUTHENTICATING = "self-authenticating"


class MachineSecretPresence(StrEnum):
    """Presence condition for a machine-secret payload variant."""

    ABSENT = "absent"
    PRESENT = "present"


type Capability = Literal[
    "state-free",
    "local-storage",
    "registry",
    "profile-custody",
    "encrypted-facts",
    "network",
    "aeat",
    "browser",
    "google",
    "calculation",
    "filing",
    "crypto",
    "subprocess",
]
type SideEffect = Literal["none", "local-state", "network", "browser", "google"]
type PerformanceClass = Literal["metadata", "local-io", "compute", "external-io", "interactive"]
type CommandWriteRouteValue = Literal[
    CommandWriteRoute.NONE,
    CommandWriteRoute.PROFILE_BOUND,
    CommandWriteRoute.BOOTSTRAP_ROOT,
]
type ProfileAuthenticationPostureValue = Literal[
    ProfileAuthenticationPosture.NOT_APPLICABLE,
    ProfileAuthenticationPosture.RESUME_FALLBACK,
    ProfileAuthenticationPosture.SELF_AUTHENTICATING,
]
type MachineSecretPresenceValue = Literal[MachineSecretPresence.ABSENT, MachineSecretPresence.PRESENT]
type CommandParameterDefault = bool | int | float | str | tuple[bool | int | float | str | None, ...] | None


@dataclass(frozen=True, slots=True)
class CommandCapabilityClass:
    """Capability/effect/performance classification supplied by the graph."""

    capabilities: frozenset[Capability]
    side_effects: frozenset[SideEffect]
    performance: PerformanceClass

    @property
    def expanded_capabilities(self) -> frozenset[Capability]:
        """Return the transitive capability implications used by policy checks."""
        implications: dict[Capability, tuple[Capability, ...]] = {
            "encrypted-facts": ("profile-custody",),
            "aeat": ("network",),
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
class CommandParameterMetadata:
    """One language-specific parameter projection from a command declaration."""

    name: str
    kind: ParameterKind
    cli_flag: str
    off_flag: str
    json_type: JsonType
    required: bool
    is_flag: bool
    multiple: bool
    choices: tuple[str, ...]
    default: CommandParameterDefault
    help: str


@dataclass(frozen=True, slots=True)
class MachineSecretFieldMetadata:
    """Value-free field shape for one machine-secret payload."""

    name: str
    json_type: Literal["string"]


@dataclass(frozen=True, slots=True)
class MachineSecretVariantConditionMetadata:
    """Condition selecting one machine-secret payload variant."""

    option_name: str
    presence: MachineSecretPresenceValue


@dataclass(frozen=True, slots=True)
class MachineSecretPayloadMetadata:
    """Value-free machine-secret payload contract exposed to a consumer."""

    key: str
    fields: tuple[MachineSecretFieldMetadata, ...]
    condition: MachineSecretVariantConditionMetadata | None
    maximum_bytes: int
    same_scope_exclusive: bool
    duplicate_keys_forbidden: bool
    extra_fields_forbidden: bool


@dataclass(frozen=True, slots=True)
class ProfileAuthenticationContractMetadata:
    """Value-free profile-authentication shape and collision rules."""

    fields: tuple[MachineSecretFieldMetadata, ...]
    maximum_bytes: int
    same_scope_exclusive: bool
    stdin_exclusive_across_scopes: bool
    descriptors_must_differ_across_scopes: bool
    duplicate_keys_forbidden: bool
    extra_fields_forbidden: bool


@dataclass(frozen=True, slots=True)
class CommandPolicyMetadata:
    """Graph declaration from which an execution policy is projected."""

    capabilities: frozenset[Capability]
    side_effects: frozenset[SideEffect]
    performance: PerformanceClass
    write_route: CommandWriteRouteValue
    destructive: bool
    handoff: bool
    live_write: bool


@dataclass(frozen=True, slots=True)
class CommandRegistrationMetadata:
    """One command registration projected without an entrypoint object."""

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
    profile_authentication: ProfileAuthenticationPostureValue = ProfileAuthenticationPosture.NOT_APPLICABLE

    @property
    def help(self) -> dict[str, str]:
        """Return the language-indexed help projection."""
        return dict(self.help_by_language)

    @property
    def parameters(self) -> dict[str, tuple[CommandParameterMetadata, ...] | None]:
        """Return the language-indexed parameter projection."""
        return dict(self.parameters_by_language)


class RecoveryHandoffContract(BaseModel):
    """Value-free machine discovery for a two-way secret handoff."""

    model_config = _FROZEN

    handoff_option: str
    handoff_direction: Literal["write"]
    verification_option: str
    verification_direction: Literal["read"]
    required_together: bool
    json_fields: tuple[str, ...]
    maximum_bytes: int
    strict_utf8_object: bool
    duplicate_extra_missing_fields_refused: bool
    descriptors_closed: bool
    reserved_descriptors: tuple[int, ...]
    descriptors_must_differ: bool
    collides_with: tuple[str, ...]
    windows_handle_bootstrap: str


class VerbLeafKind(StrEnum):
    """Kind of resolved outer command leaf."""

    COMMAND = "command"
    CALLBACK = "callback"


class VerbParameter(BaseModel):
    """One input parameter in an application-owned verb schema."""

    model_config = _FROZEN

    name: str = Field(min_length=1)
    kind: ParameterKind
    cli_flag: str = ""
    off_flag: str = ""
    json_type: JsonType
    required: bool
    is_flag: bool
    multiple: bool
    choices: tuple[str, ...] = ()
    default: bool | int | float | str | list[Any] | None = None
    help: str = ""

    def property_schema(self) -> VerbParameterJsonSchema:
        """Project this parameter into the consumer-facing JSON schema."""
        scalar: VerbParameterJsonSchema = {"type": self.json_type.value}
        if self.choices:
            scalar["enum"] = list(self.choices)
        if self.help:
            scalar["description"] = self.help
        schema: VerbParameterJsonSchema = {"type": "array", "items": scalar} if self.multiple else scalar
        if self.default is not None:
            schema["default"] = self.default
        return schema


class ResolvedVerbLeaf(BaseModel):
    """One command key resolved to its canonical outer path."""

    model_config = _FROZEN

    subject_leaf_key: str = Field(min_length=1)
    cli_path: tuple[str, ...]
    alias_paths: tuple[tuple[str, ...], ...] = ()
    kind: VerbLeafKind


class VerbLeafResolutionFailure(BaseModel):
    """One failed command-key-to-schema resolution."""

    model_config = _FROZEN

    subject_leaf_key: str = Field(min_length=1)
    attempted_cli_path: tuple[str, ...]
    resolved_cli_path: tuple[str, ...] = ()
    reason: str = Field(min_length=1)


class VerbInputSchema(BaseModel):
    """Application-owned input schema supplied by an outer command adapter."""

    model_config = _FROZEN

    command_key: str = Field(min_length=1)
    cli_path: tuple[str, ...]
    parameters: tuple[VerbParameter, ...] = ()
    machine_secret_payloads: tuple[MachineSecretPayloadMetadata, ...] = ()
    recovery_handoff_contract: RecoveryHandoffContract | None = None
    profile_authentication: ProfileAuthenticationPostureValue
    profile_authentication_contract: ProfileAuthenticationContractMetadata
    help: str = ""

    @property
    def resolved_leaf(self) -> ResolvedVerbLeaf:
        """Return the canonical command-leaf identity represented by this schema."""
        return ResolvedVerbLeaf(subject_leaf_key=self.command_key, cli_path=self.cli_path, kind=VerbLeafKind.COMMAND)

    @property
    def required_inputs(self) -> tuple[VerbParameter, ...]:
        """Return parameters that must be supplied by a caller."""
        return tuple(parameter for parameter in self.parameters if parameter.required)

    def json_schema(self) -> VerbInputJsonSchema:
        """Project the input contract into a strict JSON object schema."""
        return {
            "type": "object",
            "properties": {parameter.name: parameter.property_schema() for parameter in self.parameters},
            "required": [parameter.name for parameter in self.parameters if parameter.required],
            "additionalProperties": False,
        }


class SchemaResolutionError(CadrumoError):
    """Raised by an outer adapter when its live schema projection is incomplete."""

    def __init__(self, failures: tuple[VerbLeafResolutionFailure, ...]) -> None:
        """Store every unresolved leaf so an adapter can report them together."""
        self.failures = failures
        super().__init__("; ".join(f"{item.subject_leaf_key}: {item.reason}" for item in failures))


def _parameter_values(parameter: VerbParameter, value: object) -> Sequence[object]:
    """Preserve repeated list/tuple inputs while treating other values as scalar."""
    return value if parameter.multiple and is_object_list_or_tuple(value) else (value,)


def _option_tokens(parameter: VerbParameter, value: object, values: Sequence[object]) -> tuple[str, ...]:
    """Encode one option, flag or repeated option without changing token order."""
    if parameter.is_flag:
        if value:
            return (parameter.cli_flag,)
        return (parameter.off_flag,) if parameter.off_flag else ()
    if parameter.multiple:
        return tuple(token for item in values for token in (parameter.cli_flag, str(item)))
    return parameter.cli_flag, str(value)


def _parameter_tokens(parameter: VerbParameter, value: object) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return positional and option tokens for one supplied parameter."""
    values = _parameter_values(parameter, value)
    if parameter.kind is ParameterKind.ARGUMENT:
        return tuple(str(item) for item in values), ()
    return (), _option_tokens(parameter, value, values)


def cli_argv_for(schema: VerbInputSchema, arguments: Mapping[str, object]) -> list[str]:
    """Encode named schema arguments into the canonical command argv tail."""
    positional: list[str] = []
    options: list[str] = []
    for parameter in schema.parameters:
        if parameter.name not in arguments:
            continue
        parameter_positional, parameter_options = _parameter_tokens(parameter, arguments[parameter.name])
        positional.extend(parameter_positional)
        options.extend(parameter_options)
    return ["--format", "json", *schema.cli_path, *positional, *options]


def assert_schema_coverage(resolution_errors: tuple[VerbLeafResolutionFailure, ...]) -> None:
    """Raise one typed error when an outer adapter cannot project a leaf."""
    if resolution_errors:
        raise SchemaResolutionError(resolution_errors)


__all__ = [
    "Capability",
    "CommandCapabilityClass",
    "CommandNodeKind",
    "CommandParameterDefault",
    "CommandParameterMetadata",
    "CommandPolicyMetadata",
    "CommandRegistrationMetadata",
    "CommandWriteRoute",
    "CommandWriteRouteValue",
    "JsonType",
    "MachineSecretFieldMetadata",
    "MachineSecretPayloadMetadata",
    "MachineSecretPresence",
    "MachineSecretPresenceValue",
    "MachineSecretVariantConditionMetadata",
    "ParameterKind",
    "PerformanceClass",
    "ProfileAuthenticationContractMetadata",
    "ProfileAuthenticationPosture",
    "ProfileAuthenticationPostureValue",
    "RecoveryHandoffContract",
    "ResolvedVerbLeaf",
    "SchemaResolutionError",
    "SideEffect",
    "VerbInputSchema",
    "VerbLeafKind",
    "VerbLeafResolutionFailure",
    "VerbParameter",
    "assert_schema_coverage",
    "cli_argv_for",
]
