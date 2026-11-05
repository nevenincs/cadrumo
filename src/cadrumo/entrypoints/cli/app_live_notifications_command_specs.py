"""Declarative command specs for the live notifications CLI commands."""

from __future__ import annotations

from typing import Final

from cadrumo_client.commands.parameters import ArgumentSpec
from cadrumo_client.commands.shared_contracts import (
    DeferredTarget,
    LazyBinding,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    ValueContract,
    translation_key,
)
from cadrumo_client.commands.spec import CommandSpec
from cadrumo_client.contracts.command_ports import CommandNodeKind

from .app_live_command_spec_support import (
    ENCRYPTED_LOCAL_READ_POLICY,
    LEAF_INVOCATION,
    METADATA_GROUP_INVOCATION,
    METADATA_POLICY,
    NO_RESULT_SCHEMA,
    PROFILE_BOUND_NETWORK_CAPTURE_POLICY,
)

NOTIFICATION_CERTIFICADO_ID_ARGUMENT: Final[ArgumentSpec] = ArgumentSpec(
    name="certificado_id",
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.required(),
    help_key=translation_key("cli.app.live.notifications.document.certificado_id_help"),
    constraint=ParameterConstraint(minimum=None, maximum=None),
)

LIVE_NOTIFICATIONS_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "app_live_notifications",
        "app_live",
        "notifications",
        kind=CommandNodeKind.GROUP,
        help_key=translation_key("cli.app.live.notifications.app_help"),
        short_help_key=None,
        invocation=METADATA_GROUP_INVOCATION,
        parameters=(),
        policy=METADATA_POLICY,
        handler=None,
        result_schema=NO_RESULT_SCHEMA,
    ),
    CommandSpec(
        "app_live_notifications_pull",
        "app_live_notifications",
        "pull",
        kind=CommandNodeKind.LEAF,
        help_key=translation_key("cli.app.live.notifications.pull_help"),
        short_help_key=None,
        invocation=LEAF_INVOCATION,
        parameters=(),
        policy=PROFILE_BOUND_NETWORK_CAPTURE_POLICY,
        handler=LazyBinding.available(
            DeferredTarget(".app_live_notifications_commands", "notifications_pull", __package__)
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".app_live_notifications_results", "NotificationsCaptureResult", __package__),
            identity="app.live.notifications.pull",
        ),
    ),
    CommandSpec(
        "app_live_notifications_list",
        "app_live_notifications",
        "list",
        kind=CommandNodeKind.LEAF,
        help_key=translation_key("cli.app.live.notifications.list_help"),
        short_help_key=None,
        invocation=LEAF_INVOCATION,
        parameters=(),
        policy=ENCRYPTED_LOCAL_READ_POLICY,
        handler=LazyBinding.available(
            DeferredTarget(".app_live_notifications_commands", "notifications_list", __package__)
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".app_live_notifications_results", "NotificationsListResult", __package__),
            identity="app.live.notifications.list",
        ),
    ),
    CommandSpec(
        "app_live_notifications_view",
        "app_live_notifications",
        "view",
        kind=CommandNodeKind.LEAF,
        help_key=translation_key("cli.app.live.notifications.view_help"),
        short_help_key=None,
        invocation=LEAF_INVOCATION,
        parameters=(
            ArgumentSpec(
                name="snapshot_id",
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=translation_key("cli.app.live.notifications.snapshot_id_help"),
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
        ),
        policy=ENCRYPTED_LOCAL_READ_POLICY,
        handler=LazyBinding.available(
            DeferredTarget(".app_live_notifications_commands", "notifications_show", __package__)
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".app_live_notifications_results", "NotificationsViewResult", __package__),
            identity="app.live.notifications.view",
        ),
    ),
    CommandSpec(
        "app_live_notifications_latest",
        "app_live_notifications",
        "latest",
        kind=CommandNodeKind.LEAF,
        help_key=translation_key("cli.app.live.notifications.latest_help"),
        short_help_key=None,
        invocation=LEAF_INVOCATION,
        parameters=(),
        policy=ENCRYPTED_LOCAL_READ_POLICY,
        handler=LazyBinding.available(
            DeferredTarget(".app_live_notifications_commands", "notifications_latest", __package__)
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".app_live_notifications_results", "NotificationsLatestResult", __package__),
            identity="app.live.notifications.latest",
        ),
    ),
    CommandSpec(
        "app_live_notifications_document",
        "app_live_notifications",
        "document",
        kind=CommandNodeKind.GROUP,
        help_key=translation_key("cli.app.live.notifications.document.app_help"),
        short_help_key=None,
        invocation=METADATA_GROUP_INVOCATION,
        parameters=(),
        policy=METADATA_POLICY,
        handler=None,
        result_schema=NO_RESULT_SCHEMA,
    ),
    CommandSpec(
        "app_live_notifications_document_pull",
        "app_live_notifications_document",
        "pull",
        kind=CommandNodeKind.LEAF,
        help_key=translation_key("cli.app.live.notifications.document.pull_help"),
        short_help_key=None,
        invocation=LEAF_INVOCATION,
        parameters=(NOTIFICATION_CERTIFICADO_ID_ARGUMENT,),
        policy=PROFILE_BOUND_NETWORK_CAPTURE_POLICY,
        handler=LazyBinding.available(
            DeferredTarget(".app_live_notifications_commands", "notifications_document_pull", __package__)
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".app_live_notifications_results", "NotificationDocumentPullResult", __package__),
            identity="app.live.notifications.document.pull",
        ),
    ),
    CommandSpec(
        "app_live_notifications_document_view",
        "app_live_notifications_document",
        "view",
        kind=CommandNodeKind.LEAF,
        help_key=translation_key("cli.app.live.notifications.document.view_help"),
        short_help_key=None,
        invocation=LEAF_INVOCATION,
        parameters=(NOTIFICATION_CERTIFICADO_ID_ARGUMENT,),
        policy=ENCRYPTED_LOCAL_READ_POLICY,
        handler=LazyBinding.available(
            DeferredTarget(".app_live_notifications_commands", "notifications_document_view", __package__)
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".app_live_notifications_results", "NotificationDocumentViewResult", __package__),
            identity="app.live.notifications.document.view",
        ),
    ),
    CommandSpec(
        "app_live_notifications_document_history",
        "app_live_notifications_document",
        "history",
        kind=CommandNodeKind.LEAF,
        help_key=translation_key("cli.app.live.notifications.document.history_help"),
        short_help_key=None,
        invocation=LEAF_INVOCATION,
        parameters=(),
        policy=ENCRYPTED_LOCAL_READ_POLICY,
        handler=LazyBinding.available(
            DeferredTarget(".app_live_notifications_commands", "notifications_document_history", __package__)
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(".app_live_notifications_results", "NotificationDocumentHistoryResult", __package__),
            identity="app.live.notifications.document.history",
        ),
    ),
)

__all__ = ["LIVE_NOTIFICATIONS_COMMAND_SPECS"]
"""Authored CommandSpec declarations for the live notifications service."""
"""Authored CommandSpec declarations for the live notifications service."""
