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
from typing import Any, ClassVar, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from ...core.json_contract import RegisteredSchema
from .manifest import CommandSchemaRef

_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")


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


@dataclass(frozen=True, slots=True)
class LiveNodeRegistrationMetadata:
    """One live command-tree node projected by an outer graph adapter."""

    path: tuple[str, ...]
    kind: CommandNodeKind
    loader_owner: str | None
    handler_owner: str
    source_sha256: str | None
    policy: CommandPolicyMetadata | None


@dataclass(frozen=True, slots=True)
class CommandRegistrationProjection:
    """Complete registration projection shared by outer consumers."""

    commands: tuple[CommandRegistrationMetadata, ...]
    nodes: tuple[LiveNodeRegistrationMetadata, ...]
    profile_authentication_contract: ProfileAuthenticationContractMetadata


@dataclass(frozen=True, slots=True)
class CommandExecutionPolicy:
    """Validated immutable execution policy returned by the command port."""

    classification: CommandCapabilityClass
    write_route: CommandWriteRouteValue
    destructive: bool = False
    handoff: bool = False
    live_write: bool = False

    def __post_init__(self) -> None:
        """Reject policy flags that contradict the declared capabilities."""
        if self.write_route != CommandWriteRoute.NONE and "local-state" not in self.classification.side_effects:
            raise ValueError("a command write-route scope requires the local-state side effect")
        if (
            self.write_route != CommandWriteRoute.NONE
            and "profile-custody" not in self.classification.expanded_capabilities
        ):
            raise ValueError("a command storage write-route scope requires the profile-custody capability")
        if self.destructive and "local-state" not in self.classification.side_effects:
            raise ValueError("a destructive command requires the local-state side effect")
        if self.handoff and "filing" not in self.classification.expanded_capabilities:
            raise ValueError("a filing handoff requires the filing capability")
        if self.handoff and "local-state" not in self.classification.side_effects:
            raise ValueError("a filing handoff requires the local-state side effect")
        if self.live_write and "network" not in self.classification.expanded_capabilities:
            raise ValueError("a live write requires the network capability")
        if self.live_write and not self.classification.side_effects.intersection({"network", "browser"}):
            raise ValueError("a live write requires a network or browser side effect")


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

    def property_schema(self) -> dict[str, Any]:
        """Project this parameter into the consumer-facing JSON schema."""
        scalar: dict[str, Any] = {"type": self.json_type.value}
        if self.choices:
            scalar["enum"] = list(self.choices)
        if self.help:
            scalar["description"] = self.help
        schema: dict[str, Any] = {"type": "array", "items": scalar} if self.multiple else scalar
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

    def json_schema(self) -> dict[str, Any]:
        """Project the input contract into a strict JSON object schema."""
        return {
            "type": "object",
            "properties": {parameter.name: parameter.property_schema() for parameter in self.parameters},
            "required": [parameter.name for parameter in self.parameters if parameter.required],
            "additionalProperties": False,
        }


class SchemaResolutionError(RuntimeError):
    """Raised by an outer adapter when its live schema projection is incomplete."""

    __bare_base_rationale__: ClassVar[str] = (
        "internal-schema-coverage-assertion-carrier: assert_schema_coverage raises this when the "
        "command graph and the declared verb schemas disagree, which is a build-time consistency "
        "failure for a developer, never a condition an operator can act on"
    )

    def __init__(self, failures: tuple[VerbLeafResolutionFailure, ...]) -> None:
        """Store every unresolved leaf so an adapter can report them together."""
        self.failures = failures
        super().__init__("; ".join(f"{item.subject_leaf_key}: {item.reason}" for item in failures))


@dataclass(frozen=True, slots=True)
class CommandDispatchResult:
    """Transport-neutral result of one outer command dispatch."""

    stdout: str
    stderr: str
    returncode: int


