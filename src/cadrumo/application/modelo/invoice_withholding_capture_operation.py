"""Registered exact-profile operation for received-invoice withholding capture."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Annotated, Literal, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, ValidationError, model_validator

from ...core.aggregation import BindingSourceKind
from ...core.bucket_pointer import require_active_bucket_id
from ...core.hashing import canonical_json_bytes
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_CONFIG, STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.invoices.models import InvoiceCatalogue
from ..aggregation.invoice_retencion import (
    InvoiceRetencionProjectionDefect,
    InvoiceWithholdingCapture,
    InvoiceWithholdingDefectsError,
    InvoiceWithholdingEvidenceError,
    InvoiceWithholdingEvidenceRequest,
    build_invoice_withholding_capture,
)
from ..aggregation.retencion_observations_repository import RetencionObservationRepository
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
    WithholdingMutationMode,
    WithholdingObservationMutationError,
    WithholdingObservationService,
    WithholdingWindowBaseline,
)
from ..aggregation.withholding_producer import WithholdingProducer, WithholdingProducerError
from ..aggregation.withholding_recognition import WithholdingRecognitionError
from ..invoices.catalogue_lifecycle import resolve_catalogue_invoice
from ..invoices.catalogue_selection import InvoiceLookupRefusedError
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.public_period import PublicPeriod
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import (
    ALL_OPERATION_FRONTENDS,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .invoice_withholding_capture_public import PublicInvoiceWithholdingCommand, PublicInvoiceWithholdingEvidence

MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID = "modelo.aggregate.capture_received_invoice_retencion"
MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODE = "REFUSED_INVOICE_WITHHOLDING_EVIDENCE"
MODELO_INVOICE_WITHHOLDING_DEFECTS_REFUSAL_CODE = "REFUSED_INVOICE_WITHHOLDING_DEFECTS"
MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODES = frozenset(
    {MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODE, MODELO_INVOICE_WITHHOLDING_DEFECTS_REFUSAL_CODE}
)

_PREPARE_PHASE = "modelo-invoice-withholding-capture.prepare"
_COMMIT_PHASE = "modelo-invoice-withholding-capture.commit"
_RESULT_PHASE = "modelo-invoice-withholding-capture.result"
_PHASES = (_PREPARE_PHASE, _COMMIT_PHASE, _RESULT_PHASE)
_MAX_RESULT_BYTES = 16 * 1024
_SAFE_REFUSAL_REASON = Annotated[
    str,
    Field(min_length=1, max_length=96, pattern=r"^[a-z][a-z0-9_]*$"),
]


class InvoiceCatalogueRevisionReadPort(Protocol):
    """Minimal application-owned view of one profile's revisioned invoice catalogue."""

    @property
    def bucket_id(self) -> str | None:
        """Return the immutable profile binding of this reader."""
        ...

    def load_revisioned(self) -> tuple[InvoiceCatalogue, str]:
        """Return the decrypted catalogue and its opaque read revision."""
        ...


@dataclass(frozen=True, slots=True)
class ModeloInvoiceWithholdingCapturePorts:
    """Canonical application services and repositories for one exact profile."""

    profile_id: str
    invoice_catalogue_repository: InvoiceCatalogueRevisionReadPort
    retencion_observation_repository: RetencionObservationRepository
    withholding_observation_service: WithholdingObservationService


class ModeloInvoiceWithholdingCapturePortsFactory(Protocol):
    """Build capture capabilities already bound to the requested profile."""

    def __call__(self, *, profile_id: str) -> ModeloInvoiceWithholdingCapturePorts:
        """Return the exact profile's invoice, retención and window capabilities."""
        ...


