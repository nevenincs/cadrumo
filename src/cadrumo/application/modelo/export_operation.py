"""Register modelo lifecycle operations using their canonical writers and public contracts.

Core types: :class:`~cadrumo.domain.modelos.filing_record.ModeloRecord`,
:class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`.
"""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.calculation_report_format import CalculationReportDocumentFormat
from ...core.modelo_export_artefact import ModeloExportArtefact
from ...core.operations import (
    EFFECTS_WITHOUT_PARTIAL_COMMIT,
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationInteractionKind,
)
from ...core.time.clock import now as _utc_now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ..operations.access_port import OperationAccessResolver
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.execution_actor import OperationExecutionCallerReader, execution_actor_label
from ..operations.models import (
    OperationTerminalReceipt,
    require_succeeded_terminal_receipt,
)
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.registry import (
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..operations.subject_reference import OperationSubjectReferenceV1
from .calculation_report_export import (
    ModeloCalculationReportCommand,
    ModeloCalculationReportResult,
    export_modelo_calculation_report,
)
from .export import export_modelo_revision
from .export_contracts import ModeloExportCommand, ModeloExportResult
from .export_ports import ModeloExportPorts, ModeloExportPortsFactory
from .export_projection import (
    ModeloCalculationReportPublicReceipt,
    ModeloExportCompleteness,
    ModeloExportEvidenceStatus,
    ModeloExportPublicResultV3,
    ModeloFicheroBoePublicReceipt,
)
from .review_package_signing_ports import ReviewPackageSigningKeypairCapabilityFactory
from .work_export_contracts import ModeloExportRequest, ModeloExportSettledResult

if TYPE_CHECKING:
    from ...domain.deadlines.models import TaxpayerProfile
    from ..operations.models import OperationRequest
    from ..operations.owner import OperationExecutorContext
    from .calculation_summary_pdf_ports import CalculationSummaryPdfWriter


from .operation_shared import (
    MODELO_EXPORT_OPERATION_DEFINITION_ID,
    ModeloWorkVerifyProfileResolver,
    modelo_workspace_refresh_target_binding,
    resolve_active_workflow_profile,
    resolve_modelo_work_unit_refresh_target,
)

_REPORT_DOCUMENT_FORMATS: Mapping[ModeloExportArtefact, CalculationReportDocumentFormat] = MappingProxyType(
    {
        ModeloExportArtefact.CALCULATION_REPORT_CSV: CalculationReportDocumentFormat.CSV,
        ModeloExportArtefact.CALCULATION_REPORT_PDF: CalculationReportDocumentFormat.PDF,
    },
)


_REPORT_ARTEFACTS: Mapping[CalculationReportDocumentFormat, ModeloExportArtefact] = MappingProxyType(
    {document_format: artefact for artefact, document_format in _REPORT_DOCUMENT_FORMATS.items()},
)


def _require_export_terminal_receipt(
    receipt: ModeloExportResult | ModeloCalculationReportResult | None, terminal_receipt: OperationTerminalReceipt
) -> None:
    message = "export result contradicts its terminal receipt"
    if receipt is None:
        raise ValueError(message)
    require_succeeded_terminal_receipt(
        terminal_receipt,
        definition_id=MODELO_EXPORT_OPERATION_DEFINITION_ID,
        subject_ref=receipt.work_unit_id,
        effect=OperationEffect.UPDATED,
        message=message,
    )


def _project_modelo_export_result(result: BaseModel, terminal_receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Project the service's settled receipt into the public export result.

    Every fact is read from the receipt the export service returned; the only
    translation is from its field spelling into the closed public vocabulary.
    """
    settled = ModeloExportSettledResult.model_validate(result, strict=True)
    receipt = settled.fichero_boe if settled.fichero_boe is not None else settled.calculation_report
    _require_export_terminal_receipt(receipt, terminal_receipt)
    if settled.fichero_boe is not None:
        filing = settled.fichero_boe
        return ModeloExportPublicResultV3(
            calculation_revision_id=filing.calculation_revision_id,
            artefact=ModeloExportArtefact.FICHERO_BOE,
            export_format=filing.format,
            output_path=str(filing.output_path),
            byte_size=filing.byte_size,
            file_sha256=filing.file_sha256,
            software_identity_grade=filing.software_identity_grade,
            evidence_status=ModeloExportEvidenceStatus(filing.local_evidence_status),
            completeness=(
                ModeloExportCompleteness.UNVERIFIED
                if filing.completeness_unverified
                else ModeloExportCompleteness.NOT_FLAGGED
            ),
            fichero_boe=ModeloFicheroBoePublicReceipt.from_result(filing),
        )
    report = settled.calculation_report
    if report is None:
        raise ValueError("a settled export carries exactly one receipt")
    return ModeloExportPublicResultV3(
        calculation_revision_id=report.calculation_revision_id,
        artefact=_REPORT_ARTEFACTS[report.document_format],
        export_format=report.document_format.value,
        output_path=str(report.output_path),
        byte_size=report.byte_size,
        file_sha256=report.file_sha256,
        software_identity_grade=report.software_identity_grade,
        evidence_status=ModeloExportEvidenceStatus.LOCAL_CALCULATION_REPORT_NOT_OFFICIAL_AEAT_FILING_EVIDENCE,
        completeness=ModeloExportCompleteness.NOT_ASSESSED,
        calculation_report=ModeloCalculationReportPublicReceipt.from_result(report),
    )


class ModeloExportExecutor:
    """Export one revision through the existing authority, locally only.

    The authority is local by construction and never contacts AEAT; this
    enrolment adds no transport of its own, so an exported artefact reaches
    the tax authority only when a human carries it there.
    """

    def __init__(
        self,
        *,
        profile_resolver: ModeloWorkVerifyProfileResolver,
        export_ports_factory: ModeloExportPortsFactory,
        signing_keypair_capability_factory: ReviewPackageSigningKeypairCapabilityFactory,
        calculation_summary_pdf_writer: CalculationSummaryPdfWriter,
        execution_caller_reader: OperationExecutionCallerReader | None = None,
    ) -> None:
        """Bind the live profile the export gates are judged against, and the summary PDF writer.

        The writer is the outbound adapter the composition root supplies,
        because this layer cannot import it. It is handed to the report
        service on every report export and used only for the summary PDF.
        """
        self._profile_resolver = profile_resolver
        self._export_ports_factory = export_ports_factory
        self._signing_keypair_capability_factory = signing_keypair_capability_factory
        self._calculation_summary_pdf_writer = calculation_summary_pdf_writer
        self._execution_caller_reader = execution_caller_reader

    async def execute(
        self,
        request: OperationRequest[ModeloExportRequest],
        context: OperationExecutorContext,
    ) -> str | None:
        """Delegate to the export authority and keep its receipt as the settled result.

        The command is built from the journalled request, so the identity an
        artefact is stamped with is the one this invocation recorded rather
        than whatever a closure happened to hold when the definition was built.

        The service's receipt is stored behind the secure operand boundary and
        its reference settles the operation, so a surface reads the evidence
        status, completeness and identity grade the service stated rather than
        a digest it would have to explain on its own.

        Publishes its entry phase only -- see DELEGATED PHASE REPORTING above.
        """
        await context.events.phase("modelo.export.preconditions")
        payload = request.payload
        actor = execution_actor_label(self._execution_caller_reader, context, supplied=payload.actor)
        from ...core.bucket_pointer import require_active_bucket_id

        def export() -> ModeloExportSettledResult:
            with validating_governed_facts(context.authority_operation):
                workflow_profile = self._profile_resolver(context.authority_operation)
                active_bucket_id = require_active_bucket_id()
                export_ports = self._export_ports_factory(
                    bucket_id=active_bucket_id,
                    m303_rectificativa_taxpayer_tax_id=workflow_profile.tax_id,
                    operation=context.authority_operation,
                )
                if payload.artefact is ModeloExportArtefact.FICHERO_BOE:
                    return ModeloExportSettledResult(
                        fichero_boe=self._published_fichero_boe(
                            payload,
                            actor=actor,
                            workflow_profile=workflow_profile,
                            export_ports=export_ports,
                            operation=context.authority_operation,
                        )
                    )
                return ModeloExportSettledResult(
                    calculation_report=self._published_calculation_report(
                        payload,
                        active_bucket_id=active_bucket_id,
                        export_ports=export_ports,
                        operation=context.authority_operation,
                    )
                )

        async def publish() -> str:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                settled = await asyncio.to_thread(export)
                await context.events.effect(OperationEffect.UPDATED)
                return await context.operands.put(settled, written_at=_utc_now())

        return await await_cancellation_complete(publish(), task_name="modelo-export-publication")

    @staticmethod
    def _published_fichero_boe(
        payload: ModeloExportRequest,
        *,
        actor: str,
        workflow_profile: TaxpayerProfile,
        export_ports: ModeloExportPorts,
        operation: PinnedAuthorityOperation,
    ) -> ModeloExportResult:
        """Publish the AEAT-compatible filing file and return the service's receipt."""
        return export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=payload.calculation_revision_id,
                output_path=Path(payload.output_path),
                actor=actor,
                refund_election=payload.refund_election,
                payment_election=payload.payment_election,
                prior_domiciliation_election=payload.prior_domiciliation_election,
                charge_account_id=payload.charge_account_id,
                refund_account_id=payload.refund_account_id,
                replace_existing=payload.replace_existing,
            ),
            workflow_profile=workflow_profile,
            operation=operation,
            export_ports=export_ports,
        )

    def _published_calculation_report(
        self,
        payload: ModeloExportRequest,
        *,
        active_bucket_id: str,
        export_ports: ModeloExportPorts,
        operation: PinnedAuthorityOperation,
    ) -> ModeloCalculationReportResult:
        """Publish the calculation report and return the service's receipt.

        The declaration-shaping elections are not threaded here and their absence
        is not an omission: they decide the fichero's "Tipo de declaracion", and a
        calculation report declares nothing. The service the command line reaches
        is the one reached here, so the two surfaces cannot produce different
        reports for one revision.

        The report language is this invocation's own render language, so a
        full-screen session set to Catalan produces a Catalan report exactly as
        the command line does under ``--output-language ca``.

        The summary PDF is drawn by the writer this enrolment was composed with,
        the one the command line hands the same service. Where the optional
        ``pdf`` extra is absent the service refuses the PDF with its own typed
        error; nothing here substitutes another artefact.
        """
        return export_modelo_calculation_report(
            ModeloCalculationReportCommand(
                calculation_revision_id=payload.calculation_revision_id,
                document_format=_REPORT_DOCUMENT_FORMATS[payload.artefact],
                report_language=payload.report_language,
                output_path=Path(payload.output_path),
                replace_existing=payload.replace_existing,
            ),
            export_ports=export_ports,
            signing_keypair=self._signing_keypair_capability_factory(bucket_id=active_bucket_id),
            operation=operation,
            pdf_writer=self._calculation_summary_pdf_writer,
        )