def cli_argv_for(schema: VerbInputSchema, arguments: Mapping[str, object]) -> list[str]:
    """Encode named schema arguments into the canonical command argv tail."""
    positional: list[str] = []
    options: list[str] = []
    for parameter in schema.parameters:
        if parameter.name not in arguments:
            continue
        value = arguments[parameter.name]
        values: Sequence[object] = value if parameter.multiple and isinstance(value, list | tuple) else (value,)
        if parameter.kind is ParameterKind.ARGUMENT:
            positional.extend(str(item) for item in values)
        elif parameter.is_flag:
            if value:
                options.append(parameter.cli_flag)
            elif parameter.off_flag:
                options.append(parameter.off_flag)
        elif parameter.multiple:
            options.extend(token for item in values for token in (parameter.cli_flag, str(item)))
        else:
            options.extend((parameter.cli_flag, str(value)))
    return ["--format", "json", *schema.cli_path, *positional, *options]


class CommandSchemaPort(Protocol):
    """Application boundary for an outer command graph's schema projection."""

    def command_schema_refs(self) -> tuple[CommandSchemaRef, ...]:
        """Return every registered result-schema identity."""
        ...

    def command_schema_type(self, command: str) -> RegisteredSchema:
        """Return the registered result schema for one command identity."""
        ...

    def command_schema_types(self) -> Mapping[str, RegisteredSchema]:
        """Return the immutable command-to-result-schema projection."""
        ...

    def command_registration_projection(self) -> CommandRegistrationProjection:
        """Return the complete registration metadata projection."""
        ...

    def build_verb_input_schemas(self, command_keys: tuple[str, ...]) -> Mapping[str, VerbInputSchema]:
        """Build input schemas for the requested command identities."""
        ...


class CommandMetadataPort(Protocol):
    """Application boundary for command identity and exposure metadata."""

    def cli_path_for_command_key(self, command_key: str) -> tuple[str, ...]:
        """Resolve one command identity to its canonical path."""
        ...

    def is_exposable_command(self, command_key: str) -> bool:
        """Return whether an identity is callable on the external surface."""
        ...

    def command_search_terms(self, command_key: str) -> tuple[str, ...]:
        """Return graph-authored semantic search terms for one command."""
        ...

    def global_flags(self) -> frozenset[str]:
        """Return root options accepted alongside every command path."""
        ...


class CommandPolicyPort(Protocol):
    """Application boundary for policy lookup by canonical command path."""

    def command_execution_policy_for_cli_path(self, cli_path: tuple[str, ...]) -> CommandExecutionPolicy: ...


class CommandDispatchPort(Protocol):
    """Application boundary for process/in-process command dispatch."""

    def dispatch_verb(
        self,
        schema: VerbInputSchema,
        arguments: Mapping[str, object],
        *,
        acquire_timeout_s: float,
        profile_secret_stdin_payload: str | None = None,
    ) -> CommandDispatchResult | None:
        """Dispatch one validated verb through an outer transport."""
        ...


class CommandSurfacePort(CommandSchemaPort, CommandMetadataPort, CommandPolicyPort, Protocol):
    """Complete read-only command surface consumed by the retained harness."""


def assert_schema_coverage(resolution_errors: tuple[VerbLeafResolutionFailure, ...]) -> None:
    """Raise one typed error when an outer adapter cannot project a leaf."""
    if resolution_errors:
        raise SchemaResolutionError(resolution_errors)


__all__ = [
    "Capability",
    "CommandCapabilityClass",
    "CommandDispatchPort",
    "CommandDispatchResult",
    "CommandExecutionPolicy",
    "CommandMetadataPort",
    "CommandNodeKind",
    "CommandParameterDefault",
    "CommandParameterMetadata",
    "CommandPolicyMetadata",
    "CommandRegistrationMetadata",
    "CommandRegistrationProjection",
    "CommandSchemaPort",
    "CommandSurfacePort",
    "CommandWriteRoute",
    "CommandWriteRouteValue",
    "JsonType",
    "LiveNodeRegistrationMetadata",
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
