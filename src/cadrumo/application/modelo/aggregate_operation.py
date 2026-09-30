"""Registered exact-profile operation for non-invoice modelo aggregation."""

from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Annotated, Literal, Protocol, Self
from uuid import UUID

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from ...core.aggregation import BindingSourceKind
from ...core.bucket_pointer import require_active_bucket_id
from ...core.hashing import canonical_json_bytes
from ...core.models import STRICT_FROZEN_CONFIG, STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.transactions.models import TransactionCatalogue
from ..aggregation.errors import AggregationConfigError, AggregationUnsupportedModeloError
from ..aggregation.ledger_payment_withholding import (
    LedgerPaymentWithholdingCapture,
    LedgerPaymentWithholdingEvidenceError,
    LedgerPaymentWithholdingEvidenceRequest,
    build_ledger_payment_withholding_capture,
    resolve_ledger_payment_transaction,
)
from ..aggregation.retencion_observations_repository import RetencionObservationRepository
from ..aggregation.service import (
    PerModeloAggregationCommand,
    PerModeloAggregationContributor,
    PerModeloAggregationResult,
    aggregate_per_modelo,
    provider_for_modelo,
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
    WithholdingWindowScope,
    WithholdingWindowState,
)
from ..aggregation.withholding_producer import WithholdingProducer, WithholdingProducerError
from ..aggregation.withholding_recognition import WithholdingRecognitionError
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.owner import OperationExecutorContext
from ..operations.public_period import PublicPeriod
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessAction, AccessDenialCode, OperationAccessPolicy
from ..user_profile.access_errors import ProfileAccessRefusedError
from .aggregate_public import PublicLedgerPaymentEvidenceRequest, PublicModeloAggregateCommand

MODELO_AGGREGATE_OPERATION_DEFINITION_ID = "modelo.aggregate"
MODELO_AGGREGATE_UNSUPPORTED_MODELO_REFUSAL_CODE = "REFUSED_FINANCIAL_AGGREGATION_UNSUPPORTED_MODELO"
MODELO_AGGREGATE_LEDGER_PAYMENT_REFUSAL_CODE = "REFUSED_LEDGER_PAYMENT_WITHHOLDING_EVIDENCE"
MODELO_AGGREGATE_CADENCE_REFUSAL_CODE = "REFUSED_WITHHOLDING_FILING_CADENCE"
MODELO_AGGREGATE_PRODUCER_REFUSAL_CODE = "REFUSED_WITHHOLDING_PRODUCER"
MODELO_AGGREGATE_RECOGNITION_REFUSAL_CODE = "REFUSED_WITHHOLDING_RECOGNITION"
MODELO_AGGREGATE_REFUSAL_CODES = frozenset(
    {
        MODELO_AGGREGATE_UNSUPPORTED_MODELO_REFUSAL_CODE,
        MODELO_AGGREGATE_LEDGER_PAYMENT_REFUSAL_CODE,
        MODELO_AGGREGATE_CADENCE_REFUSAL_CODE,
        MODELO_AGGREGATE_PRODUCER_REFUSAL_CODE,
        MODELO_AGGREGATE_RECOGNITION_REFUSAL_CODE,
    }
)

_PREPARE_PHASE = "modelo-aggregate.prepare"
_COMMIT_PHASE = "modelo-aggregate.commit"
_RESULT_PHASE = "modelo-aggregate.result"
_PHASES = (_PREPARE_PHASE, _COMMIT_PHASE, _RESULT_PHASE)
_MAX_RESULT_BYTES = 16 * 1024
_WITHHOLDING_MODELOS = frozenset({"111", "115", "123"})
_LEDGER_PAYMENT_MODELOS = frozenset({"111", "123"})
_SAFE_REFUSAL_REASON = Annotated[
    str,
    Field(min_length=1, max_length=96, pattern=r"^[a-z][a-z0-9_]*$"),
]


class TransactionCatalogueReadPort(Protocol):
    """Profile-bound transaction catalogue view needed for payment capture."""

    @property
    def bucket_id(self) -> str:
        """Return the immutable profile binding of this reader."""
        ...

    def load_revision(self) -> str | None:
        """Return the exact revision of the full transaction catalogue."""
        ...

    def load_by_ids(self, transaction_ids: tuple[str, ...]) -> TransactionCatalogue:
        """Read the addressed transaction rows from this profile's catalogue."""
        ...


