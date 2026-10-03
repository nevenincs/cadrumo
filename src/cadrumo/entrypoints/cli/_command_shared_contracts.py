"""Immutable deferred targets, values, defaults, schemas, and command vocabulary."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from importlib.util import resolve_name
from typing import Final, Literal

from ...application.operator_surface.command_ports import (
    CommandWriteRoute as CommandWriteRoute,
)
from ._command_parameter_validation import require_token as _require_token
from ._command_parameter_validation import validate_not_supported_schema as _validate_not_supported_schema
from ._command_parameter_validation import validate_target_schema as _validate_target_schema
from ._command_parameter_validation import validate_unavailable_schema as _validate_unavailable_schema
from ._command_policy_validation import validate_deferred_target as _validate_deferred_target
from ._command_policy_validation import validate_lazy_binding as _validate_lazy_binding
from ._command_policy_validation import validate_parameter_constraint as _validate_parameter_constraint
from ._command_policy_validation import validate_parameter_default as _validate_parameter_default
from ._command_policy_validation import validate_translation_key as _validate_translation_key
from ._command_policy_validation import validate_value_contract as _validate_value_contract
from ._command_structure_validation import validate_result_schema as _validate_result_schema

type LiteralValue = str | int | float | bool | bytes | None


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


@dataclass(frozen=True, slots=True)
class DeferredTarget:
    """A public Python object identity that is resolved only when selected."""

    module: str
    qualname: str
    package: str | None = None

    def __post_init__(self) -> None:
        """Validate and canonicalise a target anchored to its declaring package."""
        _validate_deferred_target(self.module, self.qualname, self.package)
        if self.module.startswith("."):
            if self.package is None:
                raise ValueError("relative deferred target modules require their importing package")
            object.__setattr__(self, "module", resolve_name(self.module, self.package))
        object.__setattr__(self, "package", None)

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


#: The three builtin value contracts every command surface declares. They are
#: immutable and carry no per-module state, so a module-local copy is a
#: duplicate definition rather than a convenience: eighteen modules each
#: declared their own `_STR` / `_INT` / `_BOOL` before these were centralised.
TEXT_VALUE: Final[ValueContract] = ValueContract(DeferredTarget("builtins", "str"))


WHOLE_NUMBER_VALUE: Final[ValueContract] = ValueContract(DeferredTarget("builtins", "int"))


FLAG_VALUE: Final[ValueContract] = ValueContract(DeferredTarget("builtins", "bool"))


PATH_VALUE: Final[ValueContract] = ValueContract(DeferredTarget("pathlib", "Path"))
