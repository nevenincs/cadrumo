"""Import-light production authority for profile-session custody commands."""

from __future__ import annotations

from cadrumo.application.operator_surface.command_ports import (
    CommandNodeKind,
    ProfileAuthenticationPosture,
)

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
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)
from ._command_spec_schema import config_payload_schema as _schema
from ._spec_policies import BOOTSTRAP_DESTRUCTIVE, BOOTSTRAP_WRITE, ENCRYPTED_DESTRUCTIVE, STATE_FREE

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
        "config_passphrase",
        "config",
        "passphrase",
        kind=CommandNodeKind.GROUP,
        help_key=TranslationKey("cli.config.passphrase.help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=STATE_FREE,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        "config_passphrase_change",
        "config_passphrase",
        "change",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.passphrase.change_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            *_MACHINE_SECRET_OPTIONS,
            _OUTPUT_LANGUAGE,
        ),
        policy=ENCRYPTED_DESTRUCTIVE,
        handler=LazyBinding.available(DeferredTarget(".passphrase", "passphrase_change", __package__)),
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
                        ".passphrase",
                        "PassphraseChangeSecrets",
                        __package__,
                    ),
                ),
            )
        ),
        profile_authentication=ProfileAuthenticationPosture.SELF_AUTHENTICATING,
    ),
    CommandSpec(
        "config_passphrase_reset",
        "config_passphrase",
        "reset",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.passphrase.reset_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            ArgumentSpec(
                name="name",
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.config.passphrase.reset_name_help"),
            ),
            *_MACHINE_SECRET_OPTIONS,
            _OUTPUT_LANGUAGE,
        ),
        policy=BOOTSTRAP_DESTRUCTIVE,
        handler=LazyBinding.available(DeferredTarget(".passphrase", "passphrase_reset", __package__)),
        result_schema=_schema("ConfigPassphraseResetResult", "config.passphrase.reset"),
        machine_secret=MachineSecretSpec(
            (
                MachineSecretVariantSpec(
                    "reset",
                    (
                        MachineSecretFieldSpec("recovery_code"),
                        MachineSecretFieldSpec("new_passphrase"),
                        MachineSecretFieldSpec("new_passphrase_confirmation"),
                    ),
                    DeferredTarget(
                        ".passphrase",
                        "PassphraseResetSecrets",
                        __package__,
                    ),
                ),
            )
        ),
        profile_authentication=ProfileAuthenticationPosture.SELF_AUTHENTICATING,
    ),
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
        handler=LazyBinding.available(DeferredTarget(".custody", "config_login", __package__)),
        result_schema=_schema("ConfigLoginResult", "config.login"),
        machine_secret=MachineSecretSpec(
            (
                MachineSecretVariantSpec(
                    "passphrase",
                    (MachineSecretFieldSpec("passphrase"),),
                    DeferredTarget(".custody", "LoginSecrets", __package__),
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
        parameters=(_OUTPUT_LANGUAGE,),
        policy=BOOTSTRAP_DESTRUCTIVE,
        handler=LazyBinding.available(DeferredTarget(".custody", "config_logout", __package__)),
        result_schema=_schema("ConfigLogoutResult", "config.logout"),
    ),
)


__all__ = ["CONFIG_CUSTODY_COMMAND_SPECS"]
