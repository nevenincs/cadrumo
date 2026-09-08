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
from typing import Final, Literal

from ...core.transport_locus import TransportLocus, TransportRole, TransportShape


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

_CAPABILITIES = frozenset(
    {
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
    }
)
_SIDE_EFFECTS = frozenset({"none", "local-state", "network", "browser", "google"})
_PERFORMANCE_CLASSES = frozenset({"metadata", "local-io", "compute", "external-io", "interactive"})
_IMPLIED_CAPABILITIES: dict[Capability, frozenset[Capability]] = {
    "encrypted-facts": frozenset({"profile-custody"}),
    "browser": frozenset({"network"}),
    "google": frozenset({"network"}),
    "calculation": frozenset({"registry"}),
    "filing": frozenset({"registry"}),
}


def _require_identifier(value: str, *, field: str) -> None:
    if not value or value.strip() != value or not value.isidentifier():
        raise ValueError(f"{field} must be a non-empty Python identifier")


def _require_token(value: str, *, field: str) -> None:
    if not value or value.strip() != value or any(character.isspace() for character in value):
        raise ValueError(f"{field} must be a non-empty whitespace-free token")


def _validate_policy_types(
    capabilities: frozenset[Capability],
    side_effects: frozenset[SideEffect],
    destructive: bool,
    handoff: bool,
    live_write: bool,
) -> None:
    """Validate the policy container and risk-flag runtime types."""
    if not isinstance(capabilities, frozenset):
        raise TypeError("execution policy capabilities must be a frozenset")
    if not isinstance(side_effects, frozenset):
        raise TypeError("execution policy side effects must be a frozenset")
    if any(not isinstance(value, bool) for value in (destructive, handoff, live_write)):
        raise TypeError("execution policy risk flags must be bools")


def _validate_policy_membership(
    capabilities: frozenset[Capability],
    side_effects: frozenset[SideEffect],
    performance: PerformanceClass,
    write_route: CommandWriteRouteValue,
) -> None:
    """Validate capability, effect, performance, and write-route vocabularies."""
    if not capabilities or capabilities - _CAPABILITIES:
        raise ValueError("execution policy has missing or unknown capabilities")
    if not side_effects or side_effects - _SIDE_EFFECTS:
        raise ValueError("execution policy has missing or unknown side effects")
    if performance not in _PERFORMANCE_CLASSES:
        raise ValueError("execution policy has an unknown performance class")
    if write_route not in CommandWriteRoute:
        raise ValueError("execution policy has an unknown write route")


def _validate_policy_exclusive_values(
    capabilities: frozenset[Capability],
    side_effects: frozenset[SideEffect],
) -> None:
    """Enforce the mutually exclusive state-free and no-effect vocabularies."""
    if "state-free" in capabilities and capabilities != frozenset({"state-free"}):
        raise ValueError("state-free cannot be combined with authority capabilities")
    if "none" in side_effects and side_effects != frozenset({"none"}):
        raise ValueError("none cannot be combined with observable side effects")
    if capabilities == frozenset({"state-free"}) and side_effects != frozenset({"none"}):
        raise ValueError("state-free execution must be effect-free")


def _validate_policy_effect_capabilities(
    side_effects: frozenset[SideEffect],
    expanded_capabilities: frozenset[Capability],
) -> None:
    """Require each observable effect to carry its owning capability."""
    required_by_effect = {"network": "network", "browser": "browser", "google": "google"}
    if any(
        effect in side_effects and capability not in expanded_capabilities
        for effect, capability in required_by_effect.items()
    ):
        raise ValueError("execution policy side effect lacks its owning capability")


def _validate_policy_write_route(
    write_route: CommandWriteRouteValue,
    side_effects: frozenset[SideEffect],
    expanded_capabilities: frozenset[Capability],
) -> None:
    """Require storage writes to carry local-state effects and profile custody."""
    if write_route != CommandWriteRoute.NONE and (
        "local-state" not in side_effects or "profile-custody" not in expanded_capabilities
    ):
        raise ValueError("storage write routes require profile custody and local-state effects")


def _validate_policy_destructive(destructive: bool, side_effects: frozenset[SideEffect]) -> None:
    """Require destructive operations to declare local-state effects."""
    if destructive and "local-state" not in side_effects:
        raise ValueError("destructive execution requires a local-state effect")


