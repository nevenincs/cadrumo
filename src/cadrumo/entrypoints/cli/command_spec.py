"""Import-light production authority for the executable CLI command graph.

This module contains declarations only.  It deliberately does not import
Typer, Click, handlers, schemas, translation catalogues, or development tools.
Runtime assemblers and non-runtime validators consume the same immutable
records and resolve deferred targets only at their owning boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, StrEnum
from types import MappingProxyType
from typing import Final, Literal, cast

from ...core.transport_locus import TransportLocus, TransportRole, TransportShape
from . import _command_parameter_validation as _parameter_validation
from . import _command_policy_validation as _policy_validation
from . import _command_structure_validation as _structure_validation


class CommandNodeKind(StrEnum):
    """Where a command sits in the CLI tree."""

    ROOT = "root"
    GROUP = "group"
    LEAF = "leaf"


NON_LEAF_COMMAND_KINDS: Final[frozenset[CommandNodeKind]] = frozenset(
    {CommandNodeKind.ROOT, CommandNodeKind.GROUP},
)
"""The kinds that carry children.

Derived from the members rather than relisted. A node kind added to the tree cannot be
silently omitted here, which a hand-written pair invited -- and this pair was written
twice, in two comprehensions of one reconciliation module."""


class ParameterKind(StrEnum):
    """Whether a CLI parameter is positional or a flag."""

    ARGUMENT = "argument"
    OPTION = "option"


class JsonType(StrEnum):
    """The JSON scalar a CLI parameter serialises as.

    Lives here rather than beside its first consumer because both the command schema
    and the verb input schema need it, and the verb schema imports the command schema,
    so only the kernel can hold it without a cycle.
    """

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"


type LiteralValue = str | int | float | bool | bytes | None
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


class CommandWriteRoute(StrEnum):
    """Which storage a command is permitted to write through.

    One vocabulary that carried three names: ``WriteRoute`` here,
    ``CommandWriteRouteScope`` in the policy module, and an inline spelling in the
    command schema, with a fourth copy in a validation frozenset. A route added to one
    of those left the other three validating the old set.
    """

    NONE = "none"
    """Writes nothing into profile-bound storage.

    The claim is about WRITES only. A command declaring this route may still
    read bucket-scoped encrypted storage and may still refuse without an
    active profile; most of the read surface does exactly that. Reading it as
    a promise of uninitialised-installation safety would mis-describe the
    majority of the commands that carry it.
    """

    PROFILE_BOUND = "profile-bound"
    """Writes only inside the active profile's own storage."""

    BOOTSTRAP_ROOT = "bootstrap-root"
    """Writes to the installation root, before any profile exists to bind to."""


CommandWriteRouteValue = Literal[
    CommandWriteRoute.NONE,
    CommandWriteRoute.PROFILE_BOUND,
    CommandWriteRoute.BOOTSTRAP_ROOT,
]
"""The same vocabulary for a strict spec or payload field."""


_require_coherent_transport = _parameter_validation.require_coherent_transport
_require_identifier = _parameter_validation.require_identifier
_require_token = _parameter_validation.require_token
_validate_machine_secret_contract = _parameter_validation.validate_machine_secret_contract
_validate_machine_secret_option_channel = _parameter_validation.validate_machine_secret_option_channel
_validate_not_supported_schema = _parameter_validation.validate_not_supported_schema
_validate_option_declarations = _parameter_validation.validate_option_declarations
_validate_option_environment = _parameter_validation.validate_option_environment
_validate_option_flags = _parameter_validation.validate_option_flags
_validate_parameter_declarations = _parameter_validation.validate_parameter_declarations
_validate_profile_secret_contract = _parameter_validation.validate_profile_secret_contract
_validate_profile_secret_option_channel = _parameter_validation.validate_profile_secret_option_channel
_validate_secret_channel_scope = _parameter_validation.validate_secret_channel_scope
_validate_target_schema = _parameter_validation.validate_target_schema
_validate_unavailable_schema = _parameter_validation.validate_unavailable_schema

