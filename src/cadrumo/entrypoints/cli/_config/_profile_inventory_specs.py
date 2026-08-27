"""Import-light command specifications for profile inventory and readiness."""

from __future__ import annotations

from .._command_spec import (
    CommandSpec,
    DeferredTarget,
    InvocationSpec,
    LazyBinding,
    OptionSpec,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    TuiCapability,
    ValueContract,
)
from ._spec_policies import CALCULATION_READ, PROFILE_READ

_OUTPUT_LANGUAGE = ValueContract(DeferredTarget("cadrumo.core", "OutputLanguage"))
_OUTPUT_LANGUAGE_OPTION = OptionSpec(
    name="output_language",
    declarations=("--output-language", "--language"),
    value=_OUTPUT_LANGUAGE,
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.config.auth.output_language_help"),
)


PROFILE_INVENTORY_COMMAND_SPECS = (
    CommandSpec(
        key="config_profile_list",
        parent_key="config_profile",
        token="list",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.list.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_OUTPUT_LANGUAGE_OPTION,),
        policy=PROFILE_READ,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._config._profile_list_cli", "config_list")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._config._profile_list_payloads", "ConfigListResult"),
            identity="config.profile.list",
        ),
    ),
    CommandSpec(
        key="config_profile_status",
        parent_key="config_profile",
        token="status",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.status.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_OUTPUT_LANGUAGE_OPTION,),
        policy=CALCULATION_READ,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._config._profile_status_cli", "config_status")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._config_payloads", "ConfigStatusResult"),
            identity="config.profile.status",
        ),
        allow_unregistered_profile_diagnostic=True,
        tui_capability=TuiCapability.AVAILABLE,
    ),
)


__all__ = ["PROFILE_INVENTORY_COMMAND_SPECS"]