def _validate_policy_handoff(
    handoff: bool, expanded_capabilities: frozenset[Capability], side_effects: frozenset[SideEffect]
) -> None:
    """Require filing handoffs to carry filing authority and local-state effects."""
    if handoff and ("filing" not in expanded_capabilities or "local-state" not in side_effects):
        raise ValueError("filing handoff requires filing authority and a local-state effect")


def _validate_policy_live_write(
    live_write: bool, expanded_capabilities: frozenset[Capability], side_effects: frozenset[SideEffect]
) -> None:
    """Require live writes to carry network authority and a network/browser effect."""
    if live_write and ("network" not in expanded_capabilities or not side_effects.intersection({"network", "browser"})):
        raise ValueError("live writes require network authority and a network/browser effect")


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
        expanded = set(self.capabilities)
        pending = list(self.capabilities)
        while pending:
            capability = pending.pop()
            for implied in _IMPLIED_CAPABILITIES.get(capability, ()):
                if implied not in expanded:
                    expanded.add(implied)
                    pending.append(implied)
        return frozenset(expanded)


@dataclass(frozen=True, slots=True)
class DeferredTarget:
    """A public Python object identity that is resolved only when selected."""

    module: str
    qualname: str

    def __post_init__(self) -> None:
        """Validate that ``module`` and ``qualname`` are dotted Python identifiers, or raise."""
        if not self.module or any(not part.isidentifier() for part in self.module.split(".")):
            raise ValueError("deferred target module must be a dotted Python module name")
        if not self.qualname or any(not part.isidentifier() for part in self.qualname.split(".")):
            raise ValueError("deferred target qualname must be a dotted Python identifier")

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
        if not self.value or self.value.strip() != self.value or "." not in self.value:
            raise ValueError("translation key must be a non-empty dotted key")


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
        if len(set(self.optional_dependencies)) != len(self.optional_dependencies):
            raise ValueError("optional dependency names must be unique")
        for dependency in self.optional_dependencies:
            _require_token(dependency, field="optional dependency")
        if self.state is BindingState.TARGET:
            if self.target is None or self.reason_key is not None:
                raise ValueError("target binding requires only a deferred target")
        elif self.state is BindingState.UNAVAILABLE:
            if self.target is not None or self.reason_key is None:
                raise ValueError("unavailable binding requires only a localized reason")
        else:  # pragma: no cover - Enum construction prevents this in normal use.
            raise ValueError(f"unknown binding state: {self.state!r}")

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
        if self.kind is DefaultKind.REQUIRED:
            if self.literal is not None or self.factory is not None:
                raise ValueError("required parameter default cannot carry a value")
        elif self.kind is DefaultKind.LITERAL:
            if self.factory is not None:
                raise ValueError("literal parameter default cannot carry a factory")
        elif self.kind is DefaultKind.FACTORY and (self.factory is None or self.literal is not None):
            raise ValueError("factory parameter default requires only a deferred factory")

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
        if self.click_type is not None and self.parser is not None:
            raise ValueError("value contract cannot declare both a Click type and parser")
        if len(self.choices) != len(set(self.choices)) or any(not choice for choice in self.choices):
            raise ValueError("value contract choices must be unique non-empty strings")
        if self.choices and (self.click_type is not None or self.parser is not None):
            raise ValueError("value contract choices cannot be combined with a Click type or parser")


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
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("parameter minimum cannot exceed maximum")
        if self.clamp and self.minimum is None and self.maximum is None:
            raise ValueError("clamping requires a minimum or maximum")


@dataclass(frozen=True, slots=True)
class MachineSecretFieldSpec:
    """One value-free string field in a strict machine-secret payload."""

    name: str
    json_type: Literal["string"] = "string"

    def __post_init__(self) -> None:
        _require_identifier(self.name, field="machine-secret field name")


@dataclass(frozen=True, slots=True)
class MachineSecretConditionSpec:
    """Public option-presence condition selecting a payload variant."""

    option_name: str
    presence: MachineSecretPresenceValue

    def __post_init__(self) -> None:
        _require_identifier(self.option_name, field="machine-secret condition option")


@dataclass(frozen=True, slots=True)
class MachineSecretVariantSpec:
    """One strict payload shape and its lazily resolved public model."""

    key: str
    fields: tuple[MachineSecretFieldSpec, ...]
    model: DeferredTarget
    condition: MachineSecretConditionSpec | None = None

    def __post_init__(self) -> None:
        _require_identifier(self.key, field="machine-secret variant key")
        if not self.fields:
            raise ValueError("machine-secret variant must declare at least one field")
        names = tuple(field.name for field in self.fields)
        if len(names) != len(set(names)):
            raise ValueError("machine-secret variant fields must be unique")