_validate_deferred_target = _policy_validation.validate_deferred_target
_validate_translation_key = _policy_validation.validate_translation_key
_validate_lazy_binding = _policy_validation.validate_lazy_binding
_expanded_capabilities = _policy_validation.expanded_capabilities
_validate_parameter_default = _policy_validation.validate_parameter_default
_validate_value_contract = _policy_validation.validate_value_contract
_validate_parameter_constraint = _policy_validation.validate_parameter_constraint
_validate_machine_secret_field = _policy_validation.validate_machine_secret_field
_validate_machine_secret_condition = _policy_validation.validate_machine_secret_condition
_validate_machine_secret_variant = _policy_validation.validate_machine_secret_variant
_validate_machine_secret = _policy_validation.validate_machine_secret
_validate_profile_secret = _policy_validation.validate_profile_secret
_validate_policy_destructive = _policy_validation.validate_policy_destructive
_validate_policy_effect_capabilities = _policy_validation.validate_policy_effect_capabilities
_validate_policy_exclusive_values = _policy_validation.validate_policy_exclusive_values
_validate_policy_handoff = _policy_validation.validate_policy_handoff
_validate_policy_live_write = _policy_validation.validate_policy_live_write
_validate_policy_membership = _policy_validation.validate_policy_membership
_validate_policy_types = _policy_validation.validate_policy_types
_validate_policy_write_route = _policy_validation.validate_policy_write_route

_graph_by_key = _structure_validation.graph_by_key
_graph_by_path = _structure_validation.graph_by_path
_graph_by_schema_identity = _structure_validation.graph_by_schema_identity
_graph_nodes = _structure_validation.graph_nodes
_resolve_graph_path = _structure_validation.resolve_graph_path
_validate_callback_parameters = _structure_validation.validate_callback_parameters
_validate_command_identity = _structure_validation.validate_command_identity
_validate_graph = _structure_validation.validate_graph
_validate_leaf_execution = _structure_validation.validate_leaf_execution
_validate_result_schema = _structure_validation.validate_result_schema
_validate_command_spec = _structure_validation.validate_command_spec
_validate_terminal_execution = _structure_validation.validate_terminal_execution
_validate_recovery_bootstrap = _structure_validation.validate_recovery_bootstrap
_validate_recovery_directions = _structure_validation.validate_recovery_directions
_validate_recovery_handoff_contract = _structure_validation.validate_recovery_handoff_contract
_validate_recovery_json_fields = _structure_validation.validate_recovery_json_fields
_validate_recovery_limits = _structure_validation.validate_recovery_limits
_validate_recovery_parameters = _structure_validation.validate_recovery_parameters
_validate_recovery_reserved_descriptors = _structure_validation.validate_recovery_reserved_descriptors


@dataclass(frozen=True, slots=True)
class ExecutionPolicySpec:
    """Complete capability, effect, budget, risk, and write-route authority."""

    capabilities: frozenset[Capability]
    side_effects: frozenset[SideEffect]
    performance: PerformanceClass
    write_route: CommandWriteRouteValue
    destructive: bool = False
    handoff: bool = False
    live_write: bool = False

    def __post_init__(self) -> None:
        """Validate the policy's capability, effect, budget, and risk-flag invariants, or raise."""
        _validate_policy_types(
            self.capabilities,
            self.side_effects,
            self.destructive,
            self.handoff,
            self.live_write,
        )
        _validate_policy_membership(self.capabilities, self.side_effects, self.performance, self.write_route)
        _validate_policy_exclusive_values(self.capabilities, self.side_effects)
        expanded = self.expanded_capabilities
        _validate_policy_effect_capabilities(self.side_effects, expanded)
        _validate_policy_write_route(self.write_route, self.side_effects, expanded)
        _validate_policy_destructive(self.destructive, self.side_effects)
        _validate_policy_handoff(self.handoff, expanded, self.side_effects)
        _validate_policy_live_write(self.live_write, expanded, self.side_effects)

    @property
    def expanded_capabilities(self) -> frozenset[Capability]:
        """Return the transitive capability closure used by import gates."""
        return cast(frozenset[Capability], _expanded_capabilities(self.capabilities))


@dataclass(frozen=True, slots=True)
class DeferredTarget:
    """A public Python object identity that is resolved only when selected."""

    module: str
    qualname: str

    def __post_init__(self) -> None:
        """Validate that ``module`` and ``qualname`` are dotted Python identifiers, or raise."""
        _validate_deferred_target(self.module, self.qualname)

    @property
    def identity(self) -> str:
        """Return the ``module:qualname`` identity string this target resolves to."""
        return f"{self.module}:{self.qualname}"


@dataclass(frozen=True, slots=True)
class TranslationKey:
    """A catalogue key; translated text never becomes structural authority."""

    value: str

    def __post_init__(self) -> None:
        """Validate that ``value`` is a non-empty, unpadded, dotted key, or raise."""
        _validate_translation_key(self.value)


