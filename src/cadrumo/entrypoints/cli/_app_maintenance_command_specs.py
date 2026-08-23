"""CommandSpec authority for the maintenance command family."""

from __future__ import annotations

from ._command_spec import (
    CommandSpec,
    DeferredTarget,
    ExecutionPolicySpec,
    InvocationSpec,
    LazyBinding,
    OptionSpec,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)

_METADATA = ExecutionPolicySpec(
    capabilities=frozenset({"state-free"}),
    side_effects=frozenset({"none"}),
    performance="metadata",
    write_route="none",
)
_DESTRUCTIVE = ExecutionPolicySpec(
    capabilities=frozenset({"profile-custody"}),
    side_effects=frozenset({"local-state"}),
    performance="local-io",
    write_route="profile-bound",
    destructive=True,
)

MAINTENANCE_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_maintenance",
        parent_key="app",
        token="maintenance",  # noqa: S106 - CLI operator token, not a credential
        kind="group",
        help_key=TranslationKey("cli.app.maintenance.help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=_METADATA,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        key="app_maintenance_reconcile",
        parent_key="app_maintenance",
        token="reconcile",  # noqa: S106 - CLI operator token, not a credential
        kind="leaf",
        help_key=TranslationKey("cli.app.maintenance.reconcile_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="output_language",
                declarations=("--output-language", "--language"),
                value=ValueContract(DeferredTarget("cadrumo.core", "OutputLanguage")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.config.auth.output_language_help"),
            ),
        ),
        policy=_DESTRUCTIVE,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._app_maintenance", "app_maintenance_reconcile")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            target=DeferredTarget(
                "cadrumo.entrypoints.cli._app_maintenance_payloads",
                "ProfileBundleReconcileResult",
            ),
            identity="app.maintenance.reconcile",
        ),
    ),
)

__all__ = ["MAINTENANCE_COMMAND_SPECS"]
