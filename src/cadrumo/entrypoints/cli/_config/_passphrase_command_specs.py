"""Import-light production authority for profile passphrase rotation."""

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
    ValueContract,
)
from ._spec_policies import ENCRYPTED_DESTRUCTIVE, STATE_FREE

_BOOL = ValueContract(DeferredTarget("builtins", "bool"))


CONFIG_PASSPHRASE_COMMAND_SPECS = (
    CommandSpec(
        key="config_passphrase",
        parent_key="config",
        token="passphrase",  # noqa: S106 - CLI token, not a credential.
        kind="group",
        help_key=TranslationKey("cli.config.passphrase.help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=STATE_FREE,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        key="config_passphrase_change",
        parent_key="config_passphrase",
        token="change",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.passphrase.change_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="secrets_stdin",
                declarations=("--secrets-stdin",),
                value=_BOOL,
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.config.custody.secrets_stdin_help"),
                is_flag=True,
                flag_value=True,
            ),
            OptionSpec(
                name="secrets_fd",
                declarations=("--secrets-fd",),
                value=ValueContract(DeferredTarget("builtins", "int")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.config.custody.secrets_fd_help"),
            ),
            OptionSpec(
                name="output_language",
                declarations=("--output-language", "--language"),
                value=ValueContract(DeferredTarget("cadrumo.core", "OutputLanguage")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.config.auth.output_language_help"),
            ),
        ),
        policy=ENCRYPTED_DESTRUCTIVE,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._config._passphrase", "passphrase_change")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._config_payloads", "ConfigPassphraseChangeResult"),
            identity="config.passphrase.change",
        ),
    ),
)


__all__ = ["CONFIG_PASSPHRASE_COMMAND_SPECS"]
