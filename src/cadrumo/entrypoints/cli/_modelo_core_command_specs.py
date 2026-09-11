"""Import-light command authority for the modelo root and work core verbs."""

from __future__ import annotations

from .command_spec import (
    FLAG_VALUE,
    TEXT_VALUE,
    WHOLE_NUMBER_VALUE,
    ArgumentSpec,
    CommandNodeKind,
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
_CALCULATION_READ = ExecutionPolicySpec(
    frozenset({"calculation", "encrypted-facts"}), frozenset({"none"}), "compute", CommandWriteRoute.NONE
)
_MODEL_READ = ExecutionPolicySpec(
    frozenset({"encrypted-facts"}), frozenset({"none"}), "local-io", CommandWriteRoute.NONE
)
_CALCULATION_WRITE = ExecutionPolicySpec(
    frozenset({"calculation", "encrypted-facts"}),
    frozenset({"local-state"}),
    "compute",
    CommandWriteRoute.PROFILE_BOUND,
)
_LANGUAGE = ValueContract(DeferredTarget("...core.external_constants", "OutputLanguage", __package__))
_MODELO = ValueContract(
    DeferredTarget("builtins", "str"),
    click_type=DeferredTarget(".common", "MODELO_CODE_CHOICE", __package__),
)
_AMENDMENT_KIND = ValueContract(
    DeferredTarget("...domain.modelos.calculation_revision_amendment", "CalculationRevisionAmendmentKind", __package__)
)
_M303_MOTIVE = ValueContract(
    DeferredTarget("...domain.modelos.calculation_revision_amendment", "M303RectificativaMotive", __package__)
)


def _option(
    name: str,
    declarations: tuple[str, ...],
    value: ValueContract,
    help_key: str,
    *,
    multiple: bool = False,
) -> OptionSpec:
    return OptionSpec(
        name=name,
        declarations=declarations,
        value=value,
        default=ParameterDefault.value(() if multiple else None),
        help_key=_key(help_key),
        multiple=multiple,
    )


def _leaf(
    key: str,
    parent_key: str,
    token: str,
    help_key: str,
    handler: str,
    parameters: tuple[ArgumentSpec | OptionSpec, ...],
    policy: ExecutionPolicySpec,
    schema_module: str,
    schema_name: str,
    identity: str,
) -> CommandSpec:
    return CommandSpec(
        key,
        parent_key,
        token,
        CommandNodeKind.LEAF,
        _key(help_key),
        None,
        InvocationSpec(context_parameter="ctx"),
        parameters,
        policy,
        LazyBinding.available(DeferredTarget("._modelo", handler, __package__)),
        ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget(schema_module, schema_name, __package__),
            identity=identity,
        ),
    )


_ADDRESS_OPTIONS = (
    _option("modelo", ("--modelo",), _MODELO, "cli.app.modelo.work.modelo_help"),
    _option("year", ("--year",), WHOLE_NUMBER_VALUE, "cli.app.modelo.work.year_help"),
    _option("period", ("--period",), TEXT_VALUE, "cli.app.modelo.work.period_help"),
    _option("revision", ("--revision",), TEXT_VALUE, "cli.app.modelo.work.revision_help"),
    _option("bucket_id", ("--bucket-id",), TEXT_VALUE, "cli.app.modelo.work.bucket_id_help"),
)

MODELO_CORE_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "app_modelo_work",
        "app_modelo",
        "work",
        CommandNodeKind.GROUP,
        _key("cli.app.modelo.work.app_help"),
        None,
        InvocationSpec(no_args_is_help=True),
        (),
        _METADATA,
        None,
        ResultSchemaSpec(SchemaState.NOT_SUPPORTED),
    ),
    _leaf(
        "app_modelo_work_compare_taxation",
        "app_modelo_work",
        "compare-taxation",
        "cli.app.modelo.work.compare_taxation_help",
        "work_compare_taxation",
        (
            ArgumentSpec(
                "work_unit_id", TEXT_VALUE, ParameterDefault.value(None), _key("cli.app.modelo.work.work_unit_id_help")
            ),
            *_ADDRESS_OPTIONS,
            _option(
                "output_language",
                ("--output-language",),
                _LANGUAGE,
                "cli.app.modelo.work.output_language_help",
            ),
        ),
        _CALCULATION_READ,
        "._payloads_modelo_reconcile",
        "WorkCompareTaxationResult",
        "modelo.work.compare_taxation",
    ),
    _leaf(
        "app_modelo_work_history",
        "app_modelo_work",
        "history",
        "cli.app.modelo.work.history_help",
        "work_history",
        (
            ArgumentSpec(
                "work_unit_id",
                TEXT_VALUE,
                ParameterDefault.value(None),
                _key("cli.app.modelo.work.history_work_unit_id_help"),
            ),
            *_ADDRESS_OPTIONS,
            _option(
                "output_language",
                ("--output-language", "--language"),
                _LANGUAGE,
                "cli.config.auth.output_language_help",
            ),
        ),
        _MODEL_READ,
        ".modelo_aux_payloads",
        "WorkHistoryResult",
        "modelo.work.history",
    ),
    _leaf(
        "app_modelo_work_amend",
        "app_modelo_work",
        "amend",
        "cli.app.modelo.work.amend_help",
        "work_amend",
        (
            _option(
                "from_filing_record_id",
                ("--from-filing-record",),
                TEXT_VALUE,
                "cli.app.modelo.work.from_filing_record_help",
            ),
            _option("kind", ("--kind",), _AMENDMENT_KIND, "cli.app.modelo.work.amendment_kind_help"),
            _option("reason", ("--reason",), TEXT_VALUE, "cli.app.modelo.work.amendment_reason_help"),
            _option(
                "m303_rectificativa_motive",
                ("--m303-rectificativa-motive",),
                _M303_MOTIVE,
                "cli.app.modelo.work.m303_rectificativa_motive_help",
            ),
            _option("actor", ("--by",), TEXT_VALUE, "cli.app.modelo.work.actor_help"),
            _option(
                "set_overrides",
                ("--set",),
                TEXT_VALUE,
                "cli.app.modelo.work.set_override_help",
                multiple=True,
            ),
            # The rows an amendment declares, and the separate statement that
            # it declares none. Two flags rather than one because absence and
            # emptiness are different answers here: see
            # ``_resolve_amendment_detail_rows``.
            _option("row", ("--row",), TEXT_VALUE, "cli.app.modelo.work.row_help", multiple=True),
            OptionSpec(
                name="no_detail_rows",
                declarations=("--no-detail-rows",),
                value=FLAG_VALUE,
                default=ParameterDefault.value(False),
                help_key=_key("cli.app.modelo.work.amend_no_detail_rows_help"),
                is_flag=True,
            ),
        ),
        _CALCULATION_WRITE,
        "._modelo_payloads",
        "WorkAmendResult",
        "modelo.work.amend",
    ),
    _leaf(
        "app_modelo_history",
        "app_modelo",
        "history",
        "cli.app.modelo.history_help",
        "modelo_history",
        (
            OptionSpec(
                "modelo",
                ("--modelo",),
                _MODELO,
                ParameterDefault.required(),
                _key("cli.app.modelo.history.modelo_help"),
            ),
            _option("year", ("--year",), WHOLE_NUMBER_VALUE, "cli.app.modelo.history.year_help"),
            _option("period", ("--period",), TEXT_VALUE, "cli.app.modelo.history.period_help"),
        ),
        _MODEL_READ,
        "._modelo_payloads",
        "ModeloHistoryResult",
        "modelo.history",
    ),
)

__all__ = ["MODELO_CORE_COMMAND_SPECS"]