def translation_key(value: str) -> TranslationKey:
    """Return the translation key for ``value``.

    Ten command-spec modules each defined this one-line construction privately,
    so ten places named the type a help or label string becomes.
    """
    return TranslationKey(value)


class BindingState(Enum):
    """Whether an implementation exists or is explicitly unavailable."""

    TARGET = "target"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class LazyBinding:
    """Deferred implementation or an explicit, localized unavailable state."""

    state: BindingState
    target: DeferredTarget | None = None
    reason_key: TranslationKey | None = None
    optional_dependencies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate the binding's state-dependent shape and optional-dependency tokens, or raise."""
        _validate_lazy_binding(
            self.state,
            self.target,
            self.reason_key,
            self.optional_dependencies,
            require_token=_require_token,
        )

    @classmethod
    def available(
        cls,
        target: DeferredTarget,
        *,
        optional_dependencies: tuple[str, ...] = (),
    ) -> LazyBinding:
        """Return a binding whose implementation resolves to ``target``."""
        return cls(BindingState.TARGET, target=target, optional_dependencies=optional_dependencies)

    @classmethod
    def unavailable(cls, reason_key: TranslationKey) -> LazyBinding:
        """Return a binding explicitly unavailable, with a localized reason."""
        return cls(BindingState.UNAVAILABLE, reason_key=reason_key)


class DefaultKind(Enum):
    """How a parameter's default value is determined."""

    REQUIRED = "required"
    LITERAL = "literal"
    FACTORY = "factory"


class MachineSecretChannelKind(Enum):
    """Value-free semantic role of a canonical secret transport option."""

    STDIN = "stdin"
    FILE_DESCRIPTOR = "file-descriptor"


class ProfileSecretChannelKind(Enum):
    """Semantic role of a root profile-authentication transport option."""

    STDIN = "stdin"
    FILE_DESCRIPTOR = "file-descriptor"


class ProfileAuthenticationPosture(StrEnum):
    """How the root profile-session gate applies to one parsed command."""

    NOT_APPLICABLE = "not-applicable"
    RESUME_FALLBACK = "resume-fallback"
    SELF_AUTHENTICATING = "self-authenticating"


ProfileAuthenticationPostureValue = Literal[
    ProfileAuthenticationPosture.NOT_APPLICABLE,
    ProfileAuthenticationPosture.RESUME_FALLBACK,
    ProfileAuthenticationPosture.SELF_AUTHENTICATING,
]
"""The posture where a strict payload field must accept the plain token.

The enum above was a bare ``Enum``, whose members are not strings, so no payload
surface could root a literal on it and two of them wrote the three tokens out instead.
It is a ``StrEnum`` now; every existing comparison uses ``is`` against a member, so
widening member-to-token equality changes nothing that was relied on.
"""


class MachineSecretPresence(StrEnum):
    """Whether an option must be present or absent to select a payload variant."""

    ABSENT = "absent"
    PRESENT = "present"


MachineSecretPresenceValue = Literal[
    MachineSecretPresence.ABSENT,
    MachineSecretPresence.PRESENT,
]
"""The same condition for a strict metadata payload field."""


@dataclass(frozen=True, slots=True)
class ParameterDefault:
    """A required marker, immutable literal, or deferred default factory."""

    kind: DefaultKind
    literal: LiteralValue | tuple[LiteralValue, ...] = None
    factory: DeferredTarget | None = None

    def __post_init__(self) -> None:
        """Validate that ``literal`` and ``factory`` agree with the declared ``kind``, or raise."""
        _validate_parameter_default(self.kind, self.literal, self.factory)

    @classmethod
    def required(cls) -> ParameterDefault:
        """Return a default marking the parameter as required, with no value."""
        return cls(DefaultKind.REQUIRED)

    @classmethod
    def value(cls, value: LiteralValue | tuple[LiteralValue, ...]) -> ParameterDefault:
        """Return a default carrying the immutable literal ``value``."""
        return cls(DefaultKind.LITERAL, literal=value)

    @classmethod
    def from_factory(cls, target: DeferredTarget) -> ParameterDefault:
        """Return a default resolved lazily through the deferred factory ``target``."""
        return cls(DefaultKind.FACTORY, factory=target)


@dataclass(frozen=True, slots=True)
class ValueContract:
    """Deferred annotation and conversion hooks for one CLI parameter."""

    annotation: DeferredTarget
    click_type: DeferredTarget | None = None
    parser: DeferredTarget | None = None
    completion: DeferredTarget | None = None
    callback: DeferredTarget | None = None
    choices: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """Validate that the click type, parser, and choices are mutually exclusive, or raise."""
        _validate_value_contract(self.click_type, self.parser, self.choices)


