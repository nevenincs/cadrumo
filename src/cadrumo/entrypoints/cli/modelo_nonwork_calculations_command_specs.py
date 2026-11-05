"""Declarative command specs for the modelo calculation commands outside a work unit."""

from __future__ import annotations

from cadrumo_client.commands.parameters import OptionSpec
from cadrumo_client.commands.shared_contracts import (
    FLAG_VALUE,
    DeferredTarget,
    LazyBinding,
    ParameterConstraint,
    ParameterDefault,
    ResultSchemaSpec,
    SchemaState,
    TranslationKey,
    ValueContract,
)
from cadrumo_client.commands.spec import CommandSpec, InvocationSpec
from cadrumo_client.contracts.command_ports import CommandNodeKind

from ...core.transport_locus import TransportLocus, TransportRole, TransportShape
from .modelo_nonwork_command_spec_policies import (
    CALCULATION_WRITE,
    MODEL_HANDOFF,
    REGISTRY_READ,
)
from .modelo_nonwork_common_command_parameters import (
    CALCULATION_REVISION_SELECTOR_OPTIONS,
    FILING_ELECTION_OPTIONS,
    boolean_flag_option,
    optional_text_argument,
    optional_text_option,
    optional_whole_number_option,
    repeatable_text_option,
    required_text_argument,
    required_text_option,
    required_whole_number_option,
)

MODELO_NONWORK_CALCULATION_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "app_modelo_formulas",
        "app_modelo",
        "formulas",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.formulas.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            required_text_argument("modelo", "cli.app.modelo.formulas.modelo_help"),
            optional_whole_number_option("year", ("--year",), "cli.app.modelo.list.year_help"),
            optional_text_option("period", ("--period",), "cli.app.modelo.formulas.period_help"),
            optional_text_option("as_of", ("--as-of",), "cli.app.modelo.formulas.as_of_help"),
            boolean_flag_option("explain", ("--explain",), "cli.app.modelo.formulas.explain_help"),
        ),
        policy=REGISTRY_READ,
        handler=LazyBinding.available(DeferredTarget(".modelo_discovery_commands", "formulas", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("...application.reference_catalogue_contracts", "FormulasResult", __package__),
            identity="modelo.formulas",
        ),
    ),
    CommandSpec(
        "app_modelo_support_matrix",
        "app_modelo",
        "support-matrix",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.support_matrix.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(),
        policy=REGISTRY_READ,
        handler=LazyBinding.available(DeferredTarget(".modelo_discovery_commands", "support_matrix", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("...application.reference_catalogue_contracts", "ModeloSupportMatrixResult", __package__),
            identity="modelo.support_matrix",
        ),
    ),
    CommandSpec(
        "app_modelo_aggregate",
        "app_modelo",
        "aggregate",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.aggregate_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            required_text_option("modelo", ("--modelo",), "cli.app.modelo.aggregate.modelo_help"),
            required_whole_number_option("year", ("--year",), "cli.app.modelo.work.year_help"),
            required_text_option("period", ("--period",), "cli.app.modelo.aggregate.period_help"),
            repeatable_text_option(
                "counterpart_observation",
                ("--counterpart-observation",),
                "cli.app.modelo.aggregate.counterpart_observation_help",
            ),
            repeatable_text_option(
                "foreign_asset_observation",
                ("--foreign-asset-observation",),
                "cli.app.modelo.aggregate.foreign_asset_observation_help",
            ),
            repeatable_text_option(
                "received_invoice_retencion",
                ("--received-invoice-retencion",),
                "cli.app.modelo.aggregate.received_invoice_retencion_help",
            ),
            repeatable_text_option(
                "ledger_payment_withholding",
                ("--ledger-payment-withholding",),
                "cli.app.modelo.aggregate.ledger_payment_withholding_help",
            ),
        ),
        policy=CALCULATION_WRITE,
        handler=LazyBinding.available(DeferredTarget(".modelo_aggregate_commands", "aggregate_modelo", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget(".modelo_query_results", "ModeloAggregateResult", __package__),
            identity="modelo.aggregate",
        ),
    ),
    CommandSpec(
        "app_modelo_export",
        "app_modelo",
        "export",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.export.help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            optional_text_argument("work_unit_id", "cli.app.modelo.export.work_unit_id_help"),
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
            optional_text_option("revision", ("--revision",), "cli.app.modelo.export.revision_help"),
            optional_text_option("actor", ("--by",), "cli.app.modelo.export.actor_help"),
            *FILING_ELECTION_OPTIONS,
            OptionSpec(
                name="replace_existing",
                declarations=("--replace",),
                value=FLAG_VALUE,
                default=ParameterDefault.value(False),
                help_key=TranslationKey("cli.app.modelo.export.replace_help"),
                is_flag=True,
                flag_value=True,
            ),
        ),
        policy=MODEL_HANDOFF,
        handler=LazyBinding.available(DeferredTarget(".modelo_export_commands", "modelo_export_verb", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget(".modelo_query_results", "ModeloExportPayload", __package__),
            identity="modelo.export",
        ),
    ),
)

__all__ = ["MODELO_NONWORK_CALCULATION_COMMAND_SPECS"]
"""Authored CommandSpec declarations for the Modelo non-work calculations family."""
"""Authored CommandSpec declarations for the Modelo non-work calculations family."""