@dataclass(frozen=True, slots=True)
class MachineSecretSpec:
    """Complete immutable machine-secret authority for one command leaf."""

    variants: tuple[MachineSecretVariantSpec, ...]

    def __post_init__(self) -> None:
        if not self.variants:
            raise ValueError("machine-secret spec must declare at least one variant")
        keys = tuple(variant.key for variant in self.variants)
        if len(keys) != len(set(keys)):
            raise ValueError("machine-secret variant keys must be unique")
        targets = tuple(variant.model.identity for variant in self.variants)
        if len(targets) != len(set(targets)):
            raise ValueError("machine-secret payload model targets must be unique")


@dataclass(frozen=True, slots=True)
class ProfileSecretSpec:
    """Strict value-free payload authority for root profile authentication."""

    fields: tuple[MachineSecretFieldSpec, ...]
    model: DeferredTarget

    def __post_init__(self) -> None:
        """Validate that fields are declared and their names are unique, or raise."""
        if not self.fields:
            raise ValueError("profile-secret spec must declare at least one field")
        names = tuple(field.name for field in self.fields)
        if len(names) != len(set(names)):
            raise ValueError("profile-secret fields must be unique")


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
        )
        _validate_recovery_json_fields(self.json_fields)
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


def _validate_recovery_directions(handoff_direction: str, verification_direction: str) -> None:
    """Require the recovery handoff to write first and verify second."""
    if handoff_direction != "write" or verification_direction != "read":
        raise ValueError("recovery handoff directions must be write then read")


def _validate_recovery_parameters(
    handoff_parameter: str,
    verification_parameter: str,
    collides_with_parameters: tuple[str, ...],
) -> None:
    """Require distinct identifier-shaped recovery parameter names."""
    for value in (handoff_parameter, verification_parameter, *collides_with_parameters):
        _require_identifier(value, field="recovery handoff parameter")
    if handoff_parameter == verification_parameter:
        raise ValueError("recovery handoff descriptors must be distinct parameters")


def _validate_recovery_json_fields(json_fields: tuple[str, ...]) -> None:
    """Require unique identifier-shaped fields in the recovery JSON object."""
    if not json_fields or len(json_fields) != len(set(json_fields)):
        raise ValueError("recovery handoff JSON fields must be non-empty and unique")
    for field_name in json_fields:
        _require_identifier(field_name, field="recovery handoff JSON field")


def _validate_recovery_limits(
    maximum_bytes: int,
    required_together: bool,
    strict_utf8_object: bool,
    duplicate_extra_missing_fields_refused: bool,
    descriptors_closed: bool,
    descriptors_must_differ: bool,
) -> None:
    """Require a positive recovery payload limit and boolean protocol flags."""
    if maximum_bytes <= 0:
        raise ValueError("recovery handoff maximum bytes must be positive")
    if not all(
        isinstance(value, bool)
        for value in (
            required_together,
            strict_utf8_object,
            duplicate_extra_missing_fields_refused,
            descriptors_closed,
            descriptors_must_differ,
        )
    ):
        raise TypeError("recovery handoff protocol flags must be bools")


def _validate_recovery_reserved_descriptors(reserved_descriptors: tuple[int, ...]) -> None:
    """Require non-negative unique reserved recovery descriptors."""
    if not reserved_descriptors or any(value < 0 for value in reserved_descriptors):
        raise ValueError("recovery handoff reserved descriptors must be non-negative")
    if len(reserved_descriptors) != len(set(reserved_descriptors)):
        raise ValueError("recovery handoff reserved descriptors must be unique")


def _validate_recovery_bootstrap(windows_handle_bootstrap: str) -> None:
    """Require a non-empty whitespace-free Windows descriptor bootstrap token."""
    if not windows_handle_bootstrap or any(character.isspace() for character in windows_handle_bootstrap):
        raise ValueError("recovery handoff Windows bootstrap must be a non-empty token")


