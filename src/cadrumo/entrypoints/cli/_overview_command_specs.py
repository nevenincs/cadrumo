"""Import-light command authority for the overview family."""

from __future__ import annotations

from .command_spec import (
    ArgumentSpec,
    CommandSpec,
    CommandWriteRoute,
    DeferredTarget,
    ExecutionPolicySpec,
    InvocationSpec,
    LazyBinding,
    OptionSpec,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    ValueContract,
)
from .command_spec import translation_key as _key

_METADATA = ExecutionPolicySpec(frozenset({"state-free"}), frozenset({"none"}), "metadata", CommandWriteRoute.NONE)
_READ = ExecutionPolicySpec(
    frozenset({"calculation", "encrypted-facts"}), frozenset({"none"}), "compute", CommandWriteRoute.NONE
)
_STR = ValueContract(DeferredTarget("builtins", "str"))
_INT = ValueContract(DeferredTarget("builtins", "int"))
_BOOL = ValueContract(DeferredTarget("builtins", "bool"))
_LANG = ValueContract(DeferredTarget("cadrumo.core.external_constants", "OutputLanguage"))
_MODULE = "cadrumo.entrypoints.cli._overview"
_PAYLOADS = "cadrumo.entrypoints.cli._overview_payloads"


def _option(
    name: str,
    declarations: tuple[str, ...],
    value: ValueContract,
    help_key: str,
    *,
    required: bool = False,
    default: str | int | bool | None = None,
) -> OptionSpec:
    return OptionSpec(
        name,
        declarations,
        value,
        ParameterDefault.required() if required else ParameterDefault.value(default),
        _key(help_key),
    )


def _leaf(
    key: str,
    token: str,
    help_key: str,
    schema: str,
    parameters: tuple[ArgumentSpec | OptionSpec, ...],
) -> CommandSpec:
    return CommandSpec(
        key,
        "app_overview",
        token,
        "leaf",
        _key(help_key),
        None,
        InvocationSpec(context_parameter="ctx"),
        parameters,
        _READ,
        LazyBinding.available(DeferredTarget(_MODULE, key.removeprefix("app_"))),
        ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget(_PAYLOADS, schema),
            identity=key.removeprefix("app_").replace("_", "."),
        ),
    )


OVERVIEW_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "app_overview",
        "app",
        "overview",
        "group",
        _key("cli.overview.app_help"),
        None,
        InvocationSpec(no_args_is_help=True),
        (),
        _METADATA,
        None,
        ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    _leaf(
        "app_overview_status",
        "status",
        "cli.overview.status_help",
        "OverviewStatusResult",
        (
            _option("period", ("--period",), _STR, "cli.overview.period_help"),
            _option("year", ("--year",), _INT, "cli.overview.year_help"),
            _option("verbose", ("--verbose",), _BOOL, "cli.overview.verbose_help", default=False),
        ),
    ),
    _leaf(
        "app_overview_calendar",
        "calendar",
        "cli.overview.calendar.help",
        "OverviewCalendarResult",
        (
            _option("from_date", ("--from",), _STR, "cli.overview.calendar.from_help", required=True),
            _option("to_date", ("--to",), _STR, "cli.overview.calendar.to_help", required=True),
            _option(
                "allow_incomplete",
                ("--allow-incomplete",),
                _BOOL,
                "cli.overview.calendar.allow_incomplete_help",
                default=False,
            ),
            _option(
                "show_suppressed",
                ("--show-suppressed",),
                _BOOL,
                "cli.overview.calendar.show_suppressed_help",
                default=False,
            ),
            _option(
                "all_profiles",
                ("--all-profiles",),
                _BOOL,
                "cli.overview.calendar.all_profiles_help",
                default=False,
            ),
            _option(
                "output_language",
                ("--output-language", "--language"),
                _LANG,
                "cli.config.auth.output_language_help",
            ),
        ),
    ),
    _leaf(
        "app_overview_agenda",
        "agenda",
        "cli.overview.agenda.help",
        "OverviewAgendaResult",
        (
            _option("as_of", ("--date",), _STR, "cli.overview.agenda.date_help"),
            _option("horizon_days", ("--horizon",), _INT, "cli.overview.agenda.horizon_help", default=14),
            _option(
                "allow_incomplete",
                ("--allow-incomplete",),
                _BOOL,
                "cli.overview.agenda.allow_incomplete_help",
                default=False,
            ),
        ),
    ),
    _leaf(
        "app_overview_backlog",
        "backlog",
        "cli.overview.backlog.help",
        "OverviewBacklogResult",
        (
            _option("from_date", ("--from",), _STR, "cli.overview.backlog.from_help"),
            _option("to_date", ("--to",), _STR, "cli.overview.backlog.to_help"),
            _option(
                "allow_incomplete",
                ("--allow-incomplete",),
                _BOOL,
                "cli.overview.backlog.allow_incomplete_help",
                default=False,
            ),
        ),
    ),
    _leaf(
        "app_overview_explain",
        "explain",
        "cli.overview.explain.help",
        "OverviewExplainResult",
        (
            ArgumentSpec("modelo", _STR, ParameterDefault.required(), _key("cli.overview.explain.modelo_help")),
            _option("year", ("--year",), _INT, "cli.overview.explain.year_help"),
        ),
    ),
    _leaf(
        "app_overview_prepare",
        "prepare",
        "cli.overview.prepare.help",
        "OverviewPrepareResult",
        (
            _option("modelo", ("--modelo",), _STR, "cli.overview.prepare.modelo_help", required=True),
            _option("year", ("--year",), _INT, "cli.overview.prepare.year_help", required=True),
            _option("period", ("--period",), _STR, "cli.overview.prepare.period_help", required=True),
        ),
    ),
    _leaf(
        "app_overview_pipeline",
        "pipeline",
        "cli.overview.pipeline.help",
        "OverviewPipelineResult",
        (
            _option("year", ("--year",), _INT, "cli.overview.pipeline.year_help", required=True),
            _option("period", ("--period",), _STR, "cli.overview.pipeline.period_help", required=True),
        ),
    ),
)

__all__ = ["OVERVIEW_COMMAND_SPECS"]