@dataclass(frozen=True, slots=True)
class ParameterConstraint:
    """Framework-neutral scalar constraints projected into Click/Typer."""

    minimum: int | float | None = None
    maximum: int | float | None = None
    clamp: bool = False
    case_sensitive: bool = True
    exists: bool = False
    file_okay: bool = True
    dir_okay: bool = True
    writable: bool = False
    readable: bool = True
    resolve_path: bool = False
    allow_dash: bool = False

    def __post_init__(self) -> None:
        """Validate the scalar bound and path-constraint invariants, or raise."""
        _validate_parameter_constraint(self.minimum, self.maximum, self.clamp)


@dataclass(frozen=True, slots=True)
class MachineSecretFieldSpec:
    """One value-free string field in a strict machine-secret payload."""

    name: str
    json_type: Literal["string"] = "string"

    def __post_init__(self) -> None:
        _validate_machine_secret_field(self.name, require_identifier=_require_identifier)


@dataclass(frozen=True, slots=True)
class MachineSecretConditionSpec:
    """Public option-presence condition selecting a payload variant."""

    option_name: str
    presence: MachineSecretPresenceValue

    def __post_init__(self) -> None:
        _validate_machine_secret_condition(self.option_name, require_identifier=_require_identifier)


@dataclass(frozen=True, slots=True)
class MachineSecretVariantSpec:
    """One strict payload shape and its lazily resolved public model."""

    key: str
    fields: tuple[MachineSecretFieldSpec, ...]
    model: DeferredTarget
    condition: MachineSecretConditionSpec | None = None

    def __post_init__(self) -> None:
        _validate_machine_secret_variant(self.key, self.fields, require_identifier=_require_identifier)


@dataclass(frozen=True, slots=True)
class MachineSecretSpec:
    """Complete immutable machine-secret authority for one command leaf."""

    variants: tuple[MachineSecretVariantSpec, ...]

    def __post_init__(self) -> None:
        _validate_machine_secret(self.variants)


@dataclass(frozen=True, slots=True)
class ProfileSecretSpec:
    """Strict value-free payload authority for root profile authentication."""

    fields: tuple[MachineSecretFieldSpec, ...]
    model: DeferredTarget

    def __post_init__(self) -> None:
        """Validate that fields are declared and their names are unique, or raise."""
        _validate_profile_secret(self.fields)


@dataclass(frozen=True, slots=True)
class RecoveryHandoffSpec:
    """Strict two-way recovery possession protocol owned by one command leaf."""

    handoff_parameter: str
    handoff_direction: Literal["write"]
    verification_parameter: str
    verification_direction: Literal["read"]
    required_together: bool
    json_fields: tuple[str, ...]
    maximum_bytes: int
    strict_utf8_object: bool
    duplicate_extra_missing_fields_refused: bool
    descriptors_closed: bool
    reserved_descriptors: tuple[int, ...]
    descriptors_must_differ: bool
    collides_with_parameters: tuple[str, ...]
    windows_handle_bootstrap: str

    def __post_init__(self) -> None:
        """Validate the recovery handoff protocol's parameters and flag invariants, or raise."""
        _validate_recovery_directions(self.handoff_direction, self.verification_direction)
        _validate_recovery_parameters(
            self.handoff_parameter,
            self.verification_parameter,
            self.collides_with_parameters,
            require_identifier=_require_identifier,
        )
        _validate_recovery_json_fields(self.json_fields, require_identifier=_require_identifier)
        _validate_recovery_limits(
            self.maximum_bytes,
            self.required_together,
            self.strict_utf8_object,
            self.duplicate_extra_missing_fields_refused,
            self.descriptors_closed,
            self.descriptors_must_differ,
        )
        _validate_recovery_reserved_descriptors(self.reserved_descriptors)
        _validate_recovery_bootstrap(self.windows_handle_bootstrap)