def build_modelo_export_definition(
    *,
    profile_resolver: ModeloWorkVerifyProfileResolver = resolve_active_workflow_profile,
    export_ports_factory: ModeloExportPortsFactory,
    signing_keypair_capability_factory: ReviewPackageSigningKeypairCapabilityFactory,
    calculation_summary_pdf_writer: CalculationSummaryPdfWriter,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    """Bind the export authority to its registered operation contract."""

    def build() -> ModeloExportExecutor:
        return ModeloExportExecutor(
            profile_resolver=profile_resolver,
            export_ports_factory=export_ports_factory,
            signing_keypair_capability_factory=signing_keypair_capability_factory,
            calculation_summary_pdf_writer=calculation_summary_pdf_writer,
            execution_caller_reader=execution_caller_reader,
        )

    return OperationDefinition(
        definition_id=MODELO_EXPORT_OPERATION_DEFINITION_ID,
        request_type=ModeloExportRequest,
        subject_reference=OperationSubjectReferenceV1.stored_work_unit("calculation_revision_id"),
        result_type=ModeloExportSettledResult,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloExportRequest,
            executor_type=ModeloExportExecutor,
            build=build,
        ),
        phase_codes=("modelo.export.preconditions", "modelo.export.render"),
        interaction_kinds=frozenset[OperationInteractionKind](),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.REQUEST_BOUND,
            request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
            sensitive_input=OperationSensitiveInputPolicy.NONE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=EFFECTS_WITHOUT_PARTIAL_COMMIT,
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        public_error_detail=True,
    )


def build_modelo_export_registration(
    definition: OperationDefinition,
    *,
    access_resolver: OperationAccessResolver | None = None,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the export definition to its stable public schemas."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.export.request",
            schema_version=3,
            model_type=definition.request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id="modelo.export.result",
            schema_version=3,
            model_type=ModeloExportPublicResultV3,
        ),
        workspace_refresh_target_schema=modelo_workspace_refresh_target_binding(definition.definition_id),
        workspace_refresh_adapter=resolve_modelo_work_unit_refresh_target,
        access_resolver=access_resolver,
        result_projector=_project_modelo_export_result,
    )
