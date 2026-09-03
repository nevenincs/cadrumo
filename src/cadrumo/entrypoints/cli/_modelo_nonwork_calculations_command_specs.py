"""Authored CommandSpec declarations for the Modelo non-work calculations family."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from ...core.transport_locus import TransportLocus, TransportRole, TransportShape
from ._modelo_nonwork_command_spec_policies import (
    _CALCULATION_WRITE,
    _MODEL_HANDOFF,
    _REGISTRY_READ,
)
from ._modelo_nonwork_common_command_parameters import (
    CALCULATION_REVISION_SELECTOR_OPTIONS,
    FILING_ELECTION_OPTIONS,
    _boolean_flag_option,
    _optional_text_argument,
    _optional_text_option,
    _optional_whole_number_option,
    _repeatable_text_option,
    _required_text_argument,
    _required_text_option,
    _required_whole_number_option,
)
from .command_spec import (
    CommandNodeKind,
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

MODELO_NONWORK_CALCULATION_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_modelo_formulas",
        parent_key="app_modelo",
        token="formulas",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.formulas.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            _required_text_argument("modelo", "cli.app.modelo.formulas.modelo_help"),
            _optional_whole_number_option("year", ("--year",), "cli.app.modelo.list.year_help"),
            _optional_text_option("period", ("--period",), "cli.app.modelo.formulas.period_help"),
            _optional_text_option("as_of", ("--as-of",), "cli.app.modelo.formulas.as_of_help"),
            _boolean_flag_option("explain", ("--explain",), "cli.app.modelo.formulas.explain_help"),
        ),
        policy=_REGISTRY_READ,
        handler=LazyBinding.available(DeferredTarget("cadrumo.entrypoints.cli._modelo_discovery_cli", "formulas")),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._modelo_payloads", "FormulasResult"),
            identity="modelo.formulas",
        ),
    ),
    CommandSpec(
        key="app_modelo_support_matrix",
        parent_key="app_modelo",
        token="support-matrix",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.support_matrix.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(),
        policy=_REGISTRY_READ,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._modelo_discovery_cli", "support_matrix")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._modelo_support_matrix_payloads", "ModeloSupportMatrixResult"),
            identity="modelo.support_matrix",
        ),
    ),
    CommandSpec(
        key="app_modelo_aggregate",
        parent_key="app_modelo",
        token="aggregate",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.aggregate_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            _required_text_option("modelo", ("--modelo",), "cli.app.modelo.aggregate.modelo_help"),
            _required_whole_number_option("year", ("--year",), "cli.app.modelo.work.year_help"),
            _required_text_option("period", ("--period",), "cli.app.modelo.aggregate.period_help"),
            _repeatable_text_option(
                "retencion_observation",
                ("--retencion-observation",),
                "cli.app.modelo.aggregate.retencion_observation_help",
            ),
            _repeatable_text_option(
                "counterpart_observation",
                ("--counterpart-observation",),
                "cli.app.modelo.aggregate.counterpart_observation_help",
            ),
            _repeatable_text_option(
                "foreign_asset_observation",
                ("--foreign-asset-observation",),
                "cli.app.modelo.aggregate.foreign_asset_observation_help",
            ),
            _repeatable_text_option(
                "withholding_observation",
                ("--withholding-observation",),
                "cli.app.modelo.aggregate.withholding_observation_help",
            ),
            _repeatable_text_option(
                "received_invoice_retencion",
                ("--received-invoice-retencion",),
                "cli.app.modelo.aggregate.received_invoice_retencion_help",
            ),
        ),
        policy=_CALCULATION_WRITE,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._modelo_aggregate_cli", "aggregate_modelo")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._modelo_payloads", "ModeloAggregateResult"),
            identity="modelo.aggregate",
        ),
    ),
    CommandSpec(
        key="app_modelo_export",
        parent_key="app_modelo",
        token="export",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.export.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            _optional_text_argument("work_unit_id", "cli.app.modelo.export.work_unit_id_help"),
            *CALCULATION_REVISION_SELECTOR_OPTIONS,
            OptionSpec(
                name="output",
                declarations=("--output",),
                value=ValueContract(DeferredTarget("pathlib", "Path")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.app.modelo.export.output_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(),
                transport_locus=TransportLocus.LOCAL_OUT,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.PRIMARY,
            ),
            _optional_text_option("revision", ("--revision",), "cli.app.modelo.export.revision_help"),
            _optional_text_option("actor", ("--by",), "cli.app.modelo.export.actor_help"),
            *FILING_ELECTION_OPTIONS,
        ),
        policy=_MODEL_HANDOFF,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._modelo_export_cli", "modelo_export_verb")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._modelo_payloads", "ModeloExportPayload"),
            identity="modelo.export",
        ),
    ),
)

__all__ = ["MODELO_NONWORK_CALCULATION_COMMAND_SPECS"]