@dataclass(frozen=True, slots=True)
class ModeloAggregateOperationPorts:
    """Canonical profile-scoped readers and producer service for one request."""

    profile_id: str
    transaction_catalogue_repository: TransactionCatalogueReadPort
    retencion_observation_repository: RetencionObservationRepository
    withholding_observation_service: WithholdingObservationService


class ModeloAggregateOperationPortsFactory(Protocol):
    """Build every aggregate capability already bound to the requested profile."""

    def __call__(self, *, profile_id: str) -> ModeloAggregateOperationPorts:
        """Return the exact profile's aggregate read and capture capabilities."""
        ...


class ModeloAggregateOperationRequest(BaseModel):
    """Confidential typed aggregation operands and optional ledger payment evidence."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    command: PublicModeloAggregateCommand = Field(repr=False)
    ledger_payment: PublicLedgerPaymentEvidenceRequest | None = Field(default=None, repr=False)

    @model_validator(mode="after")
    def _closed_aggregate_scope(self) -> Self:
        model = self.command.modelo
        if model in _WITHHOLDING_MODELOS and self.command.retencion_observations:
            raise ValueError("withholding-model aggregate reads stored retención observations")
        if self.ledger_payment is not None:
            if model not in _LEDGER_PAYMENT_MODELOS:
                raise ValueError("ledger-payment withholding capture is supported only for Modelos 111 and 123")
            if self.command.counterpart_observations or self.command.foreign_asset_observations:
                raise ValueError("ledger-payment capture cannot be mixed with another aggregation provider")
        return self

    @classmethod
    def from_inputs(
        cls,
        *,
        profile_id: UUID,
        command: PerModeloAggregationCommand,
        ledger_payment: LedgerPaymentWithholdingEvidenceRequest | None = None,
    ) -> Self:
        """Keep the exact typed CLI/TUI/MCP operands in the encrypted request store."""
        return cls(
            profile_id=profile_id,
            command=PublicModeloAggregateCommand.from_domain(command),
            ledger_payment=(
                None if ledger_payment is None else PublicLedgerPaymentEvidenceRequest.from_domain(ledger_payment)
            ),
        )


class ModeloAggregateWindowBaseline(BaseModel):
    """Metadata-only generation coordinates for one active withholding window."""

    model_config = STRICT_FROZEN_CONFIG

    scope_token: str = Field(min_length=1, max_length=256)
    generation_id: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")


class ModeloAggregateGenerationAudit(BaseModel):
    """Bounded lineage metadata without withholding evidence rows."""

    model_config = STRICT_FROZEN_CONFIG

    parent_generation_id: str = Field(min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    mode: WithholdingMutationMode
    supersedes_generation_id: str | None = Field(default=None, min_length=64, max_length=64)


class ModeloAggregateWindow(BaseModel):
    """CLI-compatible metadata-only readback of one withholding window."""

    model_config = STRICT_FROZEN_CONFIG

    baseline: ModeloAggregateWindowBaseline
    generation: NonNegativeInt
    generation_audit: ModeloAggregateGenerationAudit | None = None


class ModeloAggregateProjection(BaseModel):
    """Allowlisted aggregation summary; raw observation rows never leave custody."""

    model_config = STRICT_FROZEN_CONFIG

    outcome: Literal["aggregated", "refused"]
    profile_id: UUID
    modelo: str = Field(min_length=1, max_length=16)
    period: PublicPeriod
    provider: PerModeloAggregationContributor | None = None
    observation_count: NonNegativeInt | None = None
    source_kinds: tuple[BindingSourceKind, ...] | None = None
    result_row_count: NonNegativeInt | None = None
    clave_breakdown: tuple[Literal[""], ...] | None = Field(default=None, max_length=0)
    withholding_window: ModeloAggregateWindow | None = None
    refusal_reason: _SAFE_REFUSAL_REASON | None = None

    @model_validator(mode="after")
    def _outcome_shape(self) -> Self:
        aggregate_fields = (
            self.provider,
            self.observation_count,
            self.source_kinds,
            self.result_row_count,
            self.clave_breakdown,
        )
        if self.outcome == "aggregated":
            if self.refusal_reason is not None or any(value is None for value in aggregate_fields):
                raise ValueError("aggregated result requires the canonical summary fields")
            if self.modelo in _WITHHOLDING_MODELOS and self.withholding_window is None:
                raise ValueError("withholding aggregate requires its exact window readback")
        elif self.refusal_reason is None or any(value is not None for value in aggregate_fields):
            raise ValueError("refused result requires only a bounded refusal reason")
        elif self.withholding_window is not None:
            raise ValueError("refused result cannot carry a withholding window")
        return self


class ModeloAggregateReport(BaseModel):
    """Private result operand correlated with the settled operation receipt."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    projection: ModeloAggregateProjection
    local_write_performed: bool
    refusal_code: str | None = None