@dataclass(frozen=True, slots=True)
class ArgumentSpec:
    """One positional argument declaration, in command tuple order."""

    name: str
    value: ValueContract
    default: ParameterDefault
    help_key: TranslationKey | None
    metavar: str | None = None
    show_default: bool = True
    hidden: bool = False
    constraint: ParameterConstraint = ParameterConstraint()
    transport_locus: TransportLocus = TransportLocus.NONE
    transport_shape: TransportShape = TransportShape.NOT_APPLICABLE
    transport_role: TransportRole = TransportRole.NOT_APPLICABLE

    kind: ParameterKind = ParameterKind.ARGUMENT

    def __post_init__(self) -> None:
        """Validate the argument's name, metavar, and transport coherence, or raise."""
        _require_identifier(self.name, field="argument name")
        if self.metavar is not None:
            _require_token(self.metavar, field="argument metavar")
        _require_coherent_transport(
            self.transport_locus,
            self.transport_shape,
            self.transport_role,
            field="argument transport",
        )


@dataclass(frozen=True, slots=True)
class OptionSpec:
    """One named option declaration including aliases and flag pairing."""

    name: str
    declarations: tuple[str, ...]
    value: ValueContract
    default: ParameterDefault
    help_key: TranslationKey | None
    metavar: str | None = None
    show_default: bool = True
    hidden: bool = False
    is_flag: bool = False
    flag_value: LiteralValue = None
    multiple: bool = False
    count: bool = False
    prompt_key: TranslationKey | None = None
    confirmation_prompt_key: TranslationKey | None = None
    envvar: tuple[str, ...] = ()
    eager: bool = False
    constraint: ParameterConstraint = ParameterConstraint()
    machine_secret_channel: MachineSecretChannelKind | None = None
    profile_secret_channel: ProfileSecretChannelKind | None = None
    transport_locus: TransportLocus = TransportLocus.NONE
    transport_shape: TransportShape = TransportShape.NOT_APPLICABLE
    transport_role: TransportRole = TransportRole.NOT_APPLICABLE

    kind: ParameterKind = ParameterKind.OPTION

    def __post_init__(self) -> None:
        """Validate the option's declarations, flags, secret channels, and transport coherence, or raise."""
        _require_identifier(self.name, field="option name")
        _validate_option_declarations(self.declarations, self.metavar)
        _validate_option_flags(self.count, self.is_flag, self.multiple, self.flag_value)
        _validate_option_environment(self.envvar)
        _validate_machine_secret_option_channel(self.machine_secret_channel, self.value.annotation)
        _validate_secret_channel_scope(self.machine_secret_channel, self.profile_secret_channel)
        _validate_profile_secret_option_channel(self.profile_secret_channel, self.value.annotation)
        _require_coherent_transport(
            self.transport_locus,
            self.transport_shape,
            self.transport_role,
            field="option transport",
        )


type ParameterSpec = ArgumentSpec | OptionSpec


@dataclass(frozen=True, slots=True)
class InvocationSpec:
    """Command/group dispatch behavior independent of its implementation."""

    invoke_without_command: bool = False
    no_args_is_help: bool = False
    chain: bool = False
    add_help_option: bool = True
    add_completion: bool = False
    hidden: bool = False
    context_parameter: str | None = None
    terminal_behavior: Literal["introspection", "executable"] | None = None

    def __post_init__(self) -> None:
        """Validate the context parameter name, when declared, or raise."""
        if self.context_parameter is not None:
            _require_identifier(self.context_parameter, field="invocation context parameter")


class SchemaState(Enum):
    """Whether a result schema is targeted, not supported, or explicitly unavailable."""

    TARGET = "target"
    NOT_SUPPORTED = "not-supported"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ResultSchemaSpec:
    """Explicit result-schema target or intentional absence/unavailability."""

    state: SchemaState
    target: DeferredTarget | None = None
    reason_key: TranslationKey | None = None
    identity: str | None = None

    def __post_init__(self) -> None:
        """Validate the result-schema shape agrees with the declared ``state``, or raise."""
        _validate_result_schema(
            self.state,
            self.target,
            self.reason_key,
            self.identity,
            validate_target=_validate_target_schema,
            validate_not_supported=_validate_not_supported_schema,
            validate_unavailable=_validate_unavailable_schema,
        )


