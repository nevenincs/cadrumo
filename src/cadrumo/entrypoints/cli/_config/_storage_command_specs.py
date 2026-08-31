"""Import-light production authority for the config storage command family."""

from __future__ import annotations

from ..command_spec import (
    ArgumentSpec,
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
from ._spec_policies import BOOTSTRAP_DESTRUCTIVE, BOOTSTRAP_WRITE, PROFILE_READ, STATE_FREE

_OUTPUT_LANGUAGE_OPTION = OptionSpec(
    name="output_language",
    declarations=("--output-language", "--language"),
    value=ValueContract(DeferredTarget("cadrumo.core.external_constants", "OutputLanguage")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.config.auth.output_language_help"),
)
_AREA = ValueContract(DeferredTarget("cadrumo.core.storage_taxonomy", "StorageArea"))


def _schema(name: str, identity: str) -> ResultSchemaSpec:
    return ResultSchemaSpec(
        SchemaState.TARGET,
        target=DeferredTarget("cadrumo.entrypoints.cli._config._storage_payloads", name),
        identity=identity,
    )


def _handler(name: str) -> LazyBinding:
    return LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._config._storage_cli", name))


CONFIG_STORAGE_COMMAND_SPECS = (
    CommandSpec(
        key="config_storage",
        parent_key="config",
        token="storage",  # noqa: S106 - CLI token, not a credential.
        kind="group",
        help_key=TranslationKey("cli.config.storage.help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=STATE_FREE,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        key="config_storage_list",
        parent_key="config_storage",
        token="list",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.storage.list.area_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_OUTPUT_LANGUAGE_OPTION,),
        policy=PROFILE_READ,
        handler=_handler("config_storage_list"),
        result_schema=_schema("ConfigStorageListResult", "config.storage.list"),
    ),
    CommandSpec(
        key="config_storage_view",
        parent_key="config_storage",
        token="view",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.storage.view.area_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            ArgumentSpec(
                name="area",
                value=_AREA,
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.config.storage.view.area_argument_help"),
            ),
            _OUTPUT_LANGUAGE_OPTION,
        ),
        policy=PROFILE_READ,
        handler=_handler("config_storage_view"),
        result_schema=_schema("ConfigStorageViewResult", "config.storage.view"),
    ),
    CommandSpec(
        key="config_storage_check",
        parent_key="config_storage",
        token="check",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.storage.check.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_OUTPUT_LANGUAGE_OPTION,),
        policy=PROFILE_READ,
        handler=_handler("config_storage_check"),
        result_schema=_schema("ConfigStorageCheckResult", "config.storage.check"),
    ),
    CommandSpec(
        key="config_storage_init",
        parent_key="config_storage",
        token="init",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.storage.init.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_OUTPUT_LANGUAGE_OPTION,),
        policy=BOOTSTRAP_WRITE,
        handler=_handler("config_storage_init"),
        result_schema=_schema("ConfigStorageInitResult", "config.storage.init"),
    ),
    CommandSpec(
        key="config_storage_reclaim",
        parent_key="config_storage",
        token="reclaim",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.storage.reclaim.area_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            ArgumentSpec(
                name="area",
                value=_AREA,
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.config.storage.reclaim.area_argument_help"),
            ),
            OptionSpec(
                name="confirmed",
                declarations=("--yes",),
                value=ValueContract(DeferredTarget("builtins", "bool")),
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.config.storage.reclaim.yes_help"),
                is_flag=True,
                flag_value=True,
            ),
            _OUTPUT_LANGUAGE_OPTION,
        ),
        policy=BOOTSTRAP_DESTRUCTIVE,
        handler=_handler("config_storage_reclaim"),
        result_schema=_schema("ConfigStorageReclaimResult", "config.storage.reclaim"),
    ),
)


__all__ = ["CONFIG_STORAGE_COMMAND_SPECS"]
