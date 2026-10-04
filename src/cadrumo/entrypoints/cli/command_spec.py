"""Import-light immutable authority for executable command nodes and execution policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal, cast

from ...application.operator_surface.command_ports import (
    CommandNodeKind,
    CommandWriteRouteValue,
    ProfileAuthenticationPosture,
)
from ._command_parameter_validation import (
    require_identifier,
    require_token,
    validate_machine_secret_contract,
    validate_parameter_declarations,
    validate_profile_secret_contract,
)
from ._command_policy_validation import (
    expanded_capabilities,
    validate_policy_destructive,
    validate_policy_effect_capabilities,
    validate_policy_exclusive_values,
    validate_policy_handoff,
    validate_policy_live_write,
    validate_policy_membership,
    validate_policy_types,
    validate_policy_write_route,
)
from ._command_secret_contracts import MachineSecretSpec, ProfileSecretSpec, RecoveryHandoffSpec
from ._command_structure_validation import (
    validate_callback_parameters,
    validate_command_identity,
    validate_command_spec,
    validate_leaf_execution,
    validate_recovery_handoff_contract,
    validate_terminal_execution,
)
from .command_parameter_contracts import ParameterSpec
from .command_shared_contracts import (
    Capability,
    LazyBinding,
    PerformanceClass,
    ResultSchemaSpec,
    SideEffect,
    TranslationKey,
)

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
        validate_policy_types(
            self.capabilities,
            self.side_effects,
            self.destructive,
            self.handoff,
            self.live_write,
        )
        validate_policy_membership(self.capabilities, self.side_effects, self.performance, self.write_route)
        validate_policy_exclusive_values(self.capabilities, self.side_effects)
        expanded = self.expanded_capabilities
        validate_policy_effect_capabilities(self.side_effects, expanded)
        validate_policy_write_route(self.write_route, self.side_effects, expanded)
        validate_policy_destructive(self.destructive, self.side_effects)
        validate_policy_handoff(self.handoff, expanded, self.side_effects)
        validate_policy_live_write(self.live_write, expanded, self.side_effects)

    @property
    def expanded_capabilities(self) -> frozenset[Capability]:
        """Return the transitive capability closure used by import gates."""
        return cast(frozenset[Capability], expanded_capabilities(self.capabilities))


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
            require_identifier(self.context_parameter, field="invocation context parameter")


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
        validate_command_spec(
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
            require_identifier=require_identifier,
            require_token=require_token,
            validate_identity=validate_command_identity,
            validate_leaf=validate_leaf_execution,
            validate_callbacks=validate_callback_parameters,
            validate_terminal=validate_terminal_execution,
            validate_parameters=validate_parameter_declarations,
            validate_machine_secret=validate_machine_secret_contract,
            validate_profile_secret=validate_profile_secret_contract,
            validate_recovery=validate_recovery_handoff_contract,
        )


@dataclass(frozen=True, slots=True)
class CommandSpecNode:
    """One graph node with its uniquely derived operator path."""

    path: tuple[str, ...]
    spec: CommandSpec
