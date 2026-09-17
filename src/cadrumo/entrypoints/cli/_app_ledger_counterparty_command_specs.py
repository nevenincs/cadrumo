from __future__ import annotations

from cadrumo.application.operator_surface.command_ports import CommandNodeKind

from ._app_ledger_command_spec_policies import (
    _POLICY_4,
    _POLICY_5,
)
from ._app_ledger_command_spec_support import (
    _blank_default_text_option,
    _optional_text_option,
    _required_text_argument,
)
from .command_spec import (
    CommandSpec,
    DeferredTarget,
    InvocationSpec,
    LazyBinding,
    OptionSpec,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)

LEDGER_COUNTERPARTY_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "app_ledger_counterparty_confirm",
        "app_ledger_counterparty",
        "confirm",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.counterparty.confirm_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            _required_text_argument("tax_identifier", "cli.app.ledger.counterparty.tax_identifier_help"),
            OptionSpec(
                name="scope",
                declarations=("--scope",),
                value=ValueContract(
                    DeferredTarget("...domain.iva.classification", "IvaTerritorialScope", __package__),
                    click_type=DeferredTarget(".common", "IVA_TERRITORIAL_SCOPE_CHOICE", __package__),
                ),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.app.ledger.counterparty.scope_help"),
                metavar=None,
                is_flag=False,
                flag_value=None,
                multiple=False,
                count=False,
                eager=False,
                constraint=ParameterConstraint(),
                show_default=True,
                hidden=False,
            ),
            OptionSpec(
                name="identification_state",
                declarations=("--identification-state",),
                value=ValueContract(
                    DeferredTarget("...domain.iva.schema", "EUMemberState", __package__),
                    click_type=DeferredTarget(".common", "EU_MEMBER_STATE_CHOICE", __package__),
                ),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.app.ledger.counterparty.identification_state_help"),
                metavar=None,
                is_flag=False,
                flag_value=None,
                multiple=False,
                count=False,
                eager=False,
                constraint=ParameterConstraint(),
                show_default=True,
                hidden=False,
            ),
            _optional_text_option("country_code", ("--country-code",), "cli.app.ledger.counterparty.country_code_help"),
            _blank_default_text_option("note", ("--note",), "cli.app.ledger.counterparty.note_help"),
            _optional_text_option("actor", ("--actor",), "cli.app.ledger.counterparty.actor_help"),
        ),
        policy=_POLICY_4,
        handler=LazyBinding.available(DeferredTarget("._ledger_counterparty_cli", "counterparty_confirm", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("._ledger_counterparty_payloads", "CounterpartyConfirmResult", __package__),
            identity="ledger.counterparty.confirm",
        ),
    ),
    CommandSpec(
        "app_ledger_counterparty_view",
        "app_ledger_counterparty",
        "view",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.counterparty.view_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            _required_text_argument("tax_identifier", "cli.app.ledger.counterparty.tax_identifier_help"),
            _optional_text_option("country_code", ("--country-code",), "cli.app.ledger.counterparty.country_code_help"),
            OptionSpec(
                name="evidenced_scope",
                declarations=("--evidenced-scope",),
                value=ValueContract(
                    DeferredTarget("...domain.iva.classification", "IvaTerritorialScope", __package__),
                    click_type=DeferredTarget(".common", "IVA_TERRITORIAL_SCOPE_CHOICE", __package__),
                ),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.app.ledger.counterparty.evidenced_scope_help"),
                metavar=None,
                is_flag=False,
                flag_value=None,
                multiple=False,
                count=False,
                eager=False,
                constraint=ParameterConstraint(),
                show_default=True,
                hidden=False,
            ),
        ),
        policy=_POLICY_5,
        handler=LazyBinding.available(DeferredTarget("._ledger_counterparty_cli", "counterparty_view", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("._ledger_counterparty_payloads", "CounterpartyViewResult", __package__),
            identity="ledger.counterparty.view",
        ),
    ),
    CommandSpec(
        "app_ledger_counterparty_withdraw",
        "app_ledger_counterparty",
        "withdraw",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.counterparty.withdraw_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            _required_text_argument("tax_identifier", "cli.app.ledger.counterparty.tax_identifier_help"),
            _optional_text_option("country_code", ("--country-code",), "cli.app.ledger.counterparty.country_code_help"),
        ),
        policy=_POLICY_4,
        handler=LazyBinding.available(
            DeferredTarget("._ledger_counterparty_cli", "counterparty_withdraw", __package__)
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("._ledger_counterparty_payloads", "CounterpartyWithdrawResult", __package__),
            identity="ledger.counterparty.withdraw",
        ),
    ),
)

__all__ = ["LEDGER_COUNTERPARTY_COMMAND_SPECS"]
"""Authored CommandSpec declarations for the ledger counterparty surface."""
"""Authored CommandSpec declarations for the ledger counterparty surface."""