def _require_coherent_transport(
    locus: TransportLocus,
    shape: TransportShape,
    role: TransportRole,
    *,
    field: str,
) -> None:
    """Refuse a transport declaration whose three axes disagree.

    A locus that is not local has no filesystem shape and no role, and saying
    otherwise asserts a fact that does not exist. A locus that IS local has
    both, and leaving either at its not-applicable member is an author who
    filled in one field and stopped.
    """
    local = locus in {TransportLocus.LOCAL_IN, TransportLocus.LOCAL_OUT}
    if not local:
        if shape is not TransportShape.NOT_APPLICABLE:
            raise ValueError(f"{field} declares a shape without a local locus")
        if role is not TransportRole.NOT_APPLICABLE:
            raise ValueError(f"{field} declares a role without a local locus")
        return
    if shape is TransportShape.NOT_APPLICABLE:
        raise ValueError(f"{field} declares a local locus without a shape")
    if role is TransportRole.NOT_APPLICABLE:
        raise ValueError(f"{field} declares a local locus without a role")


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


def _validate_option_declarations(declarations: tuple[str, ...], metavar: str | None) -> None:
    """Validate option tokens and the optional display metavar."""
    if not declarations:
        raise ValueError("option must declare at least one CLI token")
    if len(set(declarations)) != len(declarations):
        raise ValueError("option declarations must be unique")
    for declaration in declarations:
        if not declaration.startswith("-"):
            raise ValueError("option declarations must begin with '-'")
        _require_token(declaration, field="option declaration")
    if metavar is not None:
        _require_token(metavar, field="option metavar")


def _validate_option_flags(count: bool, is_flag: bool, multiple: bool, flag_value: LiteralValue) -> None:
    """Validate count and explicit flag-value combinations."""
    if count and (not is_flag or multiple):
        raise ValueError("counting options must be singular flags")
    if flag_value is not None and not is_flag:
        raise ValueError("flag values require is_flag")


def _validate_option_environment(envvar: tuple[str, ...]) -> None:
    """Validate unique environment variable names and their token shape."""
    if len(set(envvar)) != len(envvar):
        raise ValueError("option environment variables must be unique")
    for variable in envvar:
        _require_token(variable, field="option environment variable")


def _validate_machine_secret_option_channel(
    channel: MachineSecretChannelKind | None,
    annotation: DeferredTarget,
) -> None:
    """Validate the value type required by a machine-secret channel."""
    if channel is MachineSecretChannelKind.STDIN and annotation != DeferredTarget("builtins", "bool"):
        raise ValueError("stdin machine-secret channel must be boolean")
    if channel is MachineSecretChannelKind.FILE_DESCRIPTOR and annotation != DeferredTarget("builtins", "int"):
        raise ValueError("file-descriptor machine-secret channel must be integer")


def _validate_secret_channel_scope(
    machine_secret_channel: MachineSecretChannelKind | None,
    profile_secret_channel: ProfileSecretChannelKind | None,
) -> None:
    """Refuse assigning one option to both machine and profile secret scopes."""
    if machine_secret_channel is not None and profile_secret_channel is not None:
        raise ValueError("one option cannot belong to both secret-channel scopes")


def _validate_profile_secret_option_channel(
    channel: ProfileSecretChannelKind | None,
    annotation: DeferredTarget,
) -> None:
    """Validate the value type required by a profile-secret channel."""
    if channel is ProfileSecretChannelKind.STDIN and annotation != DeferredTarget("builtins", "bool"):
        raise ValueError("stdin profile-secret channel must be boolean")
    if channel is ProfileSecretChannelKind.FILE_DESCRIPTOR and annotation != DeferredTarget("builtins", "int"):
        raise ValueError("file-descriptor profile-secret channel must be integer")


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
        if self.state is SchemaState.TARGET:
            _validate_target_schema(self.target, self.reason_key, self.identity)
        elif self.state is SchemaState.NOT_SUPPORTED:
            _validate_not_supported_schema(self.target, self.reason_key, self.identity)
        elif self.state is SchemaState.UNAVAILABLE:
            _validate_unavailable_schema(self.target, self.reason_key, self.identity)


def _validate_target_schema(
    target: DeferredTarget | None,
    reason_key: TranslationKey | None,
    identity: str | None,
) -> None:
    """Require a target schema's identity and target without an unavailable reason."""
    if target is None or reason_key is not None or identity is None:
        raise ValueError("schema target state requires an identity and target")
    parts = identity.split(".")
    if any(not part or any(character.isspace() for character in part) for part in parts):
        raise ValueError("schema identity must be a non-empty dotted token sequence")