@dataclass(frozen=True, slots=True)
class CommandSpec:
    """Sole structural declaration for one root, group, or leaf node."""

    key: str
    parent_key: str | None
    token: str
    kind: CommandNodeKind
    help_key: TranslationKey
    short_help_key: TranslationKey | None
    invocation: InvocationSpec
    parameters: tuple[ParameterSpec, ...]
    policy: ExecutionPolicySpec
    handler: LazyBinding | None
    result_schema: ResultSchemaSpec
    search_terms: tuple[str, ...] = ()
    machine_secret: MachineSecretSpec | None = None
    profile_secret: ProfileSecretSpec | None = None
    recovery_handoff: RecoveryHandoffSpec | None = None
    profile_authentication: ProfileAuthenticationPosture = ProfileAuthenticationPosture.NOT_APPLICABLE
    profile_target_parameter: str | None = None
    allow_unregistered_profile_diagnostic: bool = False

    def __post_init__(self) -> None:
        """Validate the command node's identity, hierarchy, and dispatch invariants, or raise."""
        _validate_command_spec(
            self.key,
            self.parent_key,
            self.token,
            self.kind,
            self.handler,
            self.invocation,
            self.parameters,
            self.profile_target_parameter,
            self.search_terms,
            self.machine_secret,
            self.profile_secret,
            self.recovery_handoff,
            require_identifier=_require_identifier,
            require_token=_require_token,
            validate_identity=_validate_command_identity,
            validate_leaf=_validate_leaf_execution,
            validate_callbacks=_validate_callback_parameters,
            validate_terminal=_validate_terminal_execution,
            validate_parameters=_validate_parameter_declarations,
            validate_machine_secret=_validate_machine_secret_contract,
            validate_profile_secret=_validate_profile_secret_contract,
            validate_recovery=_validate_recovery_handoff_contract,
        )


@dataclass(frozen=True, slots=True)
class CommandSpecNode:
    """One graph node with its uniquely derived operator path."""

    path: tuple[str, ...]
    spec: CommandSpec


@dataclass(frozen=True, slots=True)
class CommandSpecGraph:
    """Validated immutable tree assembled from distributed specifications."""

    specs: tuple[CommandSpec, ...]

    def __post_init__(self) -> None:
        """Validate key uniqueness, single root, parent references, and path uniqueness, or raise."""
        _validate_graph(self.specs)

    def by_key(self) -> MappingProxyType[str, CommandSpec]:
        """Return every command spec indexed by its key."""
        return _graph_by_key(self.specs)

    def nodes(self) -> tuple[CommandSpecNode, ...]:
        """Return every command spec paired with its derived operator path."""
        return _graph_nodes(self.specs, node_type=CommandSpecNode)

    def by_path(self) -> MappingProxyType[tuple[str, ...], CommandSpec]:
        """Return the exact derived operator-path index."""
        return _graph_by_path(self.specs, node_type=CommandSpecNode)

    def resolve_path(self, path: tuple[str, ...]) -> CommandSpec:
        """Resolve one complete operator path, failing closed on absence."""
        return _resolve_graph_path(self.specs, path, node_type=CommandSpecNode)

    def by_schema_identity(self) -> MappingProxyType[str, CommandSpec]:
        """Return the unique executable result-schema identity index."""
        return _graph_by_schema_identity(self.specs)


#: The three builtin value contracts every command surface declares. They are
#: immutable and carry no per-module state, so a module-local copy is a
#: duplicate definition rather than a convenience: eighteen modules each
#: declared their own `_STR` / `_INT` / `_BOOL` before these were centralised.
TEXT_VALUE: Final[ValueContract] = ValueContract(DeferredTarget("builtins", "str"))
WHOLE_NUMBER_VALUE: Final[ValueContract] = ValueContract(DeferredTarget("builtins", "int"))
FLAG_VALUE: Final[ValueContract] = ValueContract(DeferredTarget("builtins", "bool"))
PATH_VALUE: Final[ValueContract] = ValueContract(DeferredTarget("pathlib", "Path"))

__all__ = [
    "FLAG_VALUE",
    "NON_LEAF_COMMAND_KINDS",
    "PATH_VALUE",
    "TEXT_VALUE",
    "WHOLE_NUMBER_VALUE",
    "ArgumentSpec",
    "BindingState",
    "CommandNodeKind",
    "CommandSpec",
    "CommandSpecGraph",
    "CommandSpecNode",
    "DefaultKind",
    "DeferredTarget",
    "ExecutionPolicySpec",
    "InvocationSpec",
    "JsonType",
    "LazyBinding",
    "LiteralValue",
    "MachineSecretPresence",
    "MachineSecretPresenceValue",
    "OptionSpec",
    "ParameterConstraint",
    "ParameterDefault",
    "ParameterKind",
    "ParameterSpec",
    "ProfileAuthenticationPosture",
    "ProfileAuthenticationPostureValue",
    "ProfileSecretChannelKind",
    "ProfileSecretSpec",
    "RecoveryHandoffSpec",
    "ResultSchemaSpec",
    "SchemaState",
    "TranslationKey",
    "ValueContract",
]
