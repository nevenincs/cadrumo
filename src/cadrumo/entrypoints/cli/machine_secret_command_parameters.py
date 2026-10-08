"""Canonical immutable options for machine-secret input channels."""

from __future__ import annotations

from ._command_secret_contracts import MachineSecretChannelKind
from .command_parameter_contracts import OptionSpec
from .command_shared_contracts import DeferredTarget, ParameterDefault, TranslationKey, ValueContract

MACHINE_SECRET_STDIN_OPTION = OptionSpec(
    name="secrets_stdin",
    declarations=("--secrets-stdin",),
    value=ValueContract(DeferredTarget("builtins", "bool")),
    default=ParameterDefault.value(False),
    help_key=TranslationKey("cli.config.custody.secrets_stdin_help"),
    is_flag=True,
    flag_value=True,
    machine_secret_channel=MachineSecretChannelKind.STDIN,
)
MACHINE_SECRET_FD_OPTION = OptionSpec(
    name="secrets_fd",
    declarations=("--secrets-fd",),
    value=ValueContract(DeferredTarget("builtins", "int")),
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.config.custody.secrets_fd_help"),
    machine_secret_channel=MachineSecretChannelKind.FILE_DESCRIPTOR,
)
