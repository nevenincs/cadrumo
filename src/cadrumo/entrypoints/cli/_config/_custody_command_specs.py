"""Import-light production authority for profile-session custody commands."""

from __future__ import annotations

from .._command_spec import (
    ArgumentSpec,
    CommandSpec,
    DeferredTarget,
    InvocationSpec,
    LazyBinding,
    MachineSecretChannelKind,
    MachineSecretFieldSpec,
    MachineSecretSpec,
    MachineSecretVariantSpec,
    OptionSpec,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)
from ._spec_policies import BOOTSTRAP_DESTRUCTIVE, BOOTSTRAP_WRITE

_OUTPUT_LANGUAGE = OptionSpec(
    name="output_language",
    declarations=("--output-language", "--language"),
    value=ValueContract(DeferredTarget("cadrumo.core", "OutputLanguage")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.config.auth.output_language_help"),
)


def _schema(name: str, identity: str) -> ResultSchemaSpec:
    return ResultSchemaSpec(
        SchemaState.TARGET,
        target=DeferredTarget("cadrumo.entrypoints.cli._config_payloads", name),
        identity=identity,
    )


CONFIG_CUSTODY_COMMAND_SPECS = (
    CommandSpec(
        key="config_login",
        parent_key="config",
        token="login",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.login.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            ArgumentSpec(
                name="name",
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.config.login.name_help"),
            ),
            OptionSpec(
                name="secrets_stdin",
                declarations=("--secrets-stdin",),
                value=ValueContract(DeferredTarget("builtins", "bool")),
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.config.custody.secrets_stdin_help"),
                is_flag=True,
                flag_value=True,
                machine_secret_channel=MachineSecretChannelKind.STDIN,
            ),
            OptionSpec(
                name="secrets_fd",
                declarations=("--secrets-fd",),
                value=ValueContract(DeferredTarget("builtins", "int")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.config.custody.secrets_fd_help"),
                machine_secret_channel=MachineSecretChannelKind.FILE_DESCRIPTOR,
            ),
            _OUTPUT_LANGUAGE,
        ),
        policy=BOOTSTRAP_WRITE,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._config._custody", "config_login")
        ),
        result_schema=_schema("ConfigLoginResult", "config.login"),
        machine_secret=MachineSecretSpec(
            (
                MachineSecretVariantSpec(
                    "passphrase",
                    (MachineSecretFieldSpec("passphrase"),),
                    DeferredTarget("cadrumo.entrypoints.cli._config._custody", "LoginSecrets"),
                ),
            )
        ),
    ),
    CommandSpec(
        key="config_logout",
        parent_key="config",
        token="logout",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.logout.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_OUTPUT_LANGUAGE,),
        policy=BOOTSTRAP_DESTRUCTIVE,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._config._custody", "config_logout")
        ),
        result_schema=_schema("ConfigLogoutResult", "config.logout"),
    ),
)


__all__ = ["CONFIG_CUSTODY_COMMAND_SPECS"]