def _profile_ports(
    factory: ModeloAggregateOperationPortsFactory,
    *,
    profile_id: str,
) -> ModeloAggregateOperationPorts:
    ports = factory(profile_id=profile_id)
    if ports.profile_id != profile_id or ports.transaction_catalogue_repository.bucket_id != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ports


def _project_window(
    *,
    baseline: WithholdingWindowBaseline,
    generation: int,
    audit: WithholdingGenerationAudit | None,
) -> ModeloAggregateWindow:
    return ModeloAggregateWindow(
        baseline=ModeloAggregateWindowBaseline(
            scope_token=baseline.scope_token,
            generation_id=baseline.generation_id,
        ),
        generation=generation,
        generation_audit=(
            None
            if audit is None
            else ModeloAggregateGenerationAudit(
                parent_generation_id=audit.parent_generation_id,
                mode=audit.mode,
                supersedes_generation_id=audit.supersedes_generation_id,
            )
        ),
    )


def _bounded_reason(error: Exception) -> str:
    """Select a stable reason token without copying exception prose or private facts."""
    candidate: object = getattr(error, "refusal_code", None)
    if candidate is None:
        refusal = getattr(error, "refusal", None)
        candidate = getattr(refusal, "value", refusal)
    if not isinstance(candidate, str) or re.fullmatch(r"[a-z][a-z0-9_]{0,95}", candidate) is None:
        return "invalid_aggregate_input"
    return candidate


def _refused_projection(
    *,
    profile_id: UUID,
    command: PublicModeloAggregateCommand,
    reason: str,
) -> ModeloAggregateProjection:
    return ModeloAggregateProjection(
        outcome="refused",
        profile_id=profile_id,
        modelo=command.modelo,
        period=command.period,
        refusal_reason=reason,
    )


