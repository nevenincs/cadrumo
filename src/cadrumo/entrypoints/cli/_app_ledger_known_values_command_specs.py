from __future__ import annotations

from cadrumo_client.commands.parameters import OptionSpec
from cadrumo_client.commands.shared_contracts import (
    DeferredTarget,
    LazyBinding,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)
from cadrumo_client.commands.spec import CommandSpec
from cadrumo_client.contracts.command_ports import CommandNodeKind

from ._app_ledger_command_spec_policies import _POLICY_5
from ._app_ledger_command_spec_support import _LEAF_INVOCATION

LEDGER_KNOWN_VALUES_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "app_ledger_known_values",
        "app_ledger",
        "known-values",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.ledger.known_values.help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            OptionSpec(
                name="kinds",
                declarations=("--kind",),
                value=ValueContract(DeferredTarget("...core.ledger_known_values", "LedgerKnownValueKind", __package__)),
                default=ParameterDefault.value(()),
                help_key=TranslationKey("cli.ledger.known_values.kind_help"),
                metavar=None,
                is_flag=False,
                flag_value=None,
                multiple=True,
                count=False,
                eager=False,
                constraint=ParameterConstraint(),
                show_default=True,
                hidden=False,
            ),
        ),
        policy=_POLICY_5,
        handler=LazyBinding.available(
            DeferredTarget(".operation_ledger_known_values", "ledger_known_values", __package__)
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".ledger_results", "LedgerKnownValuesResult", __package__),
            identity="ledger.known-values",
        ),
    ),
)

__all__ = ["LEDGER_KNOWN_VALUES_COMMAND_SPECS"]
