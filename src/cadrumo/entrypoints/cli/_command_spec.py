"""Import-light production authority for the executable CLI command graph.

This module contains declarations only.  It deliberately does not import
Typer, Click, handlers, schemas, translation catalogues, or development tools.
Runtime assemblers and non-runtime validators consume the same immutable
records and resolve deferred targets only at their owning boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Literal

type CommandNodeKind = Literal["root", "group", "leaf"]
type ParameterKind = Literal["argument", "option"]
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
type WriteRoute = Literal["none", "profile-bound", "bootstrap-root"]

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
_WRITE_ROUTES = frozenset({"none", "profile-bound", "bootstrap-root"})
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


@dataclass(frozen=True, slots=True)
class ExecutionPolicySpec:
    """Complete capability, effect, budget, risk, and write-route authority."""

    capabilities: frozenset[Capability]
    side_effects: frozenset[SideEffect]
    performance: PerformanceClass
    write_route: WriteRoute
    destructive: bool = False
    handoff: bool = False
    live_write: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.capabilities, frozenset):
            raise TypeError("execution policy capabilities must be a frozenset")
        if not isinstance(self.side_effects, frozenset):
            raise TypeError("execution policy side effects must be a frozenset")
        if any(not isinstance(value, bool) for value in (self.destructive, self.handoff, self.live_write)):
            raise TypeError("execution policy risk flags must be bools")
        if not self.capabilities or self.capabilities - _CAPABILITIES:
            raise ValueError("execution policy has missing or unknown capabilities")
        if not self.side_effects or self.side_effects - _SIDE_EFFECTS:
            raise ValueError("execution policy has missing or unknown side effects")
        if self.performance not in _PERFORMANCE_CLASSES:
            raise ValueError("execution policy has an unknown performance class")
        if self.write_route not in _WRITE_ROUTES:
            raise ValueError("execution policy has an unknown write route")
        if "state-free" in self.capabilities and self.capabilities != frozenset({"state-free"}):
            raise ValueError("state-free cannot be combined with authority capabilities")
        if "none" in self.side_effects and self.side_effects != frozenset({"none"}):
            raise ValueError("none cannot be combined with observable side effects")
        if self.capabilities == frozenset({"state-free"}) and self.side_effects != frozenset({"none"}):
            raise ValueError("state-free execution must be effect-free")
        expanded = self.expanded_capabilities
        required_by_effect = {"network": "network", "browser": "browser", "google": "google"}
        if any(
            effect in self.side_effects and capability not in expanded
            for effect, capability in required_by_effect.items()
        ):
            raise ValueError("execution policy side effect lacks its owning capability")
        if self.write_route != "none" and (
            "local-state" not in self.side_effects or "profile-custody" not in expanded
        ):
            raise ValueError("storage write routes require profile custody and local-state effects")
        if self.destructive and "local-state" not in self.side_effects:
            raise ValueError("destructive execution requires a local-state effect")
        if self.handoff and ("filing" not in expanded or "local-state" not in self.side_effects):
            raise ValueError("filing handoff requires filing authority and a local-state effect")
        if self.live_write and (
            "network" not in expanded
            or not self.side_effects.intersection({"network", "browser"})
        ):
            raise ValueError("live writes require network authority and a network/browser effect")

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
        if not self.module or any(not part.isidentifier() for part in self.module.split(".")):
            raise ValueError("deferred target module must be a dotted Python module name")
        if not self.qualname or any(not part.isidentifier() for part in self.qualname.split(".")):
            raise ValueError("deferred target qualname must be a dotted Python identifier")

    @property
    def identity(self) -> str:
        return f"{self.module}:{self.qualname}"


@dataclass(frozen=True, slots=True)
class TranslationKey:
    """A catalogue key; translated text never becomes structural authority."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or self.value.strip() != self.value or "." not in self.value:
            raise ValueError("translation key must be a non-empty dotted key")


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
        return cls(BindingState.TARGET, target=target, optional_dependencies=optional_dependencies)

    @classmethod
    def unavailable(cls, reason_key: TranslationKey) -> LazyBinding:
        return cls(BindingState.UNAVAILABLE, reason_key=reason_key)