def _validate_not_supported_schema(
    target: DeferredTarget | None,
    reason_key: TranslationKey | None,
    identity: str | None,
) -> None:
    """Require a not-supported schema to carry no target, reason, or identity."""
    if target is not None or reason_key is not None or identity is not None:
        raise ValueError("unsupported schema state carries no identity, target, or reason")


def _validate_unavailable_schema(
    target: DeferredTarget | None,
    reason_key: TranslationKey | None,
    identity: str | None,
) -> None:
    """Require an unavailable schema to carry only its localized reason."""
    if target is not None or reason_key is None or identity is not None:
        raise ValueError("unavailable schema state requires only a localized reason")


def _validate_command_identity(
    key: str,
    parent_key: str | None,
    token: str,
    kind: CommandNodeKind,
) -> None:
    """Validate the command key, token, and parent/kind relationship."""
    _require_identifier(key, field="command key")
    if parent_key is not None:
        _require_identifier(parent_key, field="command parent key")
    _require_token(token, field="command token")
    if kind not in CommandNodeKind:
        raise ValueError(f"unknown command node kind: {kind}")
    if kind == CommandNodeKind.ROOT and parent_key is not None:
        raise ValueError("root command cannot declare a parent")
    if kind != "root" and parent_key is None:
        raise ValueError("non-root command must declare a parent")


def _validate_leaf_execution(
    kind: CommandNodeKind,
    handler: LazyBinding | None,
    invocation: InvocationSpec,
) -> None:
    """Validate handler and chaining invariants owned by command leaves."""
    if kind == "leaf" and handler is None:
        raise ValueError("leaf command must declare a handler binding")
    if kind == "leaf" and invocation.chain:
        raise ValueError("leaf command cannot enable command chaining")


def _validate_callback_parameters(
    kind: CommandNodeKind,
    parameters: tuple[ParameterSpec, ...],
    invocation: InvocationSpec,
) -> None:
    """Reject callback parameters on non-executable groups."""
    if kind != "leaf" and parameters and not invocation.invoke_without_command:
        raise ValueError("non-executable groups cannot declare callback parameters")


def _validate_terminal_execution(
    kind: CommandNodeKind,
    handler: LazyBinding | None,
    invocation: InvocationSpec,
) -> None:
    """Validate terminal invocation, handler, and context relationships."""
    _validate_terminal_handler(handler, invocation)
    _validate_terminal_classification(invocation)
    _validate_terminal_context(invocation)
    _validate_metadata_group_handler(kind, handler, invocation)


def _validate_terminal_handler(handler: LazyBinding | None, invocation: InvocationSpec) -> None:
    """Require a handler whenever a node invokes without a child command."""
    if invocation.invoke_without_command and handler is None:
        raise ValueError("executable root/group must declare a handler binding")


def _validate_terminal_classification(invocation: InvocationSpec) -> None:
    """Require terminal behavior exactly when invocation skips child dispatch."""
    if invocation.invoke_without_command and invocation.terminal_behavior is None:
        raise ValueError("invoke-without-command nodes must classify terminal behavior")
    if not invocation.invoke_without_command and invocation.terminal_behavior is not None:
        raise ValueError("non-terminal nodes cannot classify terminal behavior")


def _validate_terminal_context(invocation: InvocationSpec) -> None:
    """Require context injection for executable terminal groups."""
    if invocation.terminal_behavior == "executable" and invocation.context_parameter is None:
        raise ValueError("terminal executable groups require an invocation context")


def _validate_metadata_group_handler(
    kind: CommandNodeKind,
    handler: LazyBinding | None,
    invocation: InvocationSpec,
) -> None:
    """Keep metadata-only root/group nodes free of handler bindings."""
    if not invocation.invoke_without_command and kind != "leaf" and handler is not None:
        raise ValueError("metadata-only root/group cannot declare a handler binding")


def _validate_unique_parameter_names(parameters: tuple[ParameterSpec, ...]) -> tuple[str, ...]:
    """Return parameter names after refusing duplicate command fields."""
    parameter_names = tuple(parameter.name for parameter in parameters)
    if len(parameter_names) != len(set(parameter_names)):
        raise ValueError("command parameter names must be unique")
    return parameter_names


