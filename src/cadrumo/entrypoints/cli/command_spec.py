"""Import-light immutable authority for executable command nodes and execution policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal, cast

from ...application.operator_surface.command_ports import (
    CommandNodeKind,
    CommandWriteRouteValue,
    ProfileAuthenticationPosture,
)
from ._command_parameter_contracts import ParameterSpec
from ._command_parameter_validation import require_identifier as _require_identifier
from ._command_parameter_validation import require_token as _require_token
from ._command_parameter_validation import validate_machine_secret_contract as _validate_machine_secret_contract
from ._command_parameter_validation import validate_parameter_declarations as _validate_parameter_declarations
from ._command_parameter_validation import validate_profile_secret_contract as _validate_profile_secret_contract
from ._command_policy_validation import expanded_capabilities as _expanded_capabilities
from ._command_policy_validation import validate_policy_destructive as _validate_policy_destructive
from ._command_policy_validation import validate_policy_effect_capabilities as _validate_policy_effect_capabilities
from ._command_policy_validation import validate_policy_exclusive_values as _validate_policy_exclusive_values
from ._command_policy_validation import validate_policy_handoff as _validate_policy_handoff
from ._command_policy_validation import validate_policy_live_write as _validate_policy_live_write
from ._command_policy_validation import validate_policy_membership as _validate_policy_membership
from ._command_policy_validation import validate_policy_types as _validate_policy_types
from ._command_policy_validation import validate_policy_write_route as _validate_policy_write_route
from ._command_secret_contracts import MachineSecretSpec, ProfileSecretSpec, RecoveryHandoffSpec
from ._command_shared_contracts import (
    Capability,
    LazyBinding,
    PerformanceClass,
    ResultSchemaSpec,
    SideEffect,
    TranslationKey,
)
from ._command_structure_validation import validate_callback_parameters as _validate_callback_parameters
from ._command_structure_validation import validate_command_identity as _validate_command_identity
from ._command_structure_validation import validate_command_spec as _validate_command_spec
from ._command_structure_validation import validate_leaf_execution as _validate_leaf_execution
from ._command_structure_validation import validate_recovery_handoff_contract as _validate_recovery_handoff_contract
from ._command_structure_validation import validate_terminal_execution as _validate_terminal_execution

NON_LEAF_COMMAND_KINDS: Final[frozenset[CommandNodeKind]] = frozenset(
    {CommandNodeKind.ROOT, CommandNodeKind.GROUP},
)
"""The kinds that carry children.

Derived from the members rather than relisted. A node kind added to the tree cannot be
silently omitted here, which a hand-written pair invited -- and this pair was written
twice, in two comprehensions of one reconciliation module."""


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
    repairs_active_profile_pointer: bool = False
    """Whether this leaf repairs the active-profile pointer, so it must run while that record is corrupt."""

    def __post_init__(self) -> None:
        """Validate the command node's identity, hierarchy, and dispatch invariants, or raise."""
        if self.repairs_active_profile_pointer and self.kind != "leaf":
            raise ValueError(f"{self.key}: only an executable leaf can repair the active-profile pointer")
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