class DefaultKind(Enum):
    REQUIRED = "required"
    LITERAL = "literal"
    FACTORY = "factory"


@dataclass(frozen=True, slots=True)
class ParameterDefault:
    """A required marker, immutable literal, or deferred default factory."""

    kind: DefaultKind
    literal: LiteralValue | tuple[LiteralValue, ...] = None
    factory: DeferredTarget | None = None

    def __post_init__(self) -> None:
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
        return cls(DefaultKind.REQUIRED)

    @classmethod
    def value(cls, value: LiteralValue | tuple[LiteralValue, ...]) -> ParameterDefault:
        return cls(DefaultKind.LITERAL, literal=value)

    @classmethod
    def from_factory(cls, target: DeferredTarget) -> ParameterDefault:
        return cls(DefaultKind.FACTORY, factory=target)


@dataclass(frozen=True, slots=True)
class ValueContract:
    """Deferred annotation and conversion hooks for one CLI parameter."""

    annotation: DeferredTarget
    click_type: DeferredTarget | None = None
    parser: DeferredTarget | None = None
    completion: DeferredTarget | None = None
    callback: DeferredTarget | None = None

    def __post_init__(self) -> None:
        if self.click_type is not None and self.parser is not None:
            raise ValueError("value contract cannot declare both a Click type and parser")


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
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValueError("parameter minimum cannot exceed maximum")
        if self.clamp and self.minimum is None and self.maximum is None:
            raise ValueError("clamping requires a minimum or maximum")


@dataclass(frozen=True, slots=True)
class ArgumentSpec:
    """One positional argument declaration, in command tuple order."""

    name: str
    value: ValueContract
    default: ParameterDefault
    help_key: TranslationKey
    metavar: str | None = None
    show_default: bool = True
    hidden: bool = False
    constraint: ParameterConstraint = ParameterConstraint()

    kind: ParameterKind = "argument"

    def __post_init__(self) -> None:
        _require_identifier(self.name, field="argument name")
        if self.metavar is not None:
            _require_token(self.metavar, field="argument metavar")


@dataclass(frozen=True, slots=True)
class OptionSpec:
    """One named option declaration including aliases and flag pairing."""

    name: str
    declarations: tuple[str, ...]
    value: ValueContract
    default: ParameterDefault
    help_key: TranslationKey
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

    kind: ParameterKind = "option"

    def __post_init__(self) -> None:
        _require_identifier(self.name, field="option name")
        if not self.declarations:
            raise ValueError("option must declare at least one CLI token")
        if len(set(self.declarations)) != len(self.declarations):
            raise ValueError("option declarations must be unique")
        for declaration in self.declarations:
            if not declaration.startswith("-"):
                raise ValueError("option declarations must begin with '-'")
            _require_token(declaration, field="option declaration")
        if self.metavar is not None:
            _require_token(self.metavar, field="option metavar")
        if self.count and (not self.is_flag or self.multiple):
            raise ValueError("counting options must be singular flags")
        if self.flag_value is not None and not self.is_flag:
            raise ValueError("flag values require is_flag")
        if len(set(self.envvar)) != len(self.envvar):
            raise ValueError("option environment variables must be unique")
        for variable in self.envvar:
            _require_token(variable, field="option environment variable")


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
    deprecated_key: TranslationKey | None = None
    context_parameter: str | None = None

    def __post_init__(self) -> None:
        if self.context_parameter is not None:
            _require_identifier(self.context_parameter, field="invocation context parameter")


