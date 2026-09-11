"""Import-light command specifications for profile inventory and readiness."""

from __future__ import annotations

from ..command_spec import (
    CommandNodeKind,
    CommandSpec,
    DeferredTarget,
    InvocationSpec,
    LazyBinding,
    OptionSpec,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)
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
        key="config_profile_list",
        parent_key="config_profile",
        token="list",  # noqa: S106 - CLI token, not a credential.
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.list.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_OUTPUT_LANGUAGE_OPTION,),
        policy=PROFILE_READ,
        handler=LazyBinding.available(DeferredTarget("._profile_list_cli", "config_list", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("._profile_list_payloads", "ConfigListResult", __package__),
            identity="config.profile.list",
        ),
    ),
    CommandSpec(
        key="config_profile_status",
        parent_key="config_profile",
        token="status",  # noqa: S106 - CLI token, not a credential.
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.status.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_OUTPUT_LANGUAGE_OPTION,),
        policy=CALCULATION_READ,
        handler=LazyBinding.available(DeferredTarget("._profile_status_cli", "config_status", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("..config_payloads", "ConfigStatusResult", __package__),
            identity="config.profile.status",
        ),
        allow_unregistered_profile_diagnostic=True,
    ),
)


__all__ = ["PROFILE_INVENTORY_COMMAND_SPECS"]
