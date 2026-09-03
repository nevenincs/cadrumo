"""Authored CommandSpec declarations for the live notifications service."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from typing import Final

from ._app_live_command_spec_support import (
    _ENCRYPTED_LOCAL_READ_POLICY,
    _LEAF_INVOCATION,
    _METADATA_GROUP_INVOCATION,
    _METADATA_POLICY,
    _PROFILE_BOUND_NETWORK_CAPTURE_POLICY,
    NO_RESULT_SCHEMA,
    _key,
)
from .command_spec import (
    ArgumentSpec,
    CommandNodeKind,
    CommandSpec,
    DeferredTarget,
    LazyBinding,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    ValueContract,
)

_NOTIFICATION_CERTIFICADO_ID_ARGUMENT: Final[ArgumentSpec] = ArgumentSpec(
    name="certificado_id",
    value=ValueContract(DeferredTarget("builtins", "str")),
    default=ParameterDefault.required(),
    help_key=_key("cli.app.live.notifications.document.certificado_id_help"),
    constraint=ParameterConstraint(minimum=None, maximum=None),
)

LIVE_NOTIFICATIONS_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_live_notifications",
        parent_key="app_live",
        token="notifications",
        kind=CommandNodeKind.GROUP,
        help_key=_key("cli.app.live.notifications.app_help"),
        short_help_key=None,
        invocation=_METADATA_GROUP_INVOCATION,
        parameters=(),
        policy=_METADATA_POLICY,
        handler=None,
        result_schema=NO_RESULT_SCHEMA,
    ),
    CommandSpec(
        key="app_live_notifications_pull",
        parent_key="app_live_notifications",
        token="pull",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.notifications.pull_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(),
        policy=_PROFILE_BOUND_NETWORK_CAPTURE_POLICY,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._app_live_notifications_cli", "notifications_pull")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(
                "cadrumo.entrypoints.cli._app_live_notifications_payloads", "NotificationsCaptureResult"
            ),
            identity="app.live.notifications.pull",
        ),
    ),
    CommandSpec(
        key="app_live_notifications_list",
        parent_key="app_live_notifications",
        token="list",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.notifications.list_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(),
        policy=_ENCRYPTED_LOCAL_READ_POLICY,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._app_live_notifications_cli", "notifications_list")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(
                "cadrumo.entrypoints.cli._app_live_notifications_payloads", "NotificationsListResult"
            ),
            identity="app.live.notifications.list",
        ),
    ),
    CommandSpec(
        key="app_live_notifications_view",
        parent_key="app_live_notifications",
        token="view",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.notifications.view_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(
            ArgumentSpec(
                name="snapshot_id",
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.notifications.snapshot_id_help"),
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
        ),
        policy=_ENCRYPTED_LOCAL_READ_POLICY,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._app_live_notifications_cli", "notifications_show")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(
                "cadrumo.entrypoints.cli._app_live_notifications_payloads", "NotificationsViewResult"
            ),
            identity="app.live.notifications.view",
        ),
    ),
    CommandSpec(
        key="app_live_notifications_latest",
        parent_key="app_live_notifications",
        token="latest",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.notifications.latest_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(),
        policy=_ENCRYPTED_LOCAL_READ_POLICY,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._app_live_notifications_cli", "notifications_latest")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(
                "cadrumo.entrypoints.cli._app_live_notifications_payloads", "NotificationsLatestResult"
            ),
            identity="app.live.notifications.latest",
        ),
    ),
    CommandSpec(
        key="app_live_notifications_document",
        parent_key="app_live_notifications",
        token="document",
        kind=CommandNodeKind.GROUP,
        help_key=_key("cli.app.live.notifications.document.app_help"),
        short_help_key=None,
        invocation=_METADATA_GROUP_INVOCATION,
        parameters=(),
        policy=_METADATA_POLICY,
        handler=None,
        result_schema=NO_RESULT_SCHEMA,
    ),
    CommandSpec(
        key="app_live_notifications_document_pull",
        parent_key="app_live_notifications_document",
        token="pull",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.notifications.document.pull_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(_NOTIFICATION_CERTIFICADO_ID_ARGUMENT,),
        policy=_PROFILE_BOUND_NETWORK_CAPTURE_POLICY,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._app_live_notifications_cli", "notifications_document_pull")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(
                "cadrumo.entrypoints.cli._app_live_notifications_payloads", "NotificationDocumentPullResult"
            ),
            identity="app.live.notifications.document.pull",
        ),
    ),
    CommandSpec(
        key="app_live_notifications_document_view",
        parent_key="app_live_notifications_document",
        token="view",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.notifications.document.view_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(_NOTIFICATION_CERTIFICADO_ID_ARGUMENT,),
        policy=_ENCRYPTED_LOCAL_READ_POLICY,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._app_live_notifications_cli", "notifications_document_view")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(
                "cadrumo.entrypoints.cli._app_live_notifications_payloads", "NotificationDocumentViewResult"
            ),
            identity="app.live.notifications.document.view",
        ),
    ),
    CommandSpec(
        key="app_live_notifications_document_history",
        parent_key="app_live_notifications_document",
        token="history",
        kind=CommandNodeKind.LEAF,
        help_key=_key("cli.app.live.notifications.document.history_help"),
        short_help_key=None,
        invocation=_LEAF_INVOCATION,
        parameters=(),
        policy=_ENCRYPTED_LOCAL_READ_POLICY,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._app_live_notifications_cli", "notifications_document_history")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(
                "cadrumo.entrypoints.cli._app_live_notifications_payloads", "NotificationDocumentHistoryResult"
            ),
            identity="app.live.notifications.document.history",
        ),
    ),
)

__all__ = ["LIVE_NOTIFICATIONS_COMMAND_SPECS"]
