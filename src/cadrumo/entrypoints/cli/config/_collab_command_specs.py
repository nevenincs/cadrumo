"""Import-light production authority for collaboration recipient commands."""

from __future__ import annotations

from ..command_spec import (
    TEXT_VALUE,
    ArgumentSpec,
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
from ._spec_policies import ENCRYPTED_DESTRUCTIVE, ENCRYPTED_READ, ENCRYPTED_WRITE, STATE_FREE

_RECIPIENT_ID = ArgumentSpec(
    name="recipient_id",
    value=TEXT_VALUE,
    default=ParameterDefault.required(),
    help_key=TranslationKey("cli.config.collab.recipient.recipient_id_help"),
)


def _handler(name: str) -> LazyBinding:
    return LazyBinding.available(DeferredTarget(".collab", name, __package__))


def _schema(name: str, identity: str) -> ResultSchemaSpec:
    return ResultSchemaSpec(
        SchemaState.TARGET,
        target=DeferredTarget(".collab_payloads", name, __package__),
        identity=identity,
    )


CONFIG_COLLAB_COMMAND_SPECS = (
    CommandSpec(
        "config_collab",
        "config",
        "collab",
        kind=CommandNodeKind.GROUP,
        help_key=TranslationKey("cli.config.collab.help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=STATE_FREE,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        "config_collab_recipient",
        "config_collab",
        "recipient",
        kind=CommandNodeKind.GROUP,
        help_key=TranslationKey("cli.config.collab.recipient.help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=STATE_FREE,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        "config_collab_recipient_add",
        "config_collab_recipient",
        "add",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.collab.recipient.add_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            _RECIPIENT_ID,
            OptionSpec(
                name="public_key",
                declarations=("--public-key",),
                value=TEXT_VALUE,
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.config.collab.recipient.public_key_help"),
            ),
            OptionSpec(
                name="label",
                declarations=("--label",),
                value=TEXT_VALUE,
                default=ParameterDefault.value(""),
                help_key=TranslationKey("cli.config.collab.recipient.label_help"),
            ),
        ),
        policy=ENCRYPTED_WRITE,
        handler=_handler("collab_recipient_add"),
        result_schema=_schema("ConfigCollabRecipientAddResult", "config.collab.recipient.add"),
    ),
    CommandSpec(
        "config_collab_recipient_list",
        "config_collab_recipient",
        "list",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.config.collab.recipient.list_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(),
        policy=ENCRYPTED_READ,
        handler=_handler("collab_recipient_list"),
        result_schema=_schema("ConfigCollabRecipientListResult", "config.collab.recipient.list"),
    ),
    CommandSpec(
        "config_collab_recipient_remove",
        "config_collab_recipient",
        "remove",
        kind=CommandNodeKind.LEAF,
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
