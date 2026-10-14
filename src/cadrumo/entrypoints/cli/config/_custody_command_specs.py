"""Import-light production authority for profile-session custody commands."""

from __future__ import annotations

from cadrumo_client.commands.parameters import ArgumentSpec, OptionSpec
from cadrumo_client.commands.secret_contracts import (
    MachineSecretChannelKind,
    MachineSecretFieldSpec,
    MachineSecretSpec,
    MachineSecretVariantSpec,
)
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
from cadrumo_client.contracts.command_ports import (
    CommandNodeKind,
)

from ._spec_policies import BOOTSTRAP_DESTRUCTIVE, BOOTSTRAP_WRITE

_OUTPUT_LANGUAGE = OptionSpec(
    name="output_language",
    declarations=("--output-language", "--language"),
    value=ValueContract(DeferredTarget("....core.external_constants", "OutputLanguage", __package__)),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.config.auth.output_language_help"),
)

_MACHINE_SECRET_OPTIONS: tuple[OptionSpec, OptionSpec] = (
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
)


CONFIG_CUSTODY_COMMAND_SPECS = (
    CommandSpec(
        "config_login",
        "config",
        "login",
        kind=CommandNodeKind.LEAF,
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
            *_MACHINE_SECRET_OPTIONS,
            _OUTPUT_LANGUAGE,
        ),
        policy=BOOTSTRAP_WRITE,
        handler=LazyBinding.available(DeferredTarget("cadrumo_client.commands.custody", "config_login")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo_client.commands.custody_payloads", "ConfigLoginResult"),
            identity="config.login",
        ),
        machine_secret=MachineSecretSpec(
            (
                MachineSecretVariantSpec(
                    "passphrase",
                    (MachineSecretFieldSpec("passphrase"),),
                    DeferredTarget("cadrumo_client.commands.custody", "LoginSecrets"),
                ),
            )
        ),
    ),
    CommandSpec(
        "config_logout",
        "config",
        "logout",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.logout.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(*_MACHINE_SECRET_OPTIONS, _OUTPUT_LANGUAGE),
        policy=BOOTSTRAP_DESTRUCTIVE,
        handler=LazyBinding.available(DeferredTarget("cadrumo_client.commands.custody", "config_logout")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo_client.commands.custody_payloads", "ConfigLogoutResult"),
            identity="config.logout",
        ),
        machine_secret=MachineSecretSpec(
            (
                MachineSecretVariantSpec(
                    "passphrase",
                    (MachineSecretFieldSpec("passphrase"),),
                    DeferredTarget("cadrumo_client.commands.custody", "LoginSecrets"),
                ),
            )
        ),
    ),
)


__all__ = ["CONFIG_CUSTODY_COMMAND_SPECS"]