def _validate_profile_target_parameter(profile_target_parameter: str | None, parameter_names: tuple[str, ...]) -> None:
    """Require a configured profile target to identify a declared parameter."""
    if profile_target_parameter is not None:
        _require_identifier(profile_target_parameter, field="profile target parameter")
        if profile_target_parameter not in parameter_names:
            raise ValueError("profile target parameter must reference a declared command parameter")


def _validate_unique_option_tokens(parameters: tuple[ParameterSpec, ...]) -> None:
    """Refuse aliases reused by more than one command option."""
    option_tokens = [
        declaration
        for parameter in parameters
        if isinstance(parameter, OptionSpec)
        for declaration in parameter.declarations
    ]
    if len(option_tokens) != len(set(option_tokens)):
        raise ValueError("command option tokens must be unique")


def _validate_search_terms(search_terms: tuple[str, ...]) -> None:
    """Require every semantic command-search term to contain non-whitespace text."""
    if any(not term.strip() for term in search_terms):
        raise ValueError("command search terms must be non-empty")


def _validate_parameter_declarations(
    parameters: tuple[ParameterSpec, ...],
    profile_target_parameter: str | None,
    search_terms: tuple[str, ...],
) -> tuple[str, ...]:
    """Validate parameter identity, option tokens, profile target, and search terms."""
    parameter_names = _validate_unique_parameter_names(parameters)
    _validate_profile_target_parameter(profile_target_parameter, parameter_names)
    _validate_unique_option_tokens(parameters)
    _validate_search_terms(search_terms)
    return parameter_names


def _validate_machine_secret_presence(
    machine_secret: MachineSecretSpec | None,
    secret_channels: tuple[MachineSecretChannelKind, ...],
) -> None:
    """Require a machine-secret contract when options expose its channels."""
    if machine_secret is None and secret_channels:
        raise ValueError("machine-secret channel parameters require a machine-secret spec")


def _validate_machine_secret_shape(
    kind: CommandNodeKind,
    machine_secret: MachineSecretSpec | None,
    secret_channels: tuple[MachineSecretChannelKind, ...],
) -> None:
    """Require machine-secret contracts to belong to leaves with both channels."""
    if machine_secret is None:
        return
    if kind != "leaf":
        raise ValueError("machine-secret specs belong only to command leaves")
    if (
        secret_channels.count(MachineSecretChannelKind.STDIN) != 1
        or secret_channels.count(MachineSecretChannelKind.FILE_DESCRIPTOR) != 1
    ):
        raise ValueError("machine-secret spec requires exactly one stdin and file-descriptor channel")


def _validate_machine_secret_conditions(
    parameters: tuple[ParameterSpec, ...],
    machine_secret: MachineSecretSpec | None,
) -> None:
    """Require every machine-secret variant condition to name a command option."""
    if machine_secret is None:
        return
    declared_names = {parameter.name for parameter in parameters}
    for variant in machine_secret.variants:
        if variant.condition is not None and variant.condition.option_name not in declared_names:
            raise ValueError("machine-secret condition must reference a command parameter")


def _validate_machine_secret_contract(
    kind: CommandNodeKind,
    parameters: tuple[ParameterSpec, ...],
    machine_secret: MachineSecretSpec | None,
    secret_channels: tuple[MachineSecretChannelKind, ...],
) -> None:
    """Validate leaf machine-secret ownership and channel references."""
    _validate_machine_secret_presence(machine_secret, secret_channels)
    _validate_machine_secret_shape(kind, machine_secret, secret_channels)
    _validate_machine_secret_conditions(parameters, machine_secret)


def _validate_profile_secret_contract(
    kind: CommandNodeKind,
    machine_secret: MachineSecretSpec | None,
    profile_secret: ProfileSecretSpec | None,
    profile_secret_channels: tuple[ProfileSecretChannelKind, ...],
) -> None:
    """Validate root profile-secret ownership and channel cardinality."""
    if profile_secret is None and profile_secret_channels:
        raise ValueError("profile-secret channel parameters require a profile-secret spec")
    if profile_secret is None:
        return
    if kind != "root":
        raise ValueError("profile-secret specs belong only to the executable root")
    if machine_secret is not None:
        raise ValueError("root profile-secret channels cannot own a leaf machine-secret spec")
    if (
        profile_secret_channels.count(ProfileSecretChannelKind.STDIN) != 1
        or profile_secret_channels.count(ProfileSecretChannelKind.FILE_DESCRIPTOR) != 1
    ):
        raise ValueError("root profile-secret contract requires exactly one stdin and file-descriptor channel")


