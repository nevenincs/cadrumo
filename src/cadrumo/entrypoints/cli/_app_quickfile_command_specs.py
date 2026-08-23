"""Import-light command authority for the executable quickfile group."""

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

_POLICY = ExecutionPolicySpec(
    frozenset({"calculation", "encrypted-facts", "filing"}),
    frozenset({"local-state"}),
    "compute",
    "profile-bound",
    handoff=True,
)
_STR = ValueContract(DeferredTarget("builtins", "str"))
_INT = ValueContract(DeferredTarget("builtins", "int"))
_PATH = ValueContract(DeferredTarget("pathlib", "Path"))
_LANG = ValueContract(DeferredTarget("cadrumo.core", "OutputLanguage"))


def _option(
    name: str,
    declarations: tuple[str, ...],
    value: ValueContract,
    help_key: str,
    *,
    required: bool = False,
    default: str | tuple[str, ...] | None = None,
    multiple: bool = False,
) -> OptionSpec:
    return OptionSpec(
        name,
        declarations,
        value,
        ParameterDefault.required() if required else ParameterDefault.value(default),
        TranslationKey(help_key),
        multiple=multiple,
    )


QUICKFILE_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "app_quickfile",
        "app",
        "quickfile",
        "group",
        TranslationKey("cli.app.quickfile.app_help"),
        None,
        InvocationSpec(invoke_without_command=True, add_completion=True, context_parameter="ctx"),
        (
            _option("modelo", ("--modelo",), _STR, "cli.app.modelo.work.modelo_help", required=True),
            _option("year", ("--year",), _INT, "cli.app.modelo.work.year_help", required=True),
            _option("period", ("--period",), _STR, "cli.app.modelo.work.period_help", required=True),
            _option("output", ("--output",), _PATH, "cli.app.modelo.export.output_help"),
            _option("revision", ("--revision",), _STR, "cli.app.modelo.work.revision_help"),
            _option("bucket_id", ("--bucket-id",), _STR, "cli.app.modelo.work.bucket_id_help"),
            _option("casilla", ("--casilla",), _STR, "cli.app.modelo.work.casilla_help", multiple=True),
            _option("binding", ("--binding",), _STR, "cli.app.modelo.work.override_help", multiple=True),
            _option("relation", ("--relation",), _STR, "cli.app.modelo.work.relation_help", multiple=True),
            _option("row", ("--row",), _STR, "cli.app.modelo.work.row_help", multiple=True),
            _option("actor", ("--by",), _STR, "cli.app.modelo.work.actor_help"),
            _option(
                "refund_election",
                ("--refund-election",),
                ValueContract(DeferredTarget("cadrumo.core", "RefundElection")),
                "cli.app.modelo.work.refund_election_help",
                default="compensar",
            ),
            _option(
                "payment_election",
                ("--payment-election",),
                ValueContract(DeferredTarget("cadrumo.core", "PaymentElection")),
                "cli.app.modelo.work.payment_election_help",
                default="ingreso",
            ),
            _option(
                "prior_domiciliation_election",
                ("--prior-domiciliation-election",),
                ValueContract(DeferredTarget("cadrumo.core", "PriorDomiciliationElection")),
                "cli.app.modelo.work.prior_domiciliation_election_help",
                default="keep",
            ),
            _option(
                "m303_filing_evidence",
                ("--m303-filing-evidence",),
                _PATH,
                "cli.app.modelo.work.m303_filing_evidence_help",
            ),
            _option(
                "output_language",
                ("--output-language", "--language"),
                _LANG,
                "cli.config.auth.output_language_help",
            ),
        ),
        _POLICY,
        LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._app_quickfile", "quickfile")),
        ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._app_quickfile_payloads", "QuickfileResultPayload"),
            identity="app.quickfile",
        ),
    ),
)

__all__ = ["QUICKFILE_COMMAND_SPECS"]
