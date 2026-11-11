"""Declarative command specs for the ledger counterparty CLI commands."""

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
from cadrumo_client.commands.spec import CommandSpec, InvocationSpec
from cadrumo_client.contracts.command_ports import CommandNodeKind

from .app_ledger_command_spec_policies import (
    POLICY_4,
    POLICY_5,
)
from .app_ledger_command_spec_support import (
    blank_default_text_option,
    boolean_flag_option,
    optional_text_option,
    required_text_argument,
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
            required_text_argument("tax_identifier", "cli.app.ledger.counterparty.tax_identifier_help"),
            OptionSpec(
                name="scope",
                declarations=("--scope",),
                value=ValueContract(
                    DeferredTarget("...domain.iva.schema", "IvaTerritorialScope", __package__),
                    parser=DeferredTarget(".common", "IVA_TERRITORIAL_SCOPE_CHOICE", __package__),
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
                    parser=DeferredTarget(".common", "EU_MEMBER_STATE_CHOICE", __package__),
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
            optional_text_option("country_code", ("--country-code",), "cli.app.ledger.counterparty.country_code_help"),
            blank_default_text_option("note", ("--note",), "cli.app.ledger.counterparty.note_help"),
            optional_text_option("actor", ("--actor",), "cli.app.ledger.counterparty.actor_help"),
        ),
        policy=POLICY_4,
        handler=LazyBinding.available(
            DeferredTarget(".ledger_counterparty_commands", "counterparty_confirm", __package__)
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".ledger_counterparty_results", "CounterpartyConfirmResult", __package__),
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
            required_text_argument("tax_identifier", "cli.app.ledger.counterparty.tax_identifier_help"),
            optional_text_option("country_code", ("--country-code",), "cli.app.ledger.counterparty.country_code_help"),
            OptionSpec(
                name="evidenced_scope",
                declarations=("--evidenced-scope",),
                value=ValueContract(
                    DeferredTarget("...domain.iva.schema", "IvaTerritorialScope", __package__),
                    parser=DeferredTarget(".common", "IVA_TERRITORIAL_SCOPE_CHOICE", __package__),
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
        policy=POLICY_5,
        handler=LazyBinding.available(
            DeferredTarget(".ledger_counterparty_commands", "counterparty_view", __package__)
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".ledger_counterparty_results", "CounterpartyViewResult", __package__),
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
            required_text_argument("tax_identifier", "cli.app.ledger.counterparty.tax_identifier_help"),
            optional_text_option("country_code", ("--country-code",), "cli.app.ledger.counterparty.country_code_help"),
        ),
        policy=POLICY_4,
        handler=LazyBinding.available(
            DeferredTarget(".ledger_counterparty_commands", "counterparty_withdraw", __package__)
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".ledger_counterparty_results", "CounterpartyWithdrawResult", __package__),
            identity="ledger.counterparty.withdraw",
        ),
    ),
    CommandSpec(
        "app_ledger_counterparty_filing_name",
        "app_ledger_counterparty",
        "filing-name",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.ledger.counterparty.filing_name_help"),
        short_help_key=None,
        invocation=InvocationSpec(invoke_without_command=False, no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            required_text_argument("tax_identifier", "cli.app.ledger.counterparty.tax_identifier_help"),
            OptionSpec(
                name="kind",
                declarations=("--kind",),
                value=ValueContract(
                    DeferredTarget("...domain.filing.declared_party_name", "DeclaredPartyKind", __package__)
                ),
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.app.ledger.counterparty.party_kind_help"),
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
            optional_text_option(
                "primer_apellido", ("--primer-apellido",), "cli.app.ledger.counterparty.primer_apellido_help"
            ),
            optional_text_option(
                "segundo_apellido", ("--segundo-apellido",), "cli.app.ledger.counterparty.segundo_apellido_help"
            ),
            boolean_flag_option(
                "no_second_surname", ("--no-second-surname",), "cli.app.ledger.counterparty.no_second_surname_help"
            ),
            optional_text_option("nombre", ("--nombre",), "cli.app.ledger.counterparty.nombre_help"),
            optional_text_option("razon_social", ("--razon-social",), "cli.app.ledger.counterparty.razon_social_help"),
            OptionSpec(
                name="rendering",
                declarations=("--rendering",),
                value=ValueContract(
                    DeferredTarget(
                        "...application.ledger.counterparty_operation", "CounterpartyFilingNameRendering", __package__
                    ),
                    parser=DeferredTarget(
                        ".ledger_counterparty_filing_name_commands", "parse_filing_name_rendering", __package__
                    ),
                ),
                default=ParameterDefault.value(()),
                help_key=TranslationKey("cli.app.ledger.counterparty.rendering_help"),
                metavar="WIDTH=TEXT",
                is_flag=False,
                flag_value=None,
                multiple=True,
                count=False,
                eager=False,
                constraint=ParameterConstraint(),
                show_default=True,
                hidden=False,
            ),
            optional_text_option("country_code", ("--country-code",), "cli.app.ledger.counterparty.country_code_help"),
            optional_text_option("actor", ("--actor",), "cli.app.ledger.counterparty.actor_help"),
        ),
        policy=POLICY_4,
        handler=LazyBinding.available(
            DeferredTarget(".ledger_counterparty_filing_name_commands", "counterparty_filing_name", __package__)
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".ledger_counterparty_results", "CounterpartyFilingNameResult", __package__),
            identity="ledger.counterparty.filing_name",
        ),
    ),
)

__all__ = ["LEDGER_COUNTERPARTY_COMMAND_SPECS"]
"""Authored CommandSpec declarations for the ledger counterparty surface."""
"""Authored CommandSpec declarations for the ledger counterparty surface."""
