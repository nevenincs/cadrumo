"""Registered exact-profile operation for non-invoice modelo aggregation."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from pydantic import BaseModel

from ...core.bucket_pointer import require_active_bucket_id
from ...core.hashing import canonical_json_bytes
from ...core.operations import OperationEffect
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.withholding_bindings import aggregate_withholding_by_clave
from ..aggregation.errors import AggregationConfigError, AggregationUnsupportedModeloError
from ..aggregation.ledger_payment_withholding import (
    LedgerPaymentWithholdingCapture,
    LedgerPaymentWithholdingEvidenceError,
    build_ledger_payment_withholding_capture,
    resolve_ledger_payment_transaction,
)
from ..aggregation.modelo_bindings_retenciones import RetencionesAggregationSourceResolver
from ..aggregation.percepciones_observations_repository import (
    PercepcionObservationPorts,
)
from ..aggregation.retencion_observations_repository import (
    RetencionObservationPorts,
)
from ..aggregation.service import (
    CalculationWithholdingRows,
    PerModeloAggregationCommand,
    PerModeloAggregationContributor,
    PerModeloAggregationResult,
    aggregate_per_modelo,
    load_calculation_withholding_rows,
    provider_for_modelo,
)
from ..aggregation.withholding_filing_cadence import (
    WithholdingFilerCadence,
    WithholdingFilingCadenceError,
    load_bucket_withholding_filer_cadence,
)
from ..aggregation.withholding_observation_service import (
    WithholdingObservationMutationError,
    WithholdingWindowScope,
    WithholdingWindowState,
)
from ..aggregation.withholding_producer import (
    WithholdingEvidenceCaptureResult,
    WithholdingProducer,
    WithholdingProducerError,
)
from ..aggregation.withholding_recognition import WithholdingRecognitionError
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess, with_commit_action
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_access_request_profile_payload, require_operation_profile
from ..operations.public_period import PublicPeriod
from ..operations.public_scalar import PublicDecimal
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operations.registry import (
    ALL_OPERATION_FRONTENDS,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .aggregate_contracts import (
    AGGREGATE_COMMIT_PHASE,
    AGGREGATE_MAX_RESULT_BYTES,
    AGGREGATE_PHASES,
    AGGREGATE_PREPARE_PHASE,
    AGGREGATE_RESULT_PHASE,
    AGGREGATE_WITHHOLDING_MODELOS,
    MODELO_AGGREGATE_CADENCE_REFUSAL_CODE,
    MODELO_AGGREGATE_LEDGER_PAYMENT_REFUSAL_CODE,
    MODELO_AGGREGATE_OPERATION_DEFINITION_ID,
    MODELO_AGGREGATE_PRODUCER_REFUSAL_CODE,
    MODELO_AGGREGATE_RECOGNITION_REFUSAL_CODE,
    MODELO_AGGREGATE_REFUSAL_CODES,
    MODELO_AGGREGATE_UNSUPPORTED_MODELO_REFUSAL_CODE,
)
from .aggregate_ports import ModeloAggregateOperationPorts, ModeloAggregateOperationPortsFactory
from .aggregate_projection import (
    ModeloAggregateClaveTotals,
    ModeloAggregateProjection,
    ModeloAggregateReport,
    ModeloAggregateWindow,
    bounded_aggregate_refusal_reason,
    project_aggregate_window,
    project_modelo_aggregate_result,
    project_refused_aggregate,
)
from .aggregate_public import PublicLedgerPaymentEvidenceRequest
from .aggregate_request import ModeloAggregateOperationRequest


def _profile_ports(
    factory: ModeloAggregateOperationPortsFactory,
    *,
    profile_id: str,
) -> ModeloAggregateOperationPorts:
    ports = factory(profile_id=profile_id)
    if ports.profile_id != profile_id or ports.transaction_catalogue_repository.bucket_id != profile_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ports


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
        if request.definition_id != MODELO_AGGREGATE_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)

        await context.events.phase(AGGREGATE_PREPARE_PHASE)
        operation = context.authority_operation
        try:
            prepared = await asyncio.to_thread(self._prepare, payload, profile_id, operation)
        except AggregationUnsupportedModeloError as error:
            return await self._refuse(
                payload,
                context,
                refusal_code=MODELO_AGGREGATE_UNSUPPORTED_MODELO_REFUSAL_CODE,
                reason=bounded_aggregate_refusal_reason(error),
            )
        except LedgerPaymentWithholdingEvidenceError as error:
            return await self._refuse(
                payload,
                context,
                refusal_code=MODELO_AGGREGATE_LEDGER_PAYMENT_REFUSAL_CODE,
                reason=bounded_aggregate_refusal_reason(error),
            )
        except WithholdingFilingCadenceError as error:
            return await self._refuse(
                payload,
                context,
                refusal_code=MODELO_AGGREGATE_CADENCE_REFUSAL_CODE,
                reason=bounded_aggregate_refusal_reason(error),
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
                await context.events.phase(AGGREGATE_COMMIT_PHASE)
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
                    captured = await self._capture_prepared_payment(prepared, capture)
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
                        reason=bounded_aggregate_refusal_reason(error),
                    )
                except WithholdingObservationMutationError as error:
                    if error.refusal_code != "source_revision_changed":
                        raise
                    await context.events.effect(OperationEffect.NONE)
                    return await self._record_refusal(
                        payload,
                        context,
                        refusal_code=MODELO_AGGREGATE_LEDGER_PAYMENT_REFUSAL_CODE,
                        reason=bounded_aggregate_refusal_reason(error),
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

    async def _capture_prepared_payment(
        self,
        prepared: _PreparedModeloAggregate,
        capture: LedgerPaymentWithholdingCapture,
    ) -> WithholdingEvidenceCaptureResult | None:
        """Apply one prepared payment under the caller's existing commit fence."""
        if prepared.cadence is None:
            raise AssertionError("ledger capture preparation must resolve filer cadence")
        return await asyncio.to_thread(
            WithholdingProducer(service=prepared.ports.withholding_observation_service).capture,
            capture.command,
            cadence=prepared.cadence,
            source_catalogue_revision_id=capture.catalogue_read_revision_id,
        )

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
                if command.modelo in AGGREGATE_WITHHOLDING_MODELOS
                else None
            )
            command = self._withholding_command(command, window_state)
            calculation_rows = self._calculation_rows(command, ports, profile_id, operation)
            if calculation_rows is not None:
                command = command.model_copy(update={"retencion_observations": calculation_rows.retenciones or ()})
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
                calculation_rows=calculation_rows,
            )

        if provider is not PerModeloAggregationContributor.RETENCIONES:
            raise LedgerPaymentWithholdingEvidenceError("ledger_payment_provider_mismatch")
        return self._prepare_ledger_capture(
            payload.ledger_payment, profile_id, operation, ports, command, preflight_result, window_state
        )

    def _prepare_ledger_capture(
        self,
        ledger_payment: PublicLedgerPaymentEvidenceRequest,
        profile_id: str,
        operation: PinnedAuthorityOperation,
        ports: ModeloAggregateOperationPorts,
        command: PerModeloAggregationCommand,
        preflight_result: PerModeloAggregationResult,
        window_state: WithholdingWindowState | None,
    ) -> _PreparedModeloAggregate:
        """Bracket the exact payment transaction and build its pinned capture."""
        try:
            with validating_governed_facts(operation):
                ledger_request = ledger_payment.to_domain()
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
        catalogue = transaction_repository.load_by_ids((str(ledger_payment.transaction_id),))
        second_revision = transaction_repository.load_revision()
        if second_revision is None or second_revision != first_revision:
            raise LedgerPaymentWithholdingEvidenceError("transaction_catalogue_revision_changed")
        transaction = resolve_ledger_payment_transaction(catalogue, str(ledger_payment.transaction_id))
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
    def _calculation_rows(
        command: PerModeloAggregationCommand,
        ports: ModeloAggregateOperationPorts,
        profile_id: str,
        operation: PinnedAuthorityOperation,
    ) -> CalculationWithholdingRows | None:
        """Read the stored rows an annual withholding summary's calculation reads.

        ``None`` for a periodic window, which is read back from its own store,
        and for a modelo outside the retenciones family, which has no
        withholding store. Every other modelo is an annual summary composed from
        stored windows, so it aggregates exactly what its calculation reads.
        """
        if command.modelo in AGGREGATE_WITHHOLDING_MODELOS or not RetencionesAggregationSourceResolver.supports_modelo(
            command.modelo
        ):
            return None
        return load_calculation_withholding_rows(
            command.modelo,
            command.period,
            operation=operation,
            retencion_ports=RetencionObservationPorts(repository=ports.retencion_observation_repository),
            percepcion_ports=PercepcionObservationPorts(repository=ports.percepcion_observation_repository),
            cadence=lambda: load_bucket_withholding_filer_cadence(
                bucket_id=profile_id,
                filing_year=command.period.filing_year,
                operation=operation,
            ),
        )

    @staticmethod
    def _clave_totals(
        calculation_rows: CalculationWithholdingRows | None,
    ) -> tuple[ModeloAggregateClaveTotals, ...]:
        """Project the per-perceptor-clave rows the calculation reads into per-clave totals."""
        if calculation_rows is None or calculation_rows.percepciones is None:
            return ()
        return tuple(
            ModeloAggregateClaveTotals(
                clave=row.clave.value,
                percepcion_count=row.percepcion_count,
                percibido_total=PublicDecimal(decimal=str(row.percibido_total)),
                retencion_total=PublicDecimal(decimal=str(row.retencion_total)),
            )
            for row in aggregate_withholding_by_clave(calculation_rows.percepciones)
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
            clave_breakdown=self._clave_totals(prepared.calculation_rows),
            absent_source_families=(
                () if prepared.calculation_rows is None else prepared.calculation_rows.absent_source_families
            ),
            calculation_revision_id=(
                None if prepared.calculation_rows is None else prepared.calculation_rows.revision_id
            ),
            withholding_window=window,
        )
        await context.events.phase(AGGREGATE_RESULT_PHASE)
        report = ModeloAggregateReport(projection=projection, local_write_performed=local_write_performed)
        if len(canonical_json_bytes(report.model_dump(mode="json"))) > AGGREGATE_MAX_RESULT_BYTES:
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
        return project_aggregate_window(baseline=state.baseline, generation=state.generation, audit=audit)

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
            projection=project_refused_aggregate(
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
    calculation_rows: CalculationWithholdingRows | None = None
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
        phase_codes=AGGREGATE_PHASES,
        interaction_kinds=frozenset(),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
        refusal_detail_codes=MODELO_AGGREGATE_REFUSAL_CODES,
    )


def resolve_modelo_aggregate_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    /,
) -> ResolvedOperationAccess:
    """Bind result disclosure and optional capture COMMIT rights to one profile and period."""
    payload = require_access_request_profile_payload(
        request,
        definition_id=MODELO_AGGREGATE_OPERATION_DEFINITION_ID,
        payload_type=ModeloAggregateOperationRequest,
        access_profile_id=context.profile_id,
    )
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
    return with_commit_action(resolved)


def build_modelo_aggregate_operation_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind the secure request to its bounded aggregate projection."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=MODELO_AGGREGATE_OPERATION_DEFINITION_ID + ".request",
            schema_version=2,
            model_type=ModeloAggregateOperationRequest,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=MODELO_AGGREGATE_OPERATION_DEFINITION_ID + ".result",
            schema_version=2,
            model_type=ModeloAggregateProjection,
        ),
        result_projector=project_modelo_aggregate_result,
        access_resolver=resolve_modelo_aggregate_access,
    )