class ModeloInvoiceWithholdingCaptureRequest(BaseModel):
    """Confidential typed operands with canonical service conversion."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    command: PublicInvoiceWithholdingCommand = Field(repr=False)
    evidence: PublicInvoiceWithholdingEvidence = Field(repr=False)

    @model_validator(mode="after")
    def _closed_capture_scope(self) -> Self:
        self.command.to_domain()
        return self

    @classmethod
    def from_inputs(
        cls,
        *,
        profile_id: UUID,
        command: PerModeloAggregationCommand,
        evidence: InvoiceWithholdingEvidenceRequest,
    ) -> Self:
        """Store the exact typed CLI inputs in the encrypted operation operand."""
        return cls(
            profile_id=profile_id,
            command=PublicInvoiceWithholdingCommand.from_domain(command),
            evidence=PublicInvoiceWithholdingEvidence.from_domain(evidence),
        )


class ModeloInvoiceWithholdingWindowBaseline(BaseModel):
    """Safe generation coordinates for one active withholding window."""

    model_config = STRICT_FROZEN_CONFIG

    scope_token: str = Field(min_length=1, max_length=256)
    generation_id: Hex64Str


class ModeloInvoiceWithholdingGenerationAudit(BaseModel):
    """Bounded lineage metadata that carries no source evidence."""

    model_config = STRICT_FROZEN_CONFIG

    parent_generation_id: Hex64Str
    mode: WithholdingMutationMode
    supersedes_generation_id: str | None = Field(default=None, min_length=64, max_length=64)


class ModeloInvoiceWithholdingWindow(BaseModel):
    """CLI-compatible metadata-only readback of the active withholding window."""

    model_config = STRICT_FROZEN_CONFIG

    baseline: ModeloInvoiceWithholdingWindowBaseline
    generation: NonNegativeInt
    generation_audit: ModeloInvoiceWithholdingGenerationAudit | None = None


class ModeloInvoiceWithholdingCaptureProjection(BaseModel):
    """Closed CLI-safe aggregate summary or bounded refusal outcome.

    ``refusal_defects`` names every defect that keeps the invoice's retención
    out of capture, as stable untranslated tokens in the projection's sweep
    order; a frontend renders their explanations in the operator's language.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    outcome: Literal["captured", "refused"]
    profile_id: UUID
    modelo: Literal["111", "115"]
    period: PublicPeriod
    provider: Literal[PerModeloAggregationContributor.RETENCIONES] | None = None
    observation_count: NonNegativeInt | None = None
    source_kinds: tuple[BindingSourceKind, ...] | None = None
    result_row_count: NonNegativeInt | None = None
    withholding_window: ModeloInvoiceWithholdingWindow | None = None
    refusal_reason: _SAFE_REFUSAL_REASON | None = None
    refusal_defects: tuple[InvoiceRetencionProjectionDefect, ...] | None = Field(
        default=None,
        min_length=1,
        max_length=len(InvoiceRetencionProjectionDefect),
    )

    @model_validator(mode="after")
    def _outcome_shape(self) -> Self:
        captured_fields = (
            self.provider,
            self.observation_count,
            self.source_kinds,
            self.result_row_count,
            self.withholding_window,
        )
        if self.outcome == "captured":
            if (
                self.refusal_reason is not None
                or self.refusal_defects is not None
                or any(value is None for value in captured_fields)
            ):
                raise ValueError("captured result requires aggregate and withholding-window summary fields")
        elif self.refusal_reason is None or any(value is not None for value in captured_fields):
            raise ValueError("refused result requires only a bounded refusal reason")
        elif self.refusal_defects is not None and len(set(self.refusal_defects)) != len(self.refusal_defects):
            raise ValueError("refused result repeats an invoice withholding defect")
        return self

    @property
    def refusal_code(self) -> str | None:
        """Return the registered refusal code this refused outcome settles under."""
        if self.outcome != "refused":
            return None
        if self.refusal_defects is not None:
            return MODELO_INVOICE_WITHHOLDING_DEFECTS_REFUSAL_CODE
        return MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODE


