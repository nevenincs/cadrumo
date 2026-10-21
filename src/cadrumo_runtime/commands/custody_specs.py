"""Import-light production authority for profile-session custody commands."""

from __future__ import annotations

from cadrumo_client.commands.execution_policies import (
    BOOTSTRAP_DESTRUCTIVE,
    BOOTSTRAP_WRITE,
    ENCRYPTED_DESTRUCTIVE,
    PROFILE_READ,
    state_free_group_spec,
)
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
from cadrumo_client.commands.spec_schema import config_payload_schema as _schema
from cadrumo_client.contracts.command_ports import (
    CommandNodeKind,
    ProfileAuthenticationPosture,
)

_MACHINE_SECRET_OPTIONS = (MACHINE_SECRET_STDIN_OPTION, MACHINE_SECRET_FD_OPTION)


RUNTIME_CUSTODY_COMMAND_SPECS = (
    state_free_group_spec("config_passphrase", "config", "passphrase", "cli.config.passphrase.help"),
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
