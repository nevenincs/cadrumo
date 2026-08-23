"""Import-light command authority for the diagnostics family."""

from __future__ import annotations

from ._command_spec import (
    CommandSpec,
    DeferredTarget,
    ExecutionPolicySpec,
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

_READ = ExecutionPolicySpec(frozenset({"local-storage"}), frozenset({"none"}), "local-io", "none")
_WRITE = ExecutionPolicySpec(frozenset({"local-storage"}), frozenset({"local-state"}), "local-io", "none")
_METADATA = ExecutionPolicySpec(frozenset({"state-free"}), frozenset({"none"}), "metadata", "none")
_STR = ValueContract(DeferredTarget("builtins", "str"))
_INT = ValueContract(DeferredTarget("builtins", "int"))
_BOOL = ValueContract(DeferredTarget("builtins", "bool"))
_TIER = ValueContract(DeferredTarget("cadrumo.core.telemetry", "TelemetryTier"))
_PAYLOADS = "cadrumo.entrypoints.cli._diagnostics_payloads"


def _key(value: str) -> TranslationKey:
    return TranslationKey(value)


def _option(
    name: str,
    declarations: tuple[str, ...],
    value: ValueContract,
    help_key: str,
    *,
    default: str | int | bool | None = None,
    minimum: int | None = None,
) -> OptionSpec:
    return OptionSpec(
        name=name,
        declarations=declarations,
        value=value,
        default=ParameterDefault.value(default),
        help_key=_key(help_key),
        constraint=ParameterConstraint(minimum=minimum),
    )


def _leaf(
    key: str,
    parent: str,
    token: str,
    help_key: str,
    module: str,
    handler: str,
    schema: str,
    policy: ExecutionPolicySpec,
    parameters: tuple[OptionSpec, ...],
) -> CommandSpec:
    return CommandSpec(
        key=key,
        parent_key=parent,
        token=token,
        kind="leaf",
        help_key=_key(help_key),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=parameters,
        policy=policy,
        handler=LazyBinding.available(DeferredTarget(module, handler)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget(_PAYLOADS, schema),
            identity=key.replace("_", "."),
        ),
    )


def _range(prefix: str, *, limit: bool = False) -> tuple[OptionSpec, ...]:
    values = (
        _option("since", ("--since",), _STR, f"cli.diagnostics.{prefix}.since_help"),
        _option("until", ("--until",), _STR, f"cli.diagnostics.{prefix}.until_help"),
        _option("provider", ("--provider",), _STR, f"cli.diagnostics.{prefix}.provider_help"),
    )
    if not limit:
        return values
    return (*values, _option("limit", ("--limit",), _INT, "cli.diagnostics.runs.limit_help", minimum=1))


_TELEMETRY_COMMON = (
    _option("opt_in", ("--opt-in/--no-opt-in",), _BOOL, "cli.diagnostics.telemetry.opt_in_help"),
    _option("tier", ("--tier",), _TIER, "cli.diagnostics.telemetry.tier_help"),
    _option("endpoint", ("--endpoint",), _STR, "cli.diagnostics.telemetry.endpoint_help"),
)

DIAGNOSTICS_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "app_diagnostics",
        "app",
        "diagnostics",
        "group",
        _key("cli.diagnostics.app_help"),
        None,
        InvocationSpec(
            invoke_without_command=True,
            no_args_is_help=True,
            context_parameter="ctx",
            terminal_behavior="introspection",
        ),
        (),
        _READ,
        LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._app_diagnostics", "diagnostics_root")),
        ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    _leaf(
        "app_diagnostics_run_health",
        "app_diagnostics",
        "run-health",
        "cli.diagnostics.run_health.help",
        "cadrumo.entrypoints.cli._app_diagnostics",
        "diagnostics_run_health",
        "RunHealthResult",
        _READ,
        _range("run_health"),
    ),
    _leaf(
        "app_diagnostics_runs",
        "app_diagnostics",
        "runs",
        "cli.diagnostics.runs.help",
        "cadrumo.entrypoints.cli._app_diagnostics",
        "diagnostics_runs",
        "RunsListResult",
        _READ,
        _range("runs", limit=True),
    ),
    _leaf(
        "app_diagnostics_latency",
        "app_diagnostics",
        "latency",
        "cli.diagnostics.latency.help",
        "cadrumo.entrypoints.cli._app_diagnostics",
        "diagnostics_latency",
        "LatencyResult",
        _READ,
        _range("latency"),
    ),
    _leaf(
        "app_diagnostics_errors",
        "app_diagnostics",
        "errors",
        "cli.diagnostics.errors.help",
        "cadrumo.entrypoints.cli._app_diagnostics",
        "diagnostics_errors",
        "ErrorsBreakdownResult",
        _READ,
        _range("errors"),
    ),
    _leaf(
        "app_diagnostics_llm_usage",
        "app_diagnostics",
        "llm-usage",
        "cli.diagnostics.llm_usage.help",
        "cadrumo.entrypoints.cli._app_diagnostics",
        "diagnostics_llm_usage",
        "LlmUsageResult",
        _READ,
        _range("llm_usage"),
    ),
    CommandSpec(
        "app_diagnostics_telemetry",
        "app_diagnostics",
        "telemetry",
        "group",
        _key("cli.diagnostics.telemetry.app_help"),
        None,
        InvocationSpec(no_args_is_help=True),
        (),
        _METADATA,
        None,
        ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    _leaf(
        "app_diagnostics_telemetry_status",
        "app_diagnostics_telemetry",
        "status",
        "cli.diagnostics.telemetry.status.help",
        "cadrumo.entrypoints.cli._app_diagnostics_telemetry",
        "diagnostics_telemetry_status",
        "TelemetryStatusResult",
        _READ,
        _TELEMETRY_COMMON,
    ),
    _leaf(
        "app_diagnostics_telemetry_flush",
        "app_diagnostics_telemetry",
        "flush",
        "cli.diagnostics.telemetry.flush.help",
        "cadrumo.entrypoints.cli._app_diagnostics_telemetry",
        "diagnostics_telemetry_flush",
        "TelemetryFlushResult",
        _WRITE,
        (
            _option(
                "dry_run",
                ("--dry-run/--no-dry-run",),
                _BOOL,
                "cli.diagnostics.telemetry.flush.dry_run_help",
                default=True,
            ),
            *_TELEMETRY_COMMON,
            _option(
                "acknowledge",
                ("--acknowledge-remote-telemetry",),
                _BOOL,
                "cli.diagnostics.telemetry.flush.acknowledge_help",
                default=False,
            ),
        ),
    ),
)

__all__ = ["DIAGNOSTICS_COMMAND_SPECS"]