class SchemaState(Enum):
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
        if self.state is SchemaState.TARGET:
            if self.target is None or self.reason_key is not None or self.identity is None:
                raise ValueError("schema target state requires an identity and target")
            parts = self.identity.split(".")
            if any(not part or any(character.isspace() for character in part) for part in parts):
                raise ValueError("schema identity must be a non-empty dotted token sequence")
        elif self.state is SchemaState.NOT_SUPPORTED:
            if self.target is not None or self.reason_key is not None or self.identity is not None:
                raise ValueError("unsupported schema state carries no identity, target, or reason")
        elif self.state is SchemaState.UNAVAILABLE and (
            self.target is not None or self.reason_key is None or self.identity is not None
        ):
            raise ValueError("unavailable schema state requires only a localized reason")


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

    def __post_init__(self) -> None:
        _require_identifier(self.key, field="command key")
        if self.parent_key is not None:
            _require_identifier(self.parent_key, field="command parent key")
        _require_token(self.token, field="command token")
        if self.kind not in {"root", "group", "leaf"}:
            raise ValueError(f"unknown command node kind: {self.kind}")
        if self.kind == "root" and self.parent_key is not None:
            raise ValueError("root command cannot declare a parent")
        if self.kind != "root" and self.parent_key is None:
            raise ValueError("non-root command must declare a parent")
        if self.kind == "leaf" and self.handler is None:
            raise ValueError("leaf command must declare a handler binding")
        if self.kind == "leaf" and self.invocation.chain:
            raise ValueError("leaf command cannot enable command chaining")
        if self.kind != "leaf" and self.parameters and not self.invocation.invoke_without_command:
            raise ValueError("non-executable groups cannot declare callback parameters")
        if self.invocation.invoke_without_command and self.handler is None:
            raise ValueError("executable root/group must declare a handler binding")
        if not self.invocation.invoke_without_command and self.kind != "leaf" and self.handler is not None:
            raise ValueError("metadata-only root/group cannot declare a handler binding")
        parameter_names = tuple(parameter.name for parameter in self.parameters)
        if len(parameter_names) != len(set(parameter_names)):
            raise ValueError("command parameter names must be unique")
        option_tokens = [
            declaration
            for parameter in self.parameters
            if isinstance(parameter, OptionSpec)
            for declaration in parameter.declarations
        ]
        if len(option_tokens) != len(set(option_tokens)):
            raise ValueError("command option tokens must be unique")


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
        if not self.specs:
            raise ValueError("command spec graph cannot be empty")
        by_key = {spec.key: spec for spec in self.specs}
        if len(by_key) != len(self.specs):
            raise ValueError("command spec keys must be unique")
        roots = tuple(spec for spec in self.specs if spec.parent_key is None)
        if len(roots) != 1:
            raise ValueError("command spec graph must declare exactly one root")
        for spec in self.specs:
            if spec.parent_key is not None and spec.parent_key not in by_key:
                raise ValueError(f"command spec {spec.key!r} has unknown parent {spec.parent_key!r}")
            if spec.parent_key is not None and by_key[spec.parent_key].kind == "leaf":
                raise ValueError(f"leaf command {spec.parent_key!r} cannot own children")

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
        if len(set(paths.values())) != len(paths):
            raise ValueError("command spec operator paths must be unique")

    def by_key(self) -> MappingProxyType[str, CommandSpec]:
        return MappingProxyType({spec.key: spec for spec in self.specs})

    def nodes(self) -> tuple[CommandSpecNode, ...]:
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
            if spec.result_schema.state is SchemaState.TARGET
            and spec.result_schema.identity is not None
        }
        expected = sum(spec.result_schema.state is SchemaState.TARGET for spec in self.specs)
        if len(rows) != expected:
            raise ValueError("command result-schema identities must be unique")
        return MappingProxyType(rows)


__all__ = [
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
    "LazyBinding",
    "LiteralValue",
    "OptionSpec",
    "ParameterConstraint",
    "ParameterDefault",
    "ParameterKind",
    "ParameterSpec",
    "ResultSchemaSpec",
    "SchemaState",
    "TranslationKey",
    "ValueContract",
]
