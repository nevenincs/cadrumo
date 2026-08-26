"""Import-light production authority for configuration repair commands."""

from __future__ import annotations

from .._command_spec import (
    CommandSpec,
    DeferredTarget,
    InvocationSpec,
    LazyBinding,
    OptionSpec,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)
from ._spec_policies import (
    BOOTSTRAP_DESTRUCTIVE,
    BOOTSTRAP_WRITE,
    BROWSER_CONNECTIVITY,
    CALCULATION_READ,
    ENCRYPTED_READ,
    LOCAL_READ,
    PROFILE_DESTRUCTIVE,
    REGISTRY_READ,
    STATE_FREE,
)

_BOOL = ValueContract(DeferredTarget("builtins", "bool"))
_STRING = ValueContract(DeferredTarget("builtins", "str"))


def _handler(module: str, name: str) -> LazyBinding:
    return LazyBinding.available(DeferredTarget(f"cadrumo.entrypoints.cli._config.{module}", name))


def _schema(name: str, identity: str) -> ResultSchemaSpec:
    return ResultSchemaSpec(
        SchemaState.TARGET,
        target=DeferredTarget("cadrumo.entrypoints.cli._config_payloads", name),
        identity=identity,
    )


def _flag(
    name: str,
    declaration: str,
    help_key: str | None,
    *,
    default: bool = False,
) -> OptionSpec:
    return OptionSpec(
        name=name,
        declarations=(declaration,),
        value=_BOOL,
        default=ParameterDefault.value(default),
        help_key=TranslationKey(help_key) if help_key is not None else None,
        is_flag=True,
        flag_value=not default,
    )


CONFIG_REPAIR_COMMAND_SPECS = (
    CommandSpec(
        key="config_repair",
        parent_key="config",
        token="repair",  # noqa: S106 - CLI token, not a credential.
        kind="group",
        help_key=TranslationKey("cli.config.repair.help"),
        short_help_key=None,
        invocation=InvocationSpec(
            invoke_without_command=True,
            no_args_is_help=False,
            context_parameter="ctx",
            terminal_behavior="executable",
        ),
        parameters=(),
        policy=CALCULATION_READ,
        handler=_handler("_repair_cli", "repair"),
        result_schema=_schema("ConfigRepairResult", "config.repair"),
    ),
    CommandSpec(
        key="config_repair_integrity",
        parent_key="config_repair",
        token="integrity",  # noqa: S106 - CLI token, not a credential.
        kind="group",
        help_key=TranslationKey("cli.config.repair.integrity_help"),
        short_help_key=None,
        invocation=InvocationSpec(no_args_is_help=True),
        parameters=(),
        policy=STATE_FREE,
        handler=None,
        result_schema=ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    CommandSpec(
        key="config_repair_logs",
        parent_key="config_repair",
        token="logs",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.repair.logs_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="lines",
                declarations=("--lines",),
                value=ValueContract(DeferredTarget("builtins", "int")),
                default=ParameterDefault.value(20),
                help_key=TranslationKey("cli.config.repair.logs_lines_help"),
                constraint=ParameterConstraint(minimum=0),
            ),
        ),
        policy=LOCAL_READ,
        handler=_handler("_repair_cli", "repair_logs"),
        result_schema=_schema("RepairLogsResult", "config.repair.logs"),
    ),
    CommandSpec(
        key="config_repair_quarantine",
        parent_key="config_repair",
        token="quarantine",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.repair.quarantine_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            _flag("yes", "--yes", "cli.config.repair.quarantine_yes_help"),
            _flag("dry_run", "--dry-run/--no-dry-run", "cli.config.repair.quarantine_dry_run_help"),
        ),
        policy=BOOTSTRAP_WRITE,
        handler=_handler("_repair_cli", "repair_quarantine"),
        result_schema=_schema("RepairQuarantineResult", "config.repair.quarantine"),
    ),
    CommandSpec(
        key="config_repair_reset_progress",
        parent_key="config_repair",
        token="reset-progress",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.repair.reset_progress_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            _flag("yes", "--yes", "cli.config.repair.reset_progress_yes_help"),
            _flag("dry_run", "--dry-run/--no-dry-run", "cli.config.repair.reset_progress_dry_run_help"),
        ),
        policy=BOOTSTRAP_DESTRUCTIVE,
        handler=_handler("_repair_cli", "repair_reset_progress"),
        result_schema=_schema("RepairResetProgressResult", "config.repair.reset_progress"),
    ),
    CommandSpec(
        key="config_repair_integrity_objects",
        parent_key="config_repair_integrity",
        token="objects",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.repair.integrity.objects_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="namespace",
                declarations=("--namespace",),
                value=_STRING,
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.config.repair.integrity.objects_namespace_help"),
            ),
        ),
        policy=ENCRYPTED_READ,
        handler=_handler("_repair_cli", "repair_integrity_objects"),
        result_schema=_schema("RepairIntegrityObjectsResult", "config.repair.integrity.objects"),
    ),
    CommandSpec(
        key="config_repair_integrity_registry",
        parent_key="config_repair_integrity",
        token="registry",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.repair.integrity.registry_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(),
        policy=REGISTRY_READ,
        handler=_handler("_repair_cli", "repair_integrity_registry"),
        result_schema=_schema("RepairIntegrityRegistryResult", "config.repair.integrity.registry"),
    ),
    CommandSpec(
        key="config_repair_connectivity",
        parent_key="config_repair",
        token="connectivity",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.repair.connectivity_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_flag("headless", "--headless/--headed", None, default=True),),
        policy=BROWSER_CONNECTIVITY,
        handler=_handler("_repair_cli", "repair_connectivity"),
        result_schema=_schema("RepairConnectivityResult", "config.repair.connectivity"),
    ),
    CommandSpec(
        key="config_repair_profile",
        parent_key="config_repair",
        token="profile",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.repair.profile_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="profile",
                declarations=("--profile",),
                value=_STRING,
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.config.repair.profile_name_help"),
            ),
            _flag("clear_active", "--clear-active", "cli.config.repair.profile_clear_active_help"),
            _flag("yes", "--yes", "cli.config.repair.yes_help"),
        ),
        policy=BOOTSTRAP_WRITE,
        handler=_handler("_repair_profile", "repair_profile"),
        result_schema=_schema("RepairProfileResult", "config.repair.profile"),
    ),
    CommandSpec(
        key="config_repair_prepared_exports",
        parent_key="config_repair",
        token="prepared-exports",  # noqa: S106 - CLI token, not a credential.
        kind="leaf",
        help_key=TranslationKey("cli.config.repair.prepared_exports_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            OptionSpec(
                name="output_language",
                declarations=("--output-language", "--language"),
                value=ValueContract(DeferredTarget("cadrumo.core", "OutputLanguage")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.config.repair.prepared_exports_output_language_help"),
            ),
        ),
        policy=PROFILE_DESTRUCTIVE,
        handler=_handler("_repair_prepared_exports", "repair_prepared_exports"),
        result_schema=_schema("ProfileBundleReconcileResult", "config.repair.prepared_exports"),
    ),
)


__all__ = ["CONFIG_REPAIR_COMMAND_SPECS"]