def _validate_recovery_presence(parameter_names: tuple[str, ...], recovery_handoff: RecoveryHandoffSpec | None) -> None:
    """Require a recovery contract when descriptor options are declared."""
    recovery_parameter_names = {"recovery_handoff_fd", "recovery_verification_fd"}
    declared_recovery_parameters = recovery_parameter_names.intersection(parameter_names)
    if declared_recovery_parameters and recovery_handoff is None:
        raise ValueError("recovery descriptor parameters require a recovery handoff spec")


def _validate_recovery_shape(kind: CommandNodeKind, recovery_handoff: RecoveryHandoffSpec | None) -> None:
    """Keep recovery handoff contracts on command leaves."""
    if recovery_handoff is not None and kind != "leaf":
        raise ValueError("recovery handoff specs belong only to command leaves")


def _recovery_references(
    parameter_names: tuple[str, ...],
    recovery_handoff: RecoveryHandoffSpec,
) -> set[str]:
    """Return and validate all command parameters named by a recovery contract."""
    referenced = {
        recovery_handoff.handoff_parameter,
        recovery_handoff.verification_parameter,
        *recovery_handoff.collides_with_parameters,
    }
    if not referenced.issubset(parameter_names):
        raise ValueError("recovery handoff spec references a missing command parameter")
    return referenced


def _recovery_descriptor_parameters(
    parameters: tuple[ParameterSpec, ...],
    referenced: set[str],
) -> dict[str, OptionSpec]:
    """Resolve recovery references to command options, refusing other parameter kinds."""
    descriptor_parameters = {
        parameter.name: parameter
        for parameter in parameters
        if isinstance(parameter, OptionSpec) and parameter.name in referenced
    }
    if descriptor_parameters.keys() != referenced:
        raise ValueError("recovery handoff parameters must be command options")
    return descriptor_parameters


def _validate_recovery_integer_options(descriptor_parameters: dict[str, OptionSpec]) -> None:
    """Require every recovery descriptor option to carry an integer value contract."""
    if any(
        parameter.value.annotation != DeferredTarget("builtins", "int") for parameter in descriptor_parameters.values()
    ):
        raise ValueError("recovery handoff parameters must be integer options")


def _validate_recovery_handoff_contract(
    kind: CommandNodeKind,
    parameters: tuple[ParameterSpec, ...],
    parameter_names: tuple[str, ...],
    recovery_handoff: RecoveryHandoffSpec | None,
) -> None:
    """Validate recovery descriptor ownership, references, and integer options."""
    _validate_recovery_presence(parameter_names, recovery_handoff)
    if recovery_handoff is None:
        return
    _validate_recovery_shape(kind, recovery_handoff)
    referenced = _recovery_references(parameter_names, recovery_handoff)
    descriptor_parameters = _recovery_descriptor_parameters(parameters, referenced)
    _validate_recovery_integer_options(descriptor_parameters)


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
        _validate_command_identity(self.key, self.parent_key, self.token, self.kind)
        _validate_leaf_execution(self.kind, self.handler, self.invocation)
        _validate_callback_parameters(self.kind, self.parameters, self.invocation)
        _validate_terminal_execution(self.kind, self.handler, self.invocation)
        parameter_names = _validate_parameter_declarations(
            self.parameters,
            self.profile_target_parameter,
            self.search_terms,
        )
        secret_channels = tuple(
            parameter.machine_secret_channel
            for parameter in self.parameters
            if isinstance(parameter, OptionSpec) and parameter.machine_secret_channel is not None
        )
        profile_secret_channels = tuple(
            parameter.profile_secret_channel
            for parameter in self.parameters
            if isinstance(parameter, OptionSpec) and parameter.profile_secret_channel is not None
        )
        _validate_machine_secret_contract(
            self.kind,
            self.parameters,
            self.machine_secret,
            secret_channels,
        )
        _validate_profile_secret_contract(
            self.kind,
            self.machine_secret,
            self.profile_secret,
            profile_secret_channels,
        )
        _validate_recovery_handoff_contract(
            self.kind,
            self.parameters,
            parameter_names,
            self.recovery_handoff,
        )


@dataclass(frozen=True, slots=True)
class CommandSpecNode:
    """One graph node with its uniquely derived operator path."""

    path: tuple[str, ...]
    spec: CommandSpec


