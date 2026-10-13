"""Import-light production authority for the model-provider settings commands."""

from __future__ import annotations

from cadrumo.application.operator_surface.command_ports import CommandNodeKind

from .._command_secret_contracts import (
    MachineSecretChannelKind,
    MachineSecretFieldSpec,
    MachineSecretSpec,
    MachineSecretVariantSpec,
)
from ..command_parameter_contracts import ArgumentSpec, OptionSpec
from ..command_shared_contracts import (
    FLAG_VALUE,
    TEXT_VALUE,
    WHOLE_NUMBER_VALUE,
    DeferredTarget,
    LazyBinding,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
)
from ..command_spec import CommandSpec, InvocationSpec
from ._spec_policies import ENCRYPTED_DESTRUCTIVE, ENCRYPTED_READ, ENCRYPTED_WRITE, STATE_FREE

_PROVIDER_ID = ArgumentSpec(
    name="provider_id",
    value=TEXT_VALUE,
    default=ParameterDefault.required(),
    help_key=TranslationKey("cli.config.provider.provider_id_help"),
)
_EXPECTED_REVISION = OptionSpec(
    name="expected_revision",
    declarations=("--expected-revision",),
    value=TEXT_VALUE,
    default=ParameterDefault.required(),
    help_key=TranslationKey("cli.config.provider.expected_revision_help"),
)


def _handler(name: str) -> LazyBinding:
    return LazyBinding.available(DeferredTarget(".provider", name, __package__))


def _schema(name: str, identity: str) -> ResultSchemaSpec:
    return ResultSchemaSpec(
        SchemaState.TARGET,
        target=DeferredTarget("....application.provider_settings.contracts", name, __package__),
        identity=identity,
    )


def _change(key: str) -> CommandSpec:
    return CommandSpec(
        f"config_provider_{key}",
        "config_provider",
        key,
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey(f"cli.config.provider.{key}_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_PROVIDER_ID, _EXPECTED_REVISION),
        policy=ENCRYPTED_DESTRUCTIVE,
        handler=_handler(f"provider_{key}"),
        result_schema=_schema("ProviderStatusEntry", f"config.provider.{key}"),
    )


CONFIG_PROVIDER_COMMAND_SPECS = (
    CommandSpec(
        "config_provider",
        "config",
        "provider",
        kind=CommandNodeKind.GROUP,
        help_key=TranslationKey("cli.config.provider.help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=STATE_FREE,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        "config_provider_status",
        "config_provider",
        "status",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.provider.status_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(),
        policy=ENCRYPTED_READ,
        handler=_handler("provider_status"),
        result_schema=_schema("ProviderSettingsStatus", "config.provider.status"),
    ),
    CommandSpec(
        "config_provider_set",
        "config_provider",
        "set",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.provider.set_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            _PROVIDER_ID,
            _EXPECTED_REVISION,
            OptionSpec(
                name="base_url",
                declarations=("--base-url",),
                value=TEXT_VALUE,
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.config.provider.base_url_help"),
            ),
            OptionSpec(
                name="clear_base_url",
                declarations=("--clear-base-url",),
                value=FLAG_VALUE,
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.config.provider.clear_base_url_help"),
                is_flag=True,
                flag_value=True,
            ),
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
        ),
        policy=ENCRYPTED_WRITE,
        handler=_handler("provider_set"),
        result_schema=_schema("ProviderStatusEntry", "config.provider.set"),
        machine_secret=MachineSecretSpec(
            (
                MachineSecretVariantSpec(
                    "provider",
                    (MachineSecretFieldSpec("secret"),),
                    DeferredTarget(".provider", "ProviderSecretSetSecrets", __package__),
                ),
            )
        ),
    ),
    _change("remove"),
    _change("reset"),
)


__all__ = ["CONFIG_PROVIDER_COMMAND_SPECS"]
