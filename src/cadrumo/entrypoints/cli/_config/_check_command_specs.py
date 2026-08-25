"""Import-light production authority for the workstation check command."""

from __future__ import annotations

from .._command_spec import (
    CommandSpec,
    DeferredTarget,
    InvocationSpec,
    LazyBinding,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
)
from ._spec_policies import ENCRYPTED_READ

CONFIG_CHECK_COMMAND_SPECS = (
    CommandSpec(
        key="config_check",
        parent_key="config",
        token="check",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.check.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(),
        policy=ENCRYPTED_READ,
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._config._check_cli", "config_check")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget("cadrumo.entrypoints.cli._config._check_payloads", "ConfigCheckResult"),
            identity="config.check",
        ),
    ),
)

__all__ = ["CONFIG_CHECK_COMMAND_SPECS"]
