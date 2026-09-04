"""Import-light production authority for durable configuration reset commands."""

from __future__ import annotations

from ..command_spec import (
    FLAG_VALUE,
    TEXT_VALUE,
    CommandNodeKind,
    CommandSpec,
    DeferredTarget,
    InvocationSpec,
    LazyBinding,
    OptionSpec,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
)
from ._command_spec_schema import config_payload_schema as _schema
from ._spec_policies import BOOTSTRAP_DESTRUCTIVE, PROFILE_READ, STATE_FREE

_YES = OptionSpec(
    name="yes",
    declarations=("--yes",),
    value=FLAG_VALUE,
    default=ParameterDefault.value(False),
    help_key=TranslationKey("cli.config.reset.yes_help"),
    is_flag=True,
    flag_value=True,
)
_OVERRIDE_RETENTION = OptionSpec(
    name="override_retention",
    declarations=("--override-retention",),
    value=FLAG_VALUE,
    default=ParameterDefault.value(False),
    help_key=TranslationKey("cli.config.reset.override_retention_help"),
    is_flag=True,
    flag_value=True,
)
_REASON = OptionSpec(
    name="reason",
    declarations=("--reason",),
    value=TEXT_VALUE,
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.config.reset.reason_help"),
)
_OPERATION_ID = OptionSpec(
    name="operation_id",
    declarations=("--operation-id",),
    value=TEXT_VALUE,
    default=ParameterDefault.value(None),
    help_key=TranslationKey("cli.config.reset.operation_id_help"),
)


def _handler(name: str) -> LazyBinding:
    return LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli.config._reset_cli", name))


CONFIG_RESET_COMMAND_SPECS = (
    CommandSpec(
        key="config_reset",
        parent_key="config",
        token="reset",  # noqa: S106 - CLI token, not a credential.
        kind=CommandNodeKind.GROUP,
        help_key=TranslationKey("cli.config.reset.help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=STATE_FREE,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        key="config_reset_start",
        parent_key="config_reset",
        token="start",  # noqa: S106 - CLI token, not a credential.
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.reset.start_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_YES, _OVERRIDE_RETENTION, _REASON),
        policy=BOOTSTRAP_DESTRUCTIVE,
        handler=_handler("config_reset_start"),
        result_schema=_schema("ConfigResetStartResult", "config.reset.start"),
    ),
    CommandSpec(
        key="config_reset_status",
        parent_key="config_reset",
        token="status",  # noqa: S106 - CLI token, not a credential.
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.reset.status_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_OPERATION_ID,),
        policy=PROFILE_READ,
        handler=_handler("config_reset_status_command"),
        result_schema=_schema("ConfigResetStatusResult", "config.reset.status"),
    ),
    CommandSpec(
        key="config_reset_resume",
        parent_key="config_reset",
        token="resume",  # noqa: S106 - CLI token, not a credential.
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.reset.resume_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_OPERATION_ID, _YES, _OVERRIDE_RETENTION, _REASON),
        policy=BOOTSTRAP_DESTRUCTIVE,
        handler=_handler("config_reset_resume"),
        result_schema=_schema("ConfigResetResumeResult", "config.reset.resume"),
    ),
)


__all__ = ["CONFIG_RESET_COMMAND_SPECS"]
