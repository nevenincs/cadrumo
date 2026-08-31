"""Authored CommandSpec declarations for the ledger participation surface."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from ._app_ledger_command_spec_policies import (
    _POLICY_3,
)
from .command_spec import (
    CommandSpec,
    DeferredTarget,
    InvocationSpec,
    LazyBinding,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
)

LEDGER_PARTICIPATION_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_ledger_participation_rebuild",
        parent_key="app_ledger_participation",
        token="rebuild",
        kind="leaf",
        help_key=TranslationKey("cli.ledger.participation.rebuild_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(),
        policy=_POLICY_3,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._participation_cli", "participation_rebuild")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._ledger_payloads", "LedgerParticipationRebuildResult"),
            identity="ledger.participation.rebuild",
        ),
    ),
)

__all__ = ["LEDGER_PARTICIPATION_COMMAND_SPECS"]