def project_modelo_aggregate_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release only the bounded summary whose identity and effect match its receipt."""
    if type(result) is not ModeloAggregateReport:
        raise ValueError("invalid modelo-aggregate operation result")
    report = ModeloAggregateReport.model_validate(result.model_dump(mode="python"), strict=True)
    projection = report.projection
    if (
        receipt.identity.definition_id != MODELO_AGGREGATE_OPERATION_DEFINITION_ID
        or receipt.identity.subject_ref != profile_operation_subject(str(projection.profile_id))
        or receipt.failure_error_code is not None
        or receipt.diagnostic_ref is not None
    ):
        raise ValueError("modelo-aggregate result differs from its terminal receipt")
    if projection.outcome == "refused":
        if (
            report.local_write_performed
            or receipt.condition is not OperationTerminalCondition.REFUSED
            or receipt.effect is not OperationEffect.NONE
            or report.refusal_code not in MODELO_AGGREGATE_REFUSAL_CODES
            or receipt.refusal_ref != report.refusal_code
            or receipt.refusal_detail_ref is None
            or receipt.result_ref is not None
        ):
            raise ValueError("modelo-aggregate refusal contradicts its terminal receipt")
    elif (
        receipt.condition is not OperationTerminalCondition.SUCCEEDED
        or receipt.result_ref is None
        or receipt.refusal_ref is not None
        or receipt.refusal_detail_ref is not None
        or report.refusal_code is not None
        or receipt.effect is not (OperationEffect.UPDATED if report.local_write_performed else OperationEffect.NONE)
    ):
        raise ValueError("modelo-aggregate result contradicts its terminal receipt")
    if len(canonical_json_bytes(projection.model_dump(mode="json"))) > _MAX_RESULT_BYTES:
        raise ValueError("modelo-aggregate projection exceeds its public result limit")
    return projection


class ModeloAggregateExecutor:
    """Aggregate through the shared application service inside profile custody."""

    def __init__(self, factory: ModeloAggregateOperationPortsFactory) -> None:
        """Retain the composition-supplied exact-profile port factory."""
        self._factory = factory

    async def execute(
        self,
        request: OperationRequest[ModeloAggregateOperationRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Run a read aggregate or one idempotent ledger-payment capture."""
        payload = request.payload
        profile_id = str(payload.profile_id)
        subject = profile_operation_subject(profile_id)
        if (
            request.definition_id != MODELO_AGGREGATE_OPERATION_DEFINITION_ID
            or request.subject_ref != subject
            or context.identity.definition_id != request.definition_id
            or context.identity.subject_ref != subject
            or require_active_bucket_id() != profile_id
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

        await context.events.phase(_PREPARE_PHASE)
        operation = context.authority_operation
        try:
            prepared = await asyncio.to_thread(self._prepare, payload, profile_id, operation)
        except AggregationUnsupportedModeloError as error:
            return await self._refuse(
                payload,
                context,
                refusal_code=MODELO_AGGREGATE_UNSUPPORTED_MODELO_REFUSAL_CODE,
                reason=_bounded_reason(error),
            )
        except LedgerPaymentWithholdingEvidenceError as error:
            return await self._refuse(
                payload,
                context,
                refusal_code=MODELO_AGGREGATE_LEDGER_PAYMENT_REFUSAL_CODE,
                reason=_bounded_reason(error),
            )
        except WithholdingFilingCadenceError as error:
            return await self._refuse(
                payload,
                context,
                refusal_code=MODELO_AGGREGATE_CADENCE_REFUSAL_CODE,
                reason=_bounded_reason(error),
            )

        capture = prepared.capture
        if capture is None:
            return await self._publish_aggregate(
                prepared=prepared,
                payload=payload,
                context=context,
                aggregate_result=prepared.preflight_result,
                window_state=prepared.window_state,
                local_write_performed=False,
            )

        async def commit_and_aggregate() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                self._require_active_profile(profile_id)
                await context.events.phase(_COMMIT_PHASE)
                current_revision = await asyncio.to_thread(
                    prepared.ports.transaction_catalogue_repository.load_revision
                )
                if current_revision != capture.catalogue_read_revision_id:
                    await context.events.effect(OperationEffect.NONE)
                    return await self._record_refusal(
                        payload,
                        context,
                        refusal_code=MODELO_AGGREGATE_LEDGER_PAYMENT_REFUSAL_CODE,
                        reason=(
                            "transaction_catalogue_revision_unavailable"
                            if current_revision is None
                            else "transaction_catalogue_revision_changed"
                        ),
                    )
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    if prepared.cadence is None:
                        raise AssertionError("ledger capture preparation must resolve filer cadence")
                    captured = await asyncio.to_thread(
                        WithholdingProducer(service=prepared.ports.withholding_observation_service).capture,
                        capture.command,
                        cadence=prepared.cadence,
                        source_catalogue_revision_id=capture.catalogue_read_revision_id,
                    )
                except (WithholdingProducerError, WithholdingRecognitionError) as error:
                    # Producer validation and recognition finish before service.apply;
                    # storage failures remain UNKNOWN because their delivery is ambiguous.
                    await context.events.effect(OperationEffect.NONE)
                    refusal_code = (
                        MODELO_AGGREGATE_PRODUCER_REFUSAL_CODE
                        if isinstance(error, WithholdingProducerError)
                        else MODELO_AGGREGATE_RECOGNITION_REFUSAL_CODE
                    )
                    return await self._record_refusal(
                        payload,
                        context,
                        refusal_code=refusal_code,
                        reason=_bounded_reason(error),
                    )
                except WithholdingObservationMutationError as error:
                    if error.refusal_code != "source_revision_changed":
                        raise
                    await context.events.effect(OperationEffect.NONE)
                    return await self._record_refusal(
                        payload,
                        context,
                        refusal_code=MODELO_AGGREGATE_LEDGER_PAYMENT_REFUSAL_CODE,
                        reason=_bounded_reason(error),
                    )
                if captured is None or captured.scope != capture.scope:
                    raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

                local_write_performed = not captured.mutation.replayed
                await context.events.effect(OperationEffect.UPDATED if local_write_performed else OperationEffect.NONE)
                self._require_active_profile(profile_id)
                window_state = await asyncio.to_thread(
                    prepared.ports.withholding_observation_service.read_window,
                    capture.scope,
                )
                aggregate_command = self._withholding_command(prepared.aggregate_command, window_state)
                aggregate_result = await asyncio.to_thread(self._aggregate, aggregate_command, operation)
                return await self._publish_aggregate(
                    prepared=prepared,
                    payload=payload,
                    context=context,
                    aggregate_result=aggregate_result,
                    window_state=window_state,
                    local_write_performed=local_write_performed,
                )

        return await commit_and_aggregate()

    def _prepare(
        self,
        payload: ModeloAggregateOperationRequest,
        profile_id: str,
        operation: PinnedAuthorityOperation,
    ) -> _PreparedModeloAggregate:
        self._require_active_profile(profile_id)
        ports = _profile_ports(self._factory, profile_id=profile_id)
        with validating_governed_facts(operation):
            command = payload.command.to_domain()
            window_state = (
                ports.withholding_observation_service.read_window(
                    WithholdingWindowScope(modelo=command.modelo, period=command.period)
                )
                if command.modelo in _WITHHOLDING_MODELOS
                else None
            )
            command = self._withholding_command(command, window_state)
            provider = provider_for_modelo(command.modelo, operation=operation)
            preflight_result = aggregate_per_modelo(command, operation=operation)
        if preflight_result.provider is not provider:
            raise AggregationConfigError("aggregate preflight provider changed")
        if payload.ledger_payment is None:
            return _PreparedModeloAggregate(
                ports=ports,
                aggregate_command=command,
                preflight_result=preflight_result,
                window_state=window_state,
            )

        if provider is not PerModeloAggregationContributor.RETENCIONES:
            raise LedgerPaymentWithholdingEvidenceError("ledger_payment_provider_mismatch")
        try:
            with validating_governed_facts(operation):
                ledger_request = payload.ledger_payment.to_domain()
        except ValueError as error:
            raise LedgerPaymentWithholdingEvidenceError("invalid_evidence") from error
        cadence = load_bucket_withholding_filer_cadence(
            bucket_id=profile_id,
            filing_year=command.period.filing_year,
            operation=operation,
        )
        transaction_repository = ports.transaction_catalogue_repository
        first_revision = transaction_repository.load_revision()
        if first_revision is None:
            raise LedgerPaymentWithholdingEvidenceError("transaction_catalogue_revision_unavailable")
        catalogue = transaction_repository.load_by_ids((str(payload.ledger_payment.transaction_id),))
        second_revision = transaction_repository.load_revision()
        if second_revision is None or second_revision != first_revision:
            raise LedgerPaymentWithholdingEvidenceError("transaction_catalogue_revision_changed")
        transaction = resolve_ledger_payment_transaction(catalogue, str(payload.ledger_payment.transaction_id))
        with validating_governed_facts(operation):
            capture = build_ledger_payment_withholding_capture(
                transaction,
                catalogue_revision_id=first_revision,
                request=ledger_request,
                applicable_year=command.period.filing_year,
                cadence=cadence,
            )
        if capture.scope.modelo != command.modelo or capture.scope.period != command.period:
            raise LedgerPaymentWithholdingEvidenceError("ledger_payment_period_mismatch")
        return _PreparedModeloAggregate(
            ports=ports,
            aggregate_command=command,
            preflight_result=preflight_result,
            window_state=window_state,
            capture=capture,
            cadence=cadence,
        )

    @staticmethod
    def _withholding_command(
        command: PerModeloAggregationCommand,
        state: WithholdingWindowState | None,
    ) -> PerModeloAggregationCommand:
        if state is None:
            return command
        if state.scope != WithholdingWindowScope(modelo=command.modelo, period=command.period):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        observations = tuple(entry.retencion for entry in state.entries if entry.retencion is not None)
        return command.model_copy(update={"retencion_observations": observations})

    @staticmethod
    def _aggregate(
        command: PerModeloAggregationCommand,
        operation: PinnedAuthorityOperation,
    ) -> PerModeloAggregationResult:
        with validating_governed_facts(operation):
            return aggregate_per_modelo(command, operation=operation)

    async def _publish_aggregate(
        self,
        *,
        prepared: _PreparedModeloAggregate,
        payload: ModeloAggregateOperationRequest,
        context: OperationExecutorContext,
        aggregate_result: PerModeloAggregationResult,
        window_state: WithholdingWindowState | None,
        local_write_performed: bool,
    ) -> str | OperationRefusalEvidence:
        if (
            str(aggregate_result.modelo) != payload.command.modelo
            or aggregate_result.period != payload.command.period.to_period()
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        if aggregate_result.provider is not prepared.preflight_result.provider:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        window = await asyncio.to_thread(
            self._project_window_state,
            prepared.ports,
            window_state,
        )
        projection = ModeloAggregateProjection(
            outcome="aggregated",
            profile_id=payload.profile_id,
            modelo=str(aggregate_result.modelo),
            period=PublicPeriod.from_period(aggregate_result.period),
            provider=aggregate_result.provider,
            observation_count=aggregate_result.log_fields.observation_count,
            source_kinds=aggregate_result.source_kinds,
            result_row_count=aggregate_result.log_fields.result_row_count,
            clave_breakdown=(),
            withholding_window=window,
        )
        await context.events.phase(_RESULT_PHASE)
        report = ModeloAggregateReport(projection=projection, local_write_performed=local_write_performed)
        if len(canonical_json_bytes(report.model_dump(mode="json"))) > _MAX_RESULT_BYTES:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
        if require_active_bucket_id() != str(payload.profile_id):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        if not local_write_performed and payload.ledger_payment is None:
            await context.events.effect(OperationEffect.NONE)
        return await context.operands.put(report, written_at=now())

    @staticmethod
    def _project_window_state(
        ports: ModeloAggregateOperationPorts,
        state: WithholdingWindowState | None,
    ) -> ModeloAggregateWindow | None:
        if state is None:
            return None
        audit = (
            None
            if state.generation == 0
            else ports.withholding_observation_service.read_generation(state.scope, state.baseline.generation_id)
        )
        return _project_window(baseline=state.baseline, generation=state.generation, audit=audit)

    @staticmethod
    def _require_active_profile(profile_id: str) -> None:
        if require_active_bucket_id() != profile_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)

    async def _refuse(
        self,
        payload: ModeloAggregateOperationRequest,
        context: OperationExecutorContext,
        *,
        refusal_code: str,
        reason: str,
    ) -> OperationRefusalEvidence:
        async with context.cancellation.irreversible_section():
            self._require_active_profile(str(payload.profile_id))
            await context.events.effect(OperationEffect.NONE)
            return await self._record_refusal(payload, context, refusal_code=refusal_code, reason=reason)

    async def _record_refusal(
        self,
        payload: ModeloAggregateOperationRequest,
        context: OperationExecutorContext,
        *,
        refusal_code: str,
        reason: str,
    ) -> OperationRefusalEvidence:
        if refusal_code not in MODELO_AGGREGATE_REFUSAL_CODES:
            raise ValueError("modelo-aggregate refusal code is not registered for this operation")
        detail = ModeloAggregateReport(
            projection=_refused_projection(
                profile_id=payload.profile_id,
                command=payload.command,
                reason=reason,
            ),
            local_write_performed=False,
            refusal_code=refusal_code,
        )
        detail_ref = await context.operands.put(detail, written_at=now())
        return OperationRefusalEvidence(refusal_code=refusal_code, detail_ref=detail_ref)


@dataclass(frozen=True, slots=True)
class _PreparedModeloAggregate:
    ports: ModeloAggregateOperationPorts
    aggregate_command: PerModeloAggregationCommand
    preflight_result: PerModeloAggregationResult
    window_state: WithholdingWindowState | None = None
    capture: LedgerPaymentWithholdingCapture | None = None
    cadence: WithholdingFilerCadence | None = None


def build_modelo_aggregate_operation_definition(
    factory: ModeloAggregateOperationPortsFactory,
) -> OperationDefinition:
    """Declare exact-profile scope, confidential operands, and honest write effects."""
    return OperationDefinition(
        definition_id=MODELO_AGGREGATE_OPERATION_DEFINITION_ID,
        request_type=ModeloAggregateOperationRequest,
        result_type=ModeloAggregateReport,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloAggregateOperationRequest,
            executor_type=ModeloAggregateExecutor,
            build=lambda: ModeloAggregateExecutor(factory),
        ),
        phase_codes=_PHASES,
        interaction_kinds=frozenset(),
        capabilities=OperationCapabilities(
            durability=OperationDurability.RECORDED,
            cancellation=OperationCancellation.UNSUPPORTED,
            deadline=OperationDeadline.ABSENT,
            replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
            baseline=OperationBaselinePolicy.NONE,
            request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
            sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
            conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
            owned_resources=frozenset(),
            permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
            close_policy=OperationClosePolicy.DETACH_ALLOWED,
        ),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {
                OperationFrontendProjection.CLI,
                OperationFrontendProjection.TUI,
                OperationFrontendProjection.MCP,
            }
        ),
        refusal_detail_codes=MODELO_AGGREGATE_REFUSAL_CODES,
    )