class ModeloInvoiceWithholdingCaptureReport(BaseModel):
    """Private executor operand correlated with the settled effect and receipt."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    projection: ModeloInvoiceWithholdingCaptureProjection
    local_write_performed: bool


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


def project_modelo_invoice_withholding_capture_result(
    result: BaseModel,
    receipt: OperationTerminalReceipt,
    /,
) -> BaseModel:
    """Release only the allowlisted summary whose terminal receipt agrees."""
    if type(result) is not ModeloInvoiceWithholdingCaptureReport:
        raise ValueError("invalid invoice-withholding operation result")
    report = ModeloInvoiceWithholdingCaptureReport.model_validate(result.model_dump(mode="python"), strict=True)
    projection = report.projection
    if (
        receipt.identity.definition_id != MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("invoice-withholding result differs from its terminal receipt")
    if projection.outcome == "refused":
        if (
            report.local_write_performed
            or receipt.condition is not OperationTerminalCondition.REFUSED
            or receipt.effect is not OperationEffect.NONE
            or receipt.refusal_ref != projection.refusal_code
            or receipt.refusal_detail_ref is None
        ):
            raise ValueError("invoice-withholding refusal contradicts its terminal receipt")
    elif receipt.condition is not OperationTerminalCondition.SUCCEEDED or receipt.effect is not (
        OperationEffect.UPDATED if report.local_write_performed else OperationEffect.NONE
    ):
        raise ValueError("invoice-withholding capture contradicts its terminal receipt")
    if len(canonical_json_bytes(projection.model_dump(mode="json"))) > _MAX_RESULT_BYTES:
        raise ValueError("invoice-withholding projection exceeds its public result limit")
    return projection


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

        await context.events.phase(_PREPARE_PHASE)
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

        async def commit_and_aggregate() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                if require_active_bucket_id() != profile_id:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                await context.events.phase(_COMMIT_PHASE)
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    captured = await asyncio.to_thread(
                        WithholdingProducer(service=prepared.ports.withholding_observation_service).capture,
                        prepared.capture.command,
                        cadence=prepared.cadence,
                        source_catalogue_revision_id=prepared.capture.catalogue_read_revision_id,
                    )
                except (WithholdingProducerError, WithholdingRecognitionError) as error:
                    # These two canonical validation boundaries run before the
                    # producer calls service.apply. Storage failures stay
                    # UNKNOWN because their delivery outcome is not inferred.
                    await context.events.effect(OperationEffect.NONE)
                    return await self._record_refusal(payload, context, _bounded_reason(error))
                except WithholdingObservationMutationError as error:
                    if error.refusal_code != "source_revision_changed":
                        raise
                    await context.events.effect(OperationEffect.NONE)
                    return await self._record_refusal(payload, context, _bounded_reason(error))
                if captured is None or captured.scope != prepared.capture.scope:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

                local_write_performed = not captured.mutation.replayed
                await context.events.effect(OperationEffect.UPDATED if local_write_performed else OperationEffect.NONE)
                if require_active_bucket_id() != profile_id:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                window_state = await asyncio.to_thread(
                    prepared.ports.withholding_observation_service.read_window,
                    prepared.capture.scope,
                )
                if window_state.scope != prepared.capture.scope:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
                observations = tuple(entry.retencion for entry in window_state.entries if entry.retencion is not None)
                aggregate_command = prepared.aggregate_command.model_copy(
                    update={"retencion_observations": observations}
                )
                aggregate_result = await asyncio.to_thread(
                    self._aggregate,
                    aggregate_command,
                    operation,
                )
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
                await context.events.phase(_RESULT_PHASE)
                report = ModeloInvoiceWithholdingCaptureReport(
                    projection=projection,
                    local_write_performed=local_write_performed,
                )
                if len(canonical_json_bytes(report.model_dump(mode="json"))) > _MAX_RESULT_BYTES:
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
                return await context.operands.put(report, written_at=now())

        return await commit_and_aggregate()

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


def build_modelo_invoice_withholding_capture_definition(
    factory: ModeloInvoiceWithholdingCapturePortsFactory,
) -> OperationDefinition:
    """Declare secure storage, honest effects, and exact-profile mutation custody."""
    return OperationDefinition(
        definition_id=MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID,
        request_type=ModeloInvoiceWithholdingCaptureRequest,
        result_type=ModeloInvoiceWithholdingCaptureReport,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloInvoiceWithholdingCaptureRequest,
            executor_type=ModeloInvoiceWithholdingCaptureExecutor,
            build=lambda: ModeloInvoiceWithholdingCaptureExecutor(factory),
        ),
        phase_codes=_PHASES,
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
        refusal_detail_codes=MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODES,
    )


def resolve_modelo_invoice_withholding_capture_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Bind exact profile and all-period invoice-catalogue rights, including fresh COMMIT."""
    if request.definition_id != MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, ModeloInvoiceWithholdingCaptureRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    payload = request.payload
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    resolved = resolve_ledger_read_access(
        request,
        context,
        profile_id=payload.profile_id,
        periods=frozenset(),
    )
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


def build_modelo_invoice_withholding_capture_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the hidden financial request to its closed safe summary projection."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=ModeloInvoiceWithholdingCaptureRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=2,
            model_type=ModeloInvoiceWithholdingCaptureProjection,
        ),
        result_projector=project_modelo_invoice_withholding_capture_result,
        access_resolver=resolve_modelo_invoice_withholding_capture_access,
    )


__all__ = [
    "MODELO_INVOICE_WITHHOLDING_CAPTURE_OPERATION_DEFINITION_ID",
    "MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODE",
    "MODELO_INVOICE_WITHHOLDING_CAPTURE_REFUSAL_CODES",
    "MODELO_INVOICE_WITHHOLDING_DEFECTS_REFUSAL_CODE",
    "ModeloInvoiceWithholdingCaptureExecutor",
    "ModeloInvoiceWithholdingCapturePorts",
    "ModeloInvoiceWithholdingCapturePortsFactory",
    "ModeloInvoiceWithholdingCaptureProjection",
    "ModeloInvoiceWithholdingCaptureReport",
    "ModeloInvoiceWithholdingCaptureRequest",
    "ModeloInvoiceWithholdingGenerationAudit",
    "ModeloInvoiceWithholdingWindow",
    "ModeloInvoiceWithholdingWindowBaseline",
    "build_modelo_invoice_withholding_capture_definition",
    "build_modelo_invoice_withholding_capture_registration",
    "project_modelo_invoice_withholding_capture_result",
    "resolve_modelo_invoice_withholding_capture_access",
]
