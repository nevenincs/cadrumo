"""Import-light production authority for collaboration recipient commands."""

from __future__ import annotations

from .._command_spec import (
    ArgumentSpec,
    CommandSpec,
    DeferredTarget,
    InvocationSpec,
    LazyBinding,
    OptionSpec,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)
from ._spec_policies import ENCRYPTED_DESTRUCTIVE, ENCRYPTED_READ, ENCRYPTED_WRITE, STATE_FREE

_STRING = ValueContract(DeferredTarget("builtins", "str"))
_RECIPIENT_ID = ArgumentSpec(
    name="recipient_id",
    value=_STRING,
    default=ParameterDefault.required(),
    help_key=TranslationKey("cli.config.collab.recipient.recipient_id_help"),
)


def _handler(name: str) -> LazyBinding:
    return LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._config._collab", name))


def _schema(name: str, identity: str) -> ResultSchemaSpec:
    return ResultSchemaSpec(
        SchemaState.TARGET,
        target=DeferredTarget("cadrumo.entrypoints.cli._config._collab_payloads", name),
        identity=identity,
    )


CONFIG_COLLAB_COMMAND_SPECS = (
    CommandSpec(
        key="config_collab",
        parent_key="config",
        token="collab",  # noqa: S106 - CLI token, not a credential.
        kind="group",
        help_key=TranslationKey("cli.config.collab.help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=STATE_FREE,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        key="config_collab_recipient",
        parent_key="config_collab",
        token="recipient",  # noqa: S106 - CLI token, not a credential.
        kind="group",
        help_key=TranslationKey("cli.config.collab.recipient.help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=STATE_FREE,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        key="config_collab_recipient_add",
        parent_key="config_collab_recipient",
        token="add",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.collab.recipient.add_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            _RECIPIENT_ID,
            OptionSpec(
                name="public_key",
                declarations=("--public-key",),
                value=_STRING,
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.config.collab.recipient.public_key_help"),
            ),
            OptionSpec(
                name="label",
                declarations=("--label",),
                value=_STRING,
                default=ParameterDefault.value(""),
                help_key=TranslationKey("cli.config.collab.recipient.label_help"),
            ),
        ),
        policy=ENCRYPTED_WRITE,
        handler=_handler("collab_recipient_add"),
        result_schema=_schema("ConfigCollabRecipientAddResult", "config.collab.recipient.add"),
    ),
    CommandSpec(
        key="config_collab_recipient_list",
        parent_key="config_collab_recipient",
        token="list",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.collab.recipient.list_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(),
        policy=ENCRYPTED_READ,
        handler=_handler("collab_recipient_list"),
        result_schema=_schema("ConfigCollabRecipientListResult", "config.collab.recipient.list"),
    ),
    CommandSpec(
        key="config_collab_recipient_remove",
        parent_key="config_collab_recipient",
        token="remove",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.collab.recipient.remove_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_RECIPIENT_ID,),
        policy=ENCRYPTED_DESTRUCTIVE,
        handler=_handler("collab_recipient_remove"),
        result_schema=_schema("ConfigCollabRecipientRemoveResult", "config.collab.recipient.remove"),
    ),
)


__all__ = ["CONFIG_COLLAB_COMMAND_SPECS"]