def resolve_modelo_aggregate_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Bind result disclosure and optional capture COMMIT rights to one profile and period."""
    if request.definition_id != MODELO_AGGREGATE_OPERATION_DEFINITION_ID or not isinstance(
        request.payload, ModeloAggregateOperationRequest
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    payload = request.payload
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    # A capture reads a revision digest over the complete profile transaction
    # catalogue to bracket its targeted transaction read. Ordinary aggregate
    # and stored-window reads stay scoped to the requested filing period.
    access_periods: frozenset[Period] = (
        frozenset[Period]() if payload.ledger_payment is not None else frozenset({payload.command.period.to_period()})
    )
    resolved = resolve_ledger_read_access(
        request,
        context,
        profile_id=payload.profile_id,
        periods=access_periods,
    )
    if payload.ledger_payment is None:
        return resolved
    policy = OperationAccessPolicy.model_validate(
        {**dict(resolved.policy), "actions": resolved.policy.actions | {AccessAction.COMMIT}}
    )
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


def build_modelo_aggregate_operation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the secure request to its bounded aggregate projection."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=MODELO_AGGREGATE_OPERATION_DEFINITION_ID + ".request",
            schema_version=1,
            model_type=ModeloAggregateOperationRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=MODELO_AGGREGATE_OPERATION_DEFINITION_ID + ".result",
            schema_version=1,
            model_type=ModeloAggregateProjection,
        ),
        result_projector=project_modelo_aggregate_result,
        access_resolver=resolve_modelo_aggregate_access,
    )


__all__ = [
    "MODELO_AGGREGATE_CADENCE_REFUSAL_CODE",
    "MODELO_AGGREGATE_LEDGER_PAYMENT_REFUSAL_CODE",
    "MODELO_AGGREGATE_OPERATION_DEFINITION_ID",
    "MODELO_AGGREGATE_PRODUCER_REFUSAL_CODE",
    "MODELO_AGGREGATE_RECOGNITION_REFUSAL_CODE",
    "MODELO_AGGREGATE_REFUSAL_CODES",
    "MODELO_AGGREGATE_UNSUPPORTED_MODELO_REFUSAL_CODE",
    "ModeloAggregateExecutor",
    "ModeloAggregateGenerationAudit",
    "ModeloAggregateOperationPorts",
    "ModeloAggregateOperationPortsFactory",
    "ModeloAggregateOperationRequest",
    "ModeloAggregateProjection",
    "ModeloAggregateReport",
    "ModeloAggregateWindow",
    "ModeloAggregateWindowBaseline",
    "TransactionCatalogueReadPort",
    "build_modelo_aggregate_operation_definition",
    "build_modelo_aggregate_operation_registration",
    "project_modelo_aggregate_result",
    "resolve_modelo_aggregate_access",
]
