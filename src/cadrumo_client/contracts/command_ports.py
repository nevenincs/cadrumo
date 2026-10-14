"""Inward command-surface ports consumed by outer composition roots.

The command graph is an outer concern, but the values exchanged with another
composition root are application contracts.  Keeping these records here lets
the CLI and the retained harness share one schema, policy, and dispatch
vocabulary without either side importing the other.  Implementations remain
free to resolve their own command graph; this module contains no Typer, Click,
entrypoint, or process-launching code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

# The command graph's declarations are built from this vocabulary at import, so
# it stays free of pydantic; the validated verb-input records that outer roots
# exchange live in :mod:`.verb_input_contracts`.


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
    "SideEffect",
]
