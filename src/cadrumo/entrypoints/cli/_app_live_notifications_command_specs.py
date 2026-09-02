"""Authored CommandSpec declarations for the live notifications service."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from ._app_live_command_spec_support import _key
from .command_spec import (
    ArgumentSpec,
    CommandSpec,
    DeferredTarget,
    ExecutionPolicySpec,
    InvocationSpec,
    LazyBinding,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    ValueContract,
)

LIVE_NOTIFICATIONS_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_live_notifications",
        parent_key="app_live",
        token="notifications",
        kind="group",
        help_key=_key("cli.app.live.notifications.app_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True, context_parameter=None),
        parameters=(),
        policy=ExecutionPolicySpec(
            capabilities=frozenset(["state-free"]),
            side_effects=frozenset(["none"]),
            performance="metadata",
            write_route=CommandWriteRoute.NONE,
            destructive=False,
            handoff=False,
            live_write=False,
        ),
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        key="app_live_notifications_pull",
        parent_key="app_live_notifications",
        token="pull",
        kind="leaf",
        help_key=_key("cli.app.live.notifications.pull_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=False, context_parameter="ctx"),
        parameters=(),
        policy=ExecutionPolicySpec(
            capabilities=frozenset(["encrypted-facts", "network"]),
            side_effects=frozenset(["local-state", "network"]),
            performance="external-io",
            write_route=CommandWriteRoute.PROFILE_BOUND,
            destructive=False,
            handoff=False,
            live_write=False,
        ),
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
        kind="leaf",
        help_key=_key("cli.app.live.notifications.list_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=False, context_parameter="ctx"),
        parameters=(),
        policy=ExecutionPolicySpec(
            capabilities=frozenset(["encrypted-facts"]),
            side_effects=frozenset(["none"]),
            performance="local-io",
            write_route=CommandWriteRoute.NONE,
            destructive=False,
            handoff=False,
            live_write=False,
        ),
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
        kind="leaf",
        help_key=_key("cli.app.live.notifications.view_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            ArgumentSpec(
                name="snapshot_id",
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.notifications.snapshot_id_help"),
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
        ),
        policy=ExecutionPolicySpec(
            capabilities=frozenset(["encrypted-facts"]),
            side_effects=frozenset(["none"]),
            performance="local-io",
            write_route=CommandWriteRoute.NONE,
            destructive=False,
            handoff=False,
            live_write=False,
        ),
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
        kind="leaf",
        help_key=_key("cli.app.live.notifications.latest_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=False, context_parameter="ctx"),
        parameters=(),
        policy=ExecutionPolicySpec(
            capabilities=frozenset(["encrypted-facts"]),
            side_effects=frozenset(["none"]),
            performance="local-io",
            write_route=CommandWriteRoute.NONE,
            destructive=False,
            handoff=False,
            live_write=False,
        ),
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
        kind="group",
        help_key=_key("cli.app.live.notifications.document.app_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True, context_parameter=None),
        parameters=(),
        policy=ExecutionPolicySpec(
            capabilities=frozenset(["state-free"]),
            side_effects=frozenset(["none"]),
            performance="metadata",
            write_route=CommandWriteRoute.NONE,
            destructive=False,
            handoff=False,
            live_write=False,
        ),
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        key="app_live_notifications_document_pull",
        parent_key="app_live_notifications_document",
        token="pull",
        kind="leaf",
        help_key=_key("cli.app.live.notifications.document.pull_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            ArgumentSpec(
                name="certificado_id",
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.notifications.document.certificado_id_help"),
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
        ),
        policy=ExecutionPolicySpec(
            capabilities=frozenset(["encrypted-facts", "network"]),
            side_effects=frozenset(["local-state", "network"]),
            performance="external-io",
            write_route=CommandWriteRoute.PROFILE_BOUND,
            destructive=False,
            handoff=False,
            live_write=False,
        ),
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
        kind="leaf",
        help_key=_key("cli.app.live.notifications.document.view_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=False, context_parameter="ctx"),
        parameters=(
            ArgumentSpec(
                name="certificado_id",
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.required(),
                help_key=_key("cli.app.live.notifications.document.certificado_id_help"),
                constraint=ParameterConstraint(minimum=None, maximum=None),
            ),
        ),
        policy=ExecutionPolicySpec(
            capabilities=frozenset(["encrypted-facts"]),
            side_effects=frozenset(["none"]),
            performance="local-io",
            write_route=CommandWriteRoute.NONE,
            destructive=False,
            handoff=False,
            live_write=False,
        ),
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
        kind="leaf",
        help_key=_key("cli.app.live.notifications.document.history_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=False, context_parameter="ctx"),
        parameters=(),
        policy=ExecutionPolicySpec(
            capabilities=frozenset(["encrypted-facts"]),
            side_effects=frozenset(["none"]),
            performance="local-io",
            write_route=CommandWriteRoute.NONE,
            destructive=False,
            handoff=False,
            live_write=False,
        ),
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
