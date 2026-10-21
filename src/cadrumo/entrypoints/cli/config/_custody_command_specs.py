"""Import-light production authority for profile-session custody commands."""

from __future__ import annotations

from cadrumo_client.commands.execution_policies import BOOTSTRAP_DESTRUCTIVE, BOOTSTRAP_WRITE
from cadrumo_client.commands.language_options import OUTPUT_LANGUAGE_OPTION as _OUTPUT_LANGUAGE
from cadrumo_client.commands.parameters import ArgumentSpec
from cadrumo_client.commands.secret_contracts import (
    MachineSecretFieldSpec,
    MachineSecretSpec,
    MachineSecretVariantSpec,
)
from cadrumo_client.commands.secret_parameters import MACHINE_SECRET_FD_OPTION, MACHINE_SECRET_STDIN_OPTION
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

_MACHINE_SECRET_OPTIONS = (MACHINE_SECRET_STDIN_OPTION, MACHINE_SECRET_FD_OPTION)


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
