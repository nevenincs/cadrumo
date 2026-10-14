"""Runtime-owned command declarations for profile recovery credentials."""

from __future__ import annotations

from cadrumo_client.commands.parameters import OptionSpec
from cadrumo_client.commands.secret_contracts import (
    MachineSecretChannelKind,
    MachineSecretFieldSpec,
    MachineSecretSpec,
    MachineSecretVariantSpec,
    RecoveryHandoffSpec,
)
from cadrumo_client.commands.shared_contracts import (
    FLAG_VALUE,
    WHOLE_NUMBER_VALUE,
    DeferredTarget,
    LazyBinding,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)
from cadrumo_client.commands.spec import CommandSpec, ExecutionPolicySpec, InvocationSpec
from cadrumo_client.contracts.command_ports import CommandNodeKind, ProfileAuthenticationPosture

from .spec_policies import ENCRYPTED_DESTRUCTIVE, PROFILE_READ, state_free_group_spec

_OUTPUT_LANGUAGE = OptionSpec(
    name="output_language",
    declarations=("--output-language", "--language"),
    value=ValueContract(DeferredTarget("cadrumo.core.external_constants", "OutputLanguage")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.config.auth.output_language_help"),
)

_SECRET_OPTIONS = (
    OptionSpec(
        name="secrets_stdin",
        declarations=("--secrets-stdin",),
        value=FLAG_VALUE,
        default=ParameterDefault.value(False),
        help_key=TranslationKey("cli.config.custody.secrets_stdin_help"),
        is_flag=True,
        flag_value=True,
        machine_secret_channel=MachineSecretChannelKind.STDIN,
    ),
    OptionSpec(
        name="secrets_fd",
        declarations=("--secrets-fd",),
        value=WHOLE_NUMBER_VALUE,
        default=ParameterDefault.value(None),
        help_key=TranslationKey("cli.config.custody.secrets_fd_help"),
        machine_secret_channel=MachineSecretChannelKind.FILE_DESCRIPTOR,
    ),
)

_RECOVERY_HANDOFF = RecoveryHandoffSpec(
    handoff_parameter="recovery_handoff_fd",
    handoff_direction="write",
    verification_parameter="recovery_verification_fd",
    verification_direction="read",
    required_together=True,
    json_fields=("recovery_code",),
    maximum_bytes=8192,
    strict_utf8_object=True,
    duplicate_extra_missing_fields_refused=True,
    descriptors_closed=True,
    reserved_descriptors=(0, 1, 2),
    descriptors_must_differ=True,
    collides_with_parameters=("secrets_fd",),
    windows_handle_bootstrap="cadrumo_runtime.host.windows_secret_bootstrap",
)

_RECOVERY_SECRET = MachineSecretSpec(
    (
        MachineSecretVariantSpec(
            "passphrase",
            (MachineSecretFieldSpec("passphrase"),),
            DeferredTarget("cadrumo_runtime.commands.recovery", "RecoveryEnableSecrets"),
        ),
    )
)


def _recovery_leaf(
    key: str,
    token: str,
    help_key: str,
    handler: str,
    result_name: str,
    result_identity: str,
    *,
    parameters: tuple[OptionSpec, ...],
    secret: MachineSecretSpec | None = None,
    recovery_handoff: RecoveryHandoffSpec | None = None,
    profile_authentication: ProfileAuthenticationPosture = ProfileAuthenticationPosture.NOT_APPLICABLE,
    policy: ExecutionPolicySpec = ENCRYPTED_DESTRUCTIVE,
) -> CommandSpec:
    return CommandSpec(
        key=key,
        parent_key="config_profile_recovery",
        token=token,
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey(help_key),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(*parameters, _OUTPUT_LANGUAGE),
        policy=policy,
        handler=LazyBinding.available(DeferredTarget("cadrumo_runtime.commands.recovery", handler)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo_client.commands.payloads", result_name),
            identity=result_identity,
        ),
        machine_secret=secret,
        recovery_handoff=recovery_handoff,
        profile_authentication=profile_authentication,
    )


RUNTIME_RECOVERY_COMMAND_SPECS = (
    state_free_group_spec("config_profile_recovery", "config_profile", "recovery", "cli.config.profile.recovery.help"),
    _recovery_leaf(
        "config_profile_recovery_enable",
        "enable",
        "cli.config.profile.recovery.enable_help",
        "profile_recovery_enable",
        "ConfigProfileRecoveryResult",
        "config.profile.recovery.enable",
        parameters=(
            *_SECRET_OPTIONS,
            OptionSpec(
                name="recovery_handoff_fd",
                declarations=("--recovery-handoff-fd",),
                value=WHOLE_NUMBER_VALUE,
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.config.profile.recovery.handoff_fd_help"),
            ),
            OptionSpec(
                name="recovery_verification_fd",
                declarations=("--recovery-verification-fd",),
                value=WHOLE_NUMBER_VALUE,
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.config.profile.recovery.verification_fd_help"),
            ),
        ),
        secret=_RECOVERY_SECRET,
        recovery_handoff=_RECOVERY_HANDOFF,
        profile_authentication=ProfileAuthenticationPosture.SELF_AUTHENTICATING,
    ),
    _recovery_leaf(
        "config_profile_recovery_disable",
        "disable",
        "cli.config.profile.recovery.disable_help",
        "profile_recovery_disable",
        "ConfigProfileRecoveryResult",
        "config.profile.recovery.disable",
        parameters=_SECRET_OPTIONS,
        secret=_RECOVERY_SECRET,
        profile_authentication=ProfileAuthenticationPosture.SELF_AUTHENTICATING,
    ),
    _recovery_leaf(
        "config_profile_recovery_status",
        "status",
        "cli.config.profile.recovery.status_help",
        "profile_recovery_status",
        "ConfigProfileRecoveryStatusResult",
        "config.profile.recovery.status",
        parameters=(),
        policy=PROFILE_READ,
        profile_authentication=ProfileAuthenticationPosture.RESUME_FALLBACK,
    ),
)


__all__ = ["RUNTIME_RECOVERY_COMMAND_SPECS"]
