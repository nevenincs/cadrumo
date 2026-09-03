"""Authored CommandSpec declarations for the Modelo non-work filing record family."""

# ruff: noqa: S106 - command tokens are operator verbs, never credentials

from __future__ import annotations

from ...core.transport_locus import TransportLocus, TransportRole, TransportShape
from ._modelo_nonwork_command_spec_policies import (
    _MODEL_READ,
    _MODEL_WRITE,
)
from ._modelo_nonwork_common_command_parameters import (
    _boolean_flag_option,
    _optional_text_option,
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

MODELO_NONWORK_FILING_RECORD_COMMAND_SPECS: tuple[CommandSpec, ...] = (
    CommandSpec(
        key="app_modelo_filing_record_list",
        parent_key="app_modelo_filing_record",
        token="list",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.filing_record.list_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            _optional_text_option("bucket_id", ("--bucket-id",), "cli.app.modelo.filing_record.bucket_id_help"),
            _optional_text_option("modelo", ("--modelo",), "cli.app.modelo.filing_record.modelo_help"),
            _boolean_flag_option(
                "include_superseded", ("--include-superseded",), "cli.app.modelo.filing_record.include_superseded_help"
            ),
        ),
        policy=_MODEL_READ,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._modelo_records_cli", "filing_record_list")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._modelo_payloads", "ModeloRecordListResult"),
            identity="modelo.filing_record.list",
        ),
    ),
    CommandSpec(
        key="app_modelo_filing_record_view",
        parent_key="app_modelo_filing_record",
        token="view",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.filing_record.view_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(_required_text_argument("filing_record_id", "cli.app.modelo.filing_record.filing_record_id_help"),),
        policy=_MODEL_READ,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._modelo_records_cli", "filing_record_show")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._modelo_payloads", "ModeloRecordShowResult"),
            identity="modelo.filing_record.view",
        ),
    ),
    CommandSpec(
        key="app_modelo_filing_record_import",
        parent_key="app_modelo_filing_record",
        token="import",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.filing_record.import_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            _required_text_argument("work_unit_id", "cli.app.modelo.work.work_unit_id_help"),
            OptionSpec(
                name="evidence_kind",
                declarations=("--evidence-kind",),
                value=ValueContract(DeferredTarget("cadrumo.domain.modelos.filing_record", "ExternalEvidenceKind")),
                default=ParameterDefault.required(),
                help_key=TranslationKey("cli.app.modelo.filing_record.evidence_kind_help"),
                multiple=False,
                is_flag=False,
                flag_value=None,
                constraint=ParameterConstraint(),
            ),
            _required_text_option(
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
            _repeatable_text_option("set_overrides", ("--set",), "cli.app.modelo.filing_record.import_casilla_help"),
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
        ),
        policy=_MODEL_WRITE,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._modelo_records_cli", "filing_record_import")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._modelo_payloads", "FilingRecordImportResult"),
            identity="modelo.filing_record.import",
        ),
    ),
    CommandSpec(
        key="app_modelo_filing_record_observe_local",
        parent_key="app_modelo_filing_record",
        token="observe-local",
        kind=CommandNodeKind.LEAF,
        help_key=TranslationKey("cli.app.modelo.filing_record.observe_local_help"),
        short_help_key=None,
        invocation=InvocationSpec(context_parameter="ctx"),
        parameters=(
            _required_text_option("modelo", ("--modelo",), "cli.app.modelo.work.modelo_help"),
            _required_whole_number_option("year", ("--year",), "cli.app.modelo.work.year_help"),
            _required_text_option("period", ("--period",), "cli.app.modelo.work.period_help"),
            _optional_text_option("actor", ("--by",), "cli.app.modelo.work.actor_help"),
            _repeatable_text_option("set_overrides", ("--set",), "cli.app.modelo.filing_record.observe_local_set_help"),
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
            _boolean_flag_option(
                "replace_official_evidence",
                ("--replace-official-evidence",),
                "cli.app.modelo.filing_record.observe_local_replace_official_evidence_help",
            ),
        ),
        policy=_MODEL_WRITE,
        handler=LazyBinding.available(
            DeferredTarget("cadrumo.entrypoints.cli._modelo_records_cli", "filing_record_observe_local")
        ),
        result_schema=ResultSchemaSpec(
            SchemaState.TARGET,
            DeferredTarget("cadrumo.entrypoints.cli._modelo_payloads", "FilingRecordLocalObservationResult"),
            identity="modelo.filing_record.observe_local",
        ),
    ),
)

__all__ = ["MODELO_NONWORK_FILING_RECORD_COMMAND_SPECS"]
