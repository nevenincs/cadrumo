"""Profile-bound invoice withholding capture and aggregate execution."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from uuid import UUID

from pydantic import ValidationError

from ...core.bucket_pointer import require_active_bucket_id
from ...core.hashing import canonical_json_bytes
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ..aggregation.invoice_retencion import (
    InvoiceRetencionProjectionDefect,
    InvoiceWithholdingCapture,
    InvoiceWithholdingDefectsError,
    InvoiceWithholdingEvidenceError,
    build_invoice_withholding_capture,
)
from ..aggregation.service import (
    PerModeloAggregationCommand,
    PerModeloAggregationContributor,
    PerModeloAggregationResult,
    aggregate_per_modelo,
)
from ..aggregation.withholding_filing_cadence import (
    WithholdingFilerCadence,
    WithholdingFilingCadenceError,
    load_bucket_withholding_filer_cadence,
)
from ..aggregation.withholding_observation_service import (
    WithholdingGenerationAudit,
    WithholdingObservationMutationError,
    WithholdingWindowBaseline,
)
from ..aggregation.withholding_producer import (
    WithholdingEvidenceCaptureResult,
    WithholdingProducer,
    WithholdingProducerError,
)
from ..aggregation.withholding_recognition import WithholdingRecognitionError
from ..invoices.catalogue_lifecycle import resolve_catalogue_invoice
from ..invoices.catalogue_selection import InvoiceLookupRefusedError
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .invoice_withholding_capture_contracts import (
    MODELO_INVOICE_WITHHOLDING_CAPTURE_MAX_RESULT_BYTES,
    MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
    MODELO_INVOICE_WITHHOLDING_COMMIT_PHASE,
    MODELO_INVOICE_WITHHOLDING_PREPARE_PHASE,
    MODELO_INVOICE_WITHHOLDING_RESULT_PHASE,
    ModeloInvoiceWithholdingCapturePorts,
    ModeloInvoiceWithholdingCapturePortsFactory,
    ModeloInvoiceWithholdingCaptureProjection,
    ModeloInvoiceWithholdingCaptureReport,
    ModeloInvoiceWithholdingCaptureRequest,
    ModeloInvoiceWithholdingGenerationAudit,
    ModeloInvoiceWithholdingWindow,
    ModeloInvoiceWithholdingWindowBaseline,
)
from .invoice_withholding_capture_public import PublicInvoiceWithholdingCommand


def _profile_ports(
    factory: ModeloInvoiceWithholdingCapturePortsFactory,
    *,
    profile_id: str,
) -> ModeloInvoiceWithholdingCapturePorts:
    ports = factory(profile_id=profile_id)
    if ports.profile_id != profile_id or ports.invoice_catalogue_repository.bucket_id != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ports


def _project_window(
    *,
    baseline: WithholdingWindowBaseline,
    generation: int,
    audit: WithholdingGenerationAudit | None,
) -> ModeloInvoiceWithholdingWindow:
    return ModeloInvoiceWithholdingWindow(
        baseline=ModeloInvoiceWithholdingWindowBaseline(
            scope_token=baseline.scope_token,
            generation_id=baseline.generation_id,
        ),
        generation=generation,
        generation_audit=(
            None
            if audit is None
            else ModeloInvoiceWithholdingGenerationAudit(
                parent_generation_id=audit.parent_generation_id,
                mode=audit.mode,
                supersedes_generation_id=audit.supersedes_generation_id,
            )
        ),
    )


def _bounded_reason(error: Exception) -> str:
    """Select a stable refusal token without copying exception prose or facts."""
    if isinstance(error, InvoiceLookupRefusedError):
        candidate = error.reason.value
    else:
        candidate = getattr(error, "refusal_code", "invalid_evidence")
    if not isinstance(candidate, str) or re.fullmatch(r"[a-z][a-z0-9_]{0,95}", candidate) is None:
        return "invalid_evidence"
    return candidate


_DEFECTS_REFUSAL_REASON = "invoice_withholding_defects"


def _capture_refusal(
    *,
    profile_id: UUID,
    command: PublicInvoiceWithholdingCommand,
    reason: str,
    defects: tuple[InvoiceRetencionProjectionDefect, ...] | None = None,
) -> ModeloInvoiceWithholdingCaptureProjection:
    return ModeloInvoiceWithholdingCaptureProjection(
        outcome="refused",
        profile_id=profile_id,
        modelo=command.modelo,
        period=command.period,
        refusal_reason=reason,
        refusal_defects=defects,
    )


class ModeloInvoiceWithholdingCaptureExecutor:
    """Capture through the canonical producer, then aggregate in profile custody."""

    def __init__(self, factory: ModeloInvoiceWithholdingCapturePortsFactory) -> None:
        """Retain the composition-supplied exact-profile port factory."""
        self._factory = factory

    async def execute(
        self,
        request: OperationRequest[ModeloInvoiceWithholdingCaptureRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Capture one allocation and publish only its bounded aggregate summary."""
        payload = request.payload
        profile_id = str(payload.profile_id)
        if request.definition_id != MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)

        await context.events.phase(MODELO_INVOICE_WITHHOLDING_PREPARE_PHASE)
        operation = context.authority_operation
        try:
            prepared = await asyncio.to_thread(self._prepare, payload, profile_id, operation)
        except InvoiceWithholdingDefectsError as error:
            return await self._refuse(payload, context, _DEFECTS_REFUSAL_REASON, defects=error.defects)
        except (
            InvoiceLookupRefusedError,
            InvoiceWithholdingEvidenceError,
            WithholdingFilingCadenceError,
        ) as error:
            return await self._refuse(payload, context, _bounded_reason(error))

        return await self._commit_and_aggregate(payload, context, prepared, operation)

    async def _commit_and_aggregate(
        self,
        payload: ModeloInvoiceWithholdingCaptureRequest,
        context: OperationExecutorContext,
        prepared: _PreparedCapture,
        operation: PinnedAuthorityOperation,
    ) -> str | OperationRefusalEvidence:
        async with context.cancellation.irreversible_section():
            if require_active_bucket_id() != str(payload.profile_id):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            await context.events.phase(MODELO_INVOICE_WITHHOLDING_COMMIT_PHASE)
            await context.events.effect(OperationEffect.UNKNOWN)
            captured = await self._capture_or_refuse(payload, context, prepared)
            if isinstance(captured, OperationRefusalEvidence):
                return captured
            if captured is None or captured.scope != prepared.capture.scope:
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

            local_write_performed = not captured.mutation.replayed
            await context.events.effect(OperationEffect.UPDATED if local_write_performed else OperationEffect.NONE)
            if require_active_bucket_id() != str(payload.profile_id):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            return await self._aggregate_after_capture(
                payload,
                context,
                prepared,
                operation,
                local_write_performed=local_write_performed,
            )

    async def _capture_or_refuse(
        self,
        payload: ModeloInvoiceWithholdingCaptureRequest,
        context: OperationExecutorContext,
        prepared: _PreparedCapture,
    ) -> WithholdingEvidenceCaptureResult | OperationRefusalEvidence | None:
        try:
            return await asyncio.to_thread(
                WithholdingProducer(service=prepared.ports.withholding_observation_service).capture,
                prepared.capture.command,
                cadence=prepared.cadence,
                source_catalogue_revision_id=prepared.capture.catalogue_read_revision_id,
            )
        except (WithholdingProducerError, WithholdingRecognitionError) as error:
            # These validation boundaries run before producer service.apply.
            # Storage failures stay UNKNOWN because delivery is not inferred.
            await context.events.effect(OperationEffect.NONE)
            return await self._record_refusal(payload, context, _bounded_reason(error))
        except WithholdingObservationMutationError as error:
            if error.refusal_code != "source_revision_changed":
                raise
            await context.events.effect(OperationEffect.NONE)
            return await self._record_refusal(payload, context, _bounded_reason(error))

    async def _aggregate_after_capture(
        self,
        payload: ModeloInvoiceWithholdingCaptureRequest,
        context: OperationExecutorContext,
        prepared: _PreparedCapture,
        operation: PinnedAuthorityOperation,
        *,
        local_write_performed: bool,
    ) -> str:
        window_state = await asyncio.to_thread(
            prepared.ports.withholding_observation_service.read_window,
            prepared.capture.scope,
        )
        if window_state.scope != prepared.capture.scope:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        observations = tuple(entry.retencion for entry in window_state.entries if entry.retencion is not None)
        aggregate_command = prepared.aggregate_command.model_copy(update={"retencion_observations": observations})
        aggregate_result = await asyncio.to_thread(self._aggregate, aggregate_command, operation)
        audit = (
            None
            if window_state.generation == 0
            else await asyncio.to_thread(
                prepared.ports.withholding_observation_service.read_generation,
                prepared.capture.scope,
                window_state.baseline.generation_id,
            )
        )
        if (
            str(aggregate_result.modelo) != prepared.aggregate_command.modelo
            or aggregate_result.period != prepared.aggregate_command.period
            or aggregate_result.provider is not PerModeloAggregationContributor.RETENCIONES
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        projection = ModeloInvoiceWithholdingCaptureProjection(
            outcome="captured",
            profile_id=payload.profile_id,
            modelo=payload.command.modelo,
            period=payload.command.period,
            provider=PerModeloAggregationContributor.RETENCIONES,
            observation_count=aggregate_result.log_fields.observation_count,
            source_kinds=aggregate_result.source_kinds,
            result_row_count=aggregate_result.log_fields.result_row_count,
            withholding_window=_project_window(
                baseline=window_state.baseline,
                generation=window_state.generation,
                audit=audit,
            ),
        )
        await context.events.phase(MODELO_INVOICE_WITHHOLDING_RESULT_PHASE)
        report = ModeloInvoiceWithholdingCaptureReport(
            projection=projection,
            local_write_performed=local_write_performed,
        )
        if (
            len(canonical_json_bytes(report.model_dump(mode="json")))
            > MODELO_INVOICE_WITHHOLDING_CAPTURE_MAX_RESULT_BYTES
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        return await context.operands.put(report, written_at=now())

    def _prepare(
        self,
        payload: ModeloInvoiceWithholdingCaptureRequest,
        profile_id: str,
        operation: PinnedAuthorityOperation,
    ) -> _PreparedCapture:
        if require_active_bucket_id() != profile_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        command = payload.command.to_domain()
        try:
            with validating_governed_facts(operation):
                evidence = payload.evidence.to_domain()
        except (ValueError, ValidationError) as error:
            raise InvoiceWithholdingEvidenceError("invalid_evidence") from error
        ports = _profile_ports(self._factory, profile_id=profile_id)
        cadence = load_bucket_withholding_filer_cadence(
            bucket_id=profile_id,
            filing_year=command.period.filing_year,
            operation=operation,
        )
        catalogue, revision_id = ports.invoice_catalogue_repository.load_revisioned()
        try:
            invoice = resolve_catalogue_invoice(catalogue, str(evidence.invoice_id))
        except InvoiceLookupRefusedError:
            raise
        try:
            with validating_governed_facts(operation):
                capture = build_invoice_withholding_capture(
                    invoice,
                    catalogue_revision_id=revision_id,
                    request=evidence,
                    applicable_year=command.period.filing_year,
                    cadence=cadence,
                )
        except InvoiceWithholdingEvidenceError:
            raise
        except ValueError as exc:
            raise InvoiceWithholdingEvidenceError("invalid_evidence") from exc
        if capture.scope.modelo != command.modelo or capture.scope.period != command.period:
            raise InvoiceWithholdingEvidenceError("invoice_withholding_period_mismatch")
        return _PreparedCapture(ports=ports, cadence=cadence, capture=capture, aggregate_command=command)

    @staticmethod
    def _aggregate(
        command: PerModeloAggregationCommand,
        operation: PinnedAuthorityOperation,
    ) -> PerModeloAggregationResult:
        with validating_governed_facts(operation):
            return aggregate_per_modelo(command, operation=operation)

    async def _refuse(
        self,
        payload: ModeloInvoiceWithholdingCaptureRequest,
        context: OperationExecutorContext,
        reason: str,
        *,
        defects: tuple[InvoiceRetencionProjectionDefect, ...] | None = None,
    ) -> OperationRefusalEvidence:
        async with context.cancellation.irreversible_section():
            if require_active_bucket_id() != str(payload.profile_id):
                raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
            await context.events.effect(OperationEffect.NONE)
            return await self._record_refusal(payload, context, reason, defects=defects)

    async def _record_refusal(
        self,
        payload: ModeloInvoiceWithholdingCaptureRequest,
        context: OperationExecutorContext,
        reason: str,
        *,
        defects: tuple[InvoiceRetencionProjectionDefect, ...] | None = None,
    ) -> OperationRefusalEvidence:
        projection = _capture_refusal(
            profile_id=payload.profile_id,
            command=payload.command,
            reason=reason,
            defects=defects,
        )
        detail = ModeloInvoiceWithholdingCaptureReport(projection=projection, local_write_performed=False)
        detail_ref = await context.operands.put(detail, written_at=now())
        refusal_code = projection.refusal_code
        if refusal_code is None:
            raise AssertionError("a refused projection always settles under a registered refusal code")
        return OperationRefusalEvidence(refusal_code=refusal_code, detail_ref=detail_ref)


@dataclass(frozen=True, slots=True)
class _PreparedCapture:
    ports: ModeloInvoiceWithholdingCapturePorts
    cadence: WithholdingFilerCadence
    capture: InvoiceWithholdingCapture
    aggregate_command: PerModeloAggregationCommand


__all__ = ["ModeloInvoiceWithholdingCaptureExecutor"]
