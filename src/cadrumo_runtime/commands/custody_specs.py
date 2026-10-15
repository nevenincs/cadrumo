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
from cadrumo_client.commands.spec_schema import config_payload_schema as _schema
from cadrumo_client.contracts.command_ports import (
    CommandNodeKind,
    ProfileAuthenticationPosture,
)
from cadrumo_runtime.commands.spec_policies import (
    BOOTSTRAP_DESTRUCTIVE,
    BOOTSTRAP_WRITE,
    ENCRYPTED_DESTRUCTIVE,
    PROFILE_READ,
    STATE_FREE,
)

_OUTPUT_LANGUAGE = OptionSpec(
    name="output_language",
    declarations=("--output-language", "--language"),
    value=ValueContract(DeferredTarget("cadrumo.core.external_constants", "OutputLanguage", __package__)),
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


RUNTIME_CUSTODY_COMMAND_SPECS = (
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
        "config_activity",
        "config",
        "activity",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.activity.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_OUTPUT_LANGUAGE,),
        policy=BOOTSTRAP_WRITE,
        handler=LazyBinding.available(DeferredTarget(".activity", "config_activity", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo_client.commands.custody_payloads", "ConfigActivityResult"),
            identity="config.activity",
        ),
        profile_authentication=ProfileAuthenticationPosture.SELF_AUTHENTICATING,
    ),
    CommandSpec(
        "config_sign_in_status",
        "config",
        "sign-in-status",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.sign_in_status.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_OUTPUT_LANGUAGE,),
        policy=PROFILE_READ,
        handler=LazyBinding.available(DeferredTarget(".sign_in_status", "config_sign_in_status", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo_client.commands.custody_payloads", "ConfigSignInStatusResult"),
            identity="config.sign-in-status",
        ),
        profile_authentication=ProfileAuthenticationPosture.SELF_AUTHENTICATING,
    ),
)


__all__ = ["RUNTIME_CUSTODY_COMMAND_SPECS"]
