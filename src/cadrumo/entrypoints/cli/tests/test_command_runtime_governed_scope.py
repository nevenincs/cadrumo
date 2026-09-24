"""Dispatch runs a governed-fact-reading command inside its pinned authority scope.

A handler that opens its own scope can forget to, and one that leans on an
earlier lease is correct only in the session posture that took it. Dispatch
therefore opens the invocation's scope for every runnable command whose policy
declares a capability that reads governed facts, and for no other.

The synthetic graph below runs through the real runtime compiler with no
enclosing scope, so a handler sees exactly what dispatch gave it.
"""

from __future__ import annotations

from typing import Final

import pytest
from typer.testing import CliRunner

from cadrumo.application.operator_surface.command_ports import CommandNodeKind, CommandWriteRoute

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.governed_fact_scope import (
    GovernedFactSource,
    governed_facts_in_scope,
    outside_governed_fact_validation,
)
from .._command_runtime import GOVERNED_FACT_SCOPE_CAPABILITIES, build_command_app, runs_in_governed_fact_scope
from ..command_spec import (
    Capability,
    CommandSpec,
    CommandSpecGraph,
    DeferredTarget,
    ExecutionPolicySpec,
    InvocationSpec,
    LazyBinding,
    PerformanceClass,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
)
from ..command_specs import COMMAND_GRAPH

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_SEEN: list[GovernedFactSource | None] = []
_HELP: Final = TranslationKey("cli.root.version_help")
_NO_SCHEMA: Final = ResultSchemaSpec(SchemaState.NOT_SUPPORTED)


def record_governed_scope(ctx: object) -> None:
    """Record the governed facts the handler can reach, and nothing else."""
    del ctx
    _SEEN.append(governed_facts_in_scope())


def _policy(capability: Capability, performance: PerformanceClass) -> ExecutionPolicySpec:
    return ExecutionPolicySpec(
        capabilities=frozenset({capability}),
        side_effects=frozenset({"none"}),
        performance=performance,
        write_route=CommandWriteRoute.NONE,
    )


def _leaf(token: str, policy: ExecutionPolicySpec) -> CommandSpec:
    return CommandSpec(
        token.replace("-", "_"),
        "root",
        token,
        kind=CommandNodeKind.LEAF,
        help_key=_HELP,
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(),
        policy=policy,
        handler=LazyBinding.available(
            DeferredTarget(".test_command_runtime_governed_scope", "record_governed_scope", __package__),
        ),
        result_schema=_NO_SCHEMA,
    )


def _graph() -> CommandSpecGraph:
    root = CommandSpec(
        "root",
        None,
        "aeat",
        kind=CommandNodeKind.ROOT,
        help_key=TranslationKey("cli.root.app_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=_policy("state-free", "metadata"),
        handler=None,
        result_schema=_NO_SCHEMA,
    )
    return CommandSpecGraph(
        (
            root,
            _leaf("encrypted-read", _policy("encrypted-facts", "local-io")),
            _leaf("registry-read", _policy("registry", "local-io")),
            _leaf("state-free-read", _policy("state-free", "metadata")),
        ),
    )


def _scope_seen_by(token: str) -> GovernedFactSource | None:
    _SEEN.clear()
    with outside_governed_fact_validation():
        result = CliRunner().invoke(build_command_app(_graph()), [token])
    assert result.exit_code == 0, result.output
    assert len(_SEEN) == 1
    return _SEEN[0]


@pytest.mark.parametrize("token", ["encrypted-read", "registry-read"])
def test_a_governed_fact_capability_runs_its_handler_inside_the_pinned_scope(token: str) -> None:
    assert isinstance(_scope_seen_by(token), PinnedAuthorityOperation)


def test_a_state_free_command_is_not_given_a_scope() -> None:
    assert _scope_seen_by("state-free-read") is None


def test_every_runnable_governed_fact_command_is_reachable_by_the_seam() -> None:
    """Count the live commands dispatch scopes, and refuse one it cannot reach."""
    runnable = [
        spec
        for spec in COMMAND_GRAPH.specs
        if spec.kind == CommandNodeKind.LEAF
        or (spec.kind == CommandNodeKind.GROUP and spec.invocation.terminal_behavior == "executable")
    ]
    declaring = [
        spec for spec in runnable if not spec.policy.expanded_capabilities.isdisjoint(GOVERNED_FACT_SCOPE_CAPABILITIES)
    ]
    covered = [spec for spec in declaring if runs_in_governed_fact_scope(spec)]

    assert len(covered) > 0
    assert [spec.key for spec in declaring if spec not in covered] == []


#: Commands found reading governed facts before any scope existed: each one
#: refused, or passed only when an earlier lease in the same session lent one.
_FORMERLY_UNSCOPED_COMMANDS: Final = (
    "app_ledger_rule_add",
    "app_quickfile",
    "app_modelo_export",
    "app_modelo_review_package_build",
    "app_modelo_iva_wallet_balance",
    "config_profile_censo_pull",
)


@pytest.mark.parametrize("key", _FORMERLY_UNSCOPED_COMMANDS)
def test_a_formerly_unscoped_command_now_runs_inside_the_seam(key: str) -> None:
    """Pin each known reader to the seam, so a policy edit cannot silently drop it."""
    spec = next(spec for spec in COMMAND_GRAPH.specs if spec.key == key)

    assert runs_in_governed_fact_scope(spec), sorted(spec.policy.expanded_capabilities)
