"""Import-light command specifications for profile inventory and readiness."""

from __future__ import annotations

from cadrumo_client.commands.parameters import OptionSpec
from cadrumo_client.commands.shared_contracts import (
    DeferredTarget,
    LazyBinding,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)
from cadrumo_client.commands.spec import CommandSpec, InvocationSpec
from cadrumo_client.contracts.command_ports import CommandNodeKind

from ._spec_policies import CALCULATION_READ, PROFILE_READ

_OUTPUT_LANGUAGE = ValueContract(DeferredTarget("....core.external_constants", "OutputLanguage", __package__))
_OUTPUT_LANGUAGE_OPTION = OptionSpec(
    name="output_language",
    declarations=("--output-language", "--language"),
    value=_OUTPUT_LANGUAGE,
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.config.auth.output_language_help"),
)


PROFILE_INVENTORY_COMMAND_SPECS = (
    CommandSpec(
        "config_profile_list",
        "config_profile",
        "list",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.list.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_OUTPUT_LANGUAGE_OPTION,),
        policy=PROFILE_READ,
        handler=LazyBinding.available(DeferredTarget(".profile_list_cli", "config_list", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".profile_list_payloads", "ConfigListResult", __package__),
            identity="config.profile.list",
        ),
    ),
    CommandSpec(
        "config_profile_status",
        "config_profile",
        "status",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.status.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_OUTPUT_LANGUAGE_OPTION,),
        policy=CALCULATION_READ,
        handler=LazyBinding.available(DeferredTarget(".profile_status_cli", "config_status", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo_client.commands.payloads", "ConfigStatusResult"),
            identity="config.profile.status",
        ),
        allow_unregistered_profile_diagnostic=True,
    ),
)


__all__ = ["PROFILE_INVENTORY_COMMAND_SPECS"]
