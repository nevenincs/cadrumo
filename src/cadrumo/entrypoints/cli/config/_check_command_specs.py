"""Import-light production authority for the workstation check command."""

from __future__ import annotations

from cadrumo_client.commands.shared_contracts import (
    DeferredTarget,
    LazyBinding,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
)
from cadrumo_client.commands.spec import CommandSpec, InvocationSpec
from cadrumo_client.contracts.command_ports import CommandNodeKind

from ._spec_policies import ENCRYPTED_READ

CONFIG_CHECK_COMMAND_SPECS = (
    CommandSpec(
        "config_check",
        "config",
        "check",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.check.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(),
        policy=ENCRYPTED_READ,
        handler=LazyBinding.available(DeferredTarget(".check_cli", "config_check", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".check_payloads", "ConfigCheckResult", __package__),
            identity="config.check",
        ),
    ),
)

__all__ = ["CONFIG_CHECK_COMMAND_SPECS"]
