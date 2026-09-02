"""Import-light production authority for profile-session custody commands."""

from __future__ import annotations

from ..command_spec import (
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
    ProfileAuthenticationPosture,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    TuiCapability,
    ValueContract,
)
from ._command_spec_schema import config_payload_schema as _schema
from ._spec_policies import BOOTSTRAP_DESTRUCTIVE, BOOTSTRAP_WRITE, ENCRYPTED_DESTRUCTIVE, STATE_FREE

_OUTPUT_LANGUAGE = OptionSpec(
    name="output_language",
    declarations=("--output-language", "--language"),
    value=ValueContract(DeferredTarget("cadrumo.core.external_constants", "OutputLanguage")),
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
            *_MACHINE_SECRET_OPTIONS,
            _OUTPUT_LANGUAGE,
        ),
        policy=ENCRYPTED_DESTRUCTIVE,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli.config._passphrase", "passphrase_change")
        ),
        result_schema=_schema("ConfigPassphraseChangeResult", "config.passphrase.change"),
        machine_secret=MachineSecretSpec(
            (
                MachineSecretVariantSpec(
                    "rotation",
                    (
                        MachineSecretFieldSpec("current_passphrase"),
                        MachineSecretFieldSpec("new_passphrase"),
                        MachineSecretFieldSpec("new_passphrase_confirmation"),
                    ),
                    DeferredTarget(
                        "cadrumo.entrypoints.cli.config._passphrase",
                        "PassphraseChangeSecrets",
                    ),
                ),
            )
        ),
        profile_authentication=ProfileAuthenticationPosture.SELF_AUTHENTICATING,
    ),
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
            *_MACHINE_SECRET_OPTIONS,
            _OUTPUT_LANGUAGE,
        ),
        policy=BOOTSTRAP_WRITE,
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli.config.custody", "config_login")),
        result_schema=_schema("ConfigLoginResult", "config.login"),
        machine_secret=MachineSecretSpec(
            (
                MachineSecretVariantSpec(
                    "passphrase",
                    (MachineSecretFieldSpec("passphrase"),),
                    DeferredTarget("cadrumo.entrypoints.cli.config.custody", "LoginSecrets"),
                ),
            )
        ),
        tui_capability=TuiCapability.AVAILABLE,
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
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli.config.custody", "config_logout")),
        result_schema=_schema("ConfigLogoutResult", "config.logout"),
    ),
)


__all__ = ["CONFIG_CUSTODY_COMMAND_SPECS"]
