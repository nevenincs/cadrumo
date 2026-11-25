"""Declarative command specs for the modelo filing record commands outside a work unit."""

from __future__ import annotations

from cadrumo_client.commands.parameters import OptionSpec
from cadrumo_client.commands.shared_contracts import (
    PATH_VALUE,
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
    MODEL_READ,
    MODEL_WRITE,
)
from .modelo_nonwork_common_command_parameters import (
    boolean_flag_option,
    optional_text_option,
    repeatable_text_option,
    required_text_argument,
    required_text_option,
    required_whole_number_option,
)

MODELO_NONWORK_FILING_RECORD_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        "app_modelo_filing_record_export",
        "app_modelo_filing_record",
        "export",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.filing_record.export_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            required_text_argument("filing_record_id", "cli.app.modelo.filing_record.filing_record_id_help"),
            OptionSpec(
                name="output",
                declarations=("--output",),
                value=PATH_VALUE,
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.app.modelo.spreadsheet.export.output_help"),
                transport_locus=TransportLocus.LOCAL_OUT,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.PRIMARY,
            ),
            boolean_flag_option("replace_existing", ("--replace",), "cli.app.modelo.export.replace_help"),
        ),
        policy=MODEL_WRITE,
        handler=LazyBinding.available(
            DeferredTarget(".historical_export_cli", "export_historical_filing_cli", __package__)
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget(".calculation_review_cli", "CalculationReviewWorkbookResult", __package__),
            identity="modelo.filing_record.export",
        ),
    ),
    CommandSpec(
        "app_modelo_filing_record_list",
        "app_modelo_filing_record",
        "list",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.filing_record.list_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            optional_text_option("bucket_id", ("--bucket-id",), "cli.app.modelo.filing_record.bucket_id_help"),
            optional_text_option("modelo", ("--modelo",), "cli.app.modelo.filing_record.modelo_help"),
            boolean_flag_option(
                "include_superseded", ("--include-superseded",), "cli.app.modelo.filing_record.include_superseded_help"
            ),
        ),
        policy=MODEL_READ,
        handler=LazyBinding.available(DeferredTarget(".modelo_records_commands", "filing_record_list", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget(".modelo_results", "ModeloRecordListResult", __package__),
            identity="modelo.filing_record.list",
        ),
    ),
    CommandSpec(
        "app_modelo_filing_record_view",
        "app_modelo_filing_record",
        "view",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.filing_record.view_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(required_text_argument("filing_record_id", "cli.app.modelo.filing_record.filing_record_id_help"),),
        policy=MODEL_READ,
        handler=LazyBinding.available(DeferredTarget(".modelo_records_commands", "filing_record_show", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget(".modelo_results", "ModeloRecordShowResult", __package__),
            identity="modelo.filing_record.view",
        ),
    ),
    CommandSpec(
        "app_modelo_filing_record_import",
        "app_modelo_filing_record",
        "import",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.filing_record.import_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            required_text_argument("work_unit_id", "cli.app.modelo.work.work_unit_id_help"),
            OptionSpec(
                name="evidence_kind",
                declarations=("--evidence-kind",),
                value=ValueContract(
                    DeferredTarget("...domain.modelos.filing_record", "ExternalEvidenceKind", __package__)
                ),
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.app.modelo.filing_record.evidence_kind_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(),
            ),
            required_text_option(
                "evidence_reference_id", ("--evidence-id",), "cli.app.modelo.filing_record.evidence_reference_id_help"
            ),
            OptionSpec(
                name="actor",
                declarations=("--by",),
                value=ValueContract(DeferredTarget("builtins", "str")),
                default=ParameterDefault.value("aeat-import"),
                help_key=TranslationKey("cli.app.modelo.work.actor_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(),
            ),
            repeatable_text_option("set_overrides", ("--set",), "cli.app.modelo.filing_record.import_casilla_help"),
            OptionSpec(
                name="file",
                declarations=("--file",),
                value=ValueContract(DeferredTarget("pathlib", "Path")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.app.modelo.filing_record.import_file_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(exists=True, dir_okay=False),
                transport_locus=TransportLocus.LOCAL_IN,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.PRIMARY,
            ),
            OptionSpec(
                name="declared_kind",
                declarations=("--declared-kind",),
                value=ValueContract(
                    DeferredTarget("...domain.modelos.filing_record", "FilingDeclarationKind", __package__)
                ),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.app.modelo.filing_record.import_declared_kind_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(),
            ),
        ),
        policy=MODEL_WRITE,
        handler=LazyBinding.available(DeferredTarget(".modelo_records_commands", "filing_record_import", __package__)),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget(".modelo_results", "FilingRecordImportResult", __package__),
            identity="modelo.filing_record.import",
        ),
    ),
    CommandSpec(
        "app_modelo_filing_record_observe_local",
        "app_modelo_filing_record",
        "observe-local",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.filing_record.observe_local_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            required_text_option("modelo", ("--modelo",), "cli.app.modelo.work.modelo_help"),
            required_whole_number_option("year", ("--year",), "cli.app.modelo.work.year_help"),
            required_text_option("period", ("--period",), "cli.app.modelo.work.period_help"),
            required_text_option("reason", ("--reason",), "cli.app.modelo.filing_record.observe_local_reason_help"),
            optional_text_option("actor", ("--by",), "cli.app.modelo.work.actor_help"),
            repeatable_text_option("set_overrides", ("--set",), "cli.app.modelo.filing_record.observe_local_set_help"),
            OptionSpec(
                name="file",
                declarations=("--file",),
                value=ValueContract(DeferredTarget("pathlib", "Path")),
                default=ParameterDefault.value(None),
                help_key=TranslationKey("cli.app.modelo.filing_record.observe_local_file_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(),
                transport_locus=TransportLocus.LOCAL_IN,
                transport_shape=TransportShape.FILE,
                transport_role=TransportRole.PRIMARY,
            ),
            boolean_flag_option("clear", ("--clear",), "cli.app.modelo.filing_record.observe_local_clear_help"),
        ),
        policy=MODEL_WRITE,
        handler=LazyBinding.available(
            DeferredTarget(".modelo_records_commands", "filing_record_observe_local", __package__)
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget(".modelo_results", "FilingRecordLocalObservationResult", __package__),
            identity="modelo.filing_record.observe_local",
        ),
    ),
)

__all__ = ["MODELO_NONWORK_FILING_RECORD_COMMAND_SPECS"]
"""Authored CommandSpec declarations for the Modelo non-work filing record family."""
"""Authored CommandSpec declarations for the Modelo non-work filing record family."""