def _validate_graph_shape(specs: tuple[CommandSpec, ...]) -> dict[str, CommandSpec]:
    """Require a non-empty graph with one root and unique command keys."""
    if not specs:
        raise ValueError("command spec graph cannot be empty")
    by_key = {spec.key: spec for spec in specs}
    if len(by_key) != len(specs):
        raise ValueError("command spec keys must be unique")
    roots = tuple(spec for spec in specs if spec.parent_key is None)
    if len(roots) != 1:
        raise ValueError("command spec graph must declare exactly one root")
    return by_key


def _validate_graph_parent_edges(specs: tuple[CommandSpec, ...], by_key: dict[str, CommandSpec]) -> None:
    """Require every parent edge to name a non-leaf command."""
    for spec in specs:
        if spec.parent_key is not None and spec.parent_key not in by_key:
            raise ValueError(f"command spec {spec.key!r} has unknown parent {spec.parent_key!r}")
        if spec.parent_key is not None and by_key[spec.parent_key].kind == "leaf":
            raise ValueError(f"leaf command {spec.parent_key!r} cannot own children")


def _derive_graph_paths(by_key: dict[str, CommandSpec]) -> dict[str, tuple[str, ...]]:
    """Derive every operator path while refusing parent cycles."""
    paths: dict[str, tuple[str, ...]] = {}
    visiting: set[str] = set()

    def derive_path(key: str) -> tuple[str, ...]:
        if key in paths:
            return paths[key]
        if key in visiting:
            raise ValueError("command spec parent edges contain a cycle")
        visiting.add(key)
        spec = by_key[key]
        parent_path = () if spec.parent_key is None else derive_path(spec.parent_key)
        path = (*parent_path, spec.token)
        visiting.remove(key)
        paths[key] = path
        return path

    for key in by_key:
        derive_path(key)
    return paths


def _validate_graph_path_uniqueness(paths: dict[str, tuple[str, ...]]) -> None:
    """Require every graph node to have a unique derived operator path."""
    if len(set(paths.values())) != len(paths):
        raise ValueError("command spec operator paths must be unique")


@dataclass(frozen=True, slots=True)
class CommandSpecGraph:
    """Validated immutable tree assembled from distributed specifications."""

    specs: tuple[CommandSpec, ...]

    def __post_init__(self) -> None:
        """Validate key uniqueness, single root, parent references, and path uniqueness, or raise."""
        by_key = _validate_graph_shape(self.specs)
        _validate_graph_parent_edges(self.specs, by_key)
        paths = _derive_graph_paths(by_key)
        _validate_graph_path_uniqueness(paths)

    def by_key(self) -> MappingProxyType[str, CommandSpec]:
        """Return every command spec indexed by its key."""
        return MappingProxyType({spec.key: spec for spec in self.specs})

    def nodes(self) -> tuple[CommandSpecNode, ...]:
        """Return every command spec paired with its derived operator path."""
        by_key = self.by_key()

        def path_for(spec: CommandSpec) -> tuple[str, ...]:
            tokens = [spec.token]
            parent_key = spec.parent_key
            while parent_key is not None:
                parent = by_key[parent_key]
                tokens.append(parent.token)
                parent_key = parent.parent_key
            return tuple(reversed(tokens))

        return tuple(sorted((CommandSpecNode(path_for(spec), spec) for spec in self.specs), key=lambda node: node.path))

    def by_path(self) -> MappingProxyType[tuple[str, ...], CommandSpec]:
        """Return the exact derived operator-path index."""
        return MappingProxyType({node.path: node.spec for node in self.nodes()})

    def resolve_path(self, path: tuple[str, ...]) -> CommandSpec:
        """Resolve one complete operator path, failing closed on absence."""
        try:
            return self.by_path()[path]
        except KeyError as error:
            raise LookupError(f"unknown command spec path: {' '.join(path)!r}") from error

    def by_schema_identity(self) -> MappingProxyType[str, CommandSpec]:
        """Return the unique executable result-schema identity index."""
        rows = {
            spec.result_schema.identity: spec
            for spec in self.specs
            if spec.result_schema.state is SchemaState.TARGET and spec.result_schema.identity is not None
        }
        expected = sum(spec.result_schema.state is SchemaState.TARGET for spec in self.specs)
        if len(rows) != expected:
            raise ValueError("command result-schema identities must be unique")
        return MappingProxyType(rows)


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
