"""Profile-bound execution stages for activity-asset operations."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.period import Period
from ...core.time.clock import now
from ...core.tipos_actividad import TipoActividad
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistryError
from ...domain.calculations.registry.schema import ModeloRevision
from ...domain.calculations.registry.temporal import TemporalProjectionDirection, revision_temporal_resolution
from ...domain.renta.actividad_asset.errors import (
    ActividadAssetAcceleratedDa18DepreciationError,
    ActividadAssetClaimConflictError,
    ActividadAssetError,
    ActividadAssetIncompleteError,
    ActividadAssetUnsupportedError,
    ActividadAssetValidationError,
)
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.renta.actividad_asset.schedule import AssetScheduleHistory, ScheduledAmortizationCharge
from ...domain.transactions.tipo_actividad_partitions import tipo_actividad_code_set
from ...domain.user_profile.plantilla_media import plantilla_media_years
from ..aggregation.renta_ledger import resident_in_foral_territory
from ..calculations.actividad_asset_schedule import forecast_activity_asset_charge
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operator_actions.models import PreconditionVerdict
from ..user_profile.access_errors import ProfileAccessRefusedError
from .activity_asset_contracts import (
    ACTIVITY_ASSET_ACQUISITION_CANDIDATES_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_DESCRIBE_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_FORM_OPTIONS_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_LIST_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_PLAN_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_REFUSED_ACCELERATED_DA18,
    ACTIVITY_ASSET_REFUSED_CLAIM_CONFLICT,
    ACTIVITY_ASSET_REFUSED_INCOMPLETE,
    ACTIVITY_ASSET_REFUSED_UNSUPPORTED,
    ACTIVITY_ASSET_REFUSED_VALIDATION,
    ACTIVITY_ASSET_TIMELINE_OPERATION_DEFINITION_ID,
    ActivityAssetAcceleratedDa18Facts,
    ActivityAssetAcquisitionCandidatesRequest,
    ActivityAssetAuthorityProvenance,
    ActivityAssetClaimRequest,
    ActivityAssetCorrectRequest,
    ActivityAssetCreateRequest,
    ActivityAssetDescribeRequest,
    ActivityAssetFilingHandoffRequest,
    ActivityAssetForecastRequest,
    ActivityAssetFormOptionsRequest,
    ActivityAssetInspectRequest,
    ActivityAssetListRequest,
    ActivityAssetOperationPorts,
    ActivityAssetOperationPortsFactory,
    ActivityAssetPlanRequest,
    ActivityAssetTimelineRequest,
)
from .activity_asset_read_models import ActivityAssetEdition
from .activity_asset_results import (
    ActivityAssetAcquisitionCandidatesResult,
    ActivityAssetClaimResult,
    ActivityAssetCorrectResult,
    ActivityAssetCreateResult,
    ActivityAssetDescribeResult,
    ActivityAssetFilingHandoffResult,
    ActivityAssetForecastResult,
    ActivityAssetFormOptionsResult,
    ActivityAssetInspectionRevision,
    ActivityAssetInspectResult,
    ActivityAssetListResult,
    ActivityAssetOperationResult,
    ActivityAssetPlanResult,
    ActivityAssetRefusalResult,
    ActivityAssetTimelineResult,
)
from .modality import direct_estimation_modality
from .operation_dtos import ActivityAssetRevisionSnapshot
from .operations import ActivityAssetOperations, ActivityAssetRegisterAuthority, SupersedingClaimRequest

_AGRARIAN_INSTALMENT_SELECTOR = "rd-439-2007-art-110:selector-m036-actividades-pago-fraccionado-agrarias-pesqueras"
"""The activities whose instalment is a share of income under RIRPF art. 110.1.c."""


def _authority_provenance(operation: PinnedAuthorityOperation) -> ActivityAssetAuthorityProvenance:
    pin = operation.pin()
    return ActivityAssetAuthorityProvenance(
        logical_generation=pin.logical_generation,
        reader_incarnation=pin.reader_incarnation,
    )


def _activity_asset_operations(
    *,
    bucket_id: str,
    ports: ActivityAssetOperationPorts,
    operation: PinnedAuthorityOperation,
) -> ActivityAssetOperations:
    """Bind the canonical domain service to one worker profile and authority pin."""

    def profile_values() -> dict[str, str] | None:
        values = ports.profile_path_values.load_path_values(bucket_id=bucket_id)
        return None if values is None else dict(values)

    def taxpayer_modality():
        values = profile_values()
        token = None if values is None else values.get("irpf.estimation_regime")
        return direct_estimation_modality(token, authority=operation)

    def taxpayer_workforce():
        values = profile_values()
        return () if values is None else plantilla_media_years(values)

    def forecast(
        revision: ActivityAssetRevision,
        *,
        covered_from: date,
        covered_until: date,
        history: AssetScheduleHistory,
        requested_free_amount: Decimal | None = None,
    ) -> ScheduledAmortizationCharge:
        return forecast_activity_asset_charge(
            revision,
            modelo_100_revision=operation.revision_for_context(
                "100",
                filing_year=covered_from.year,
                period="0A",
            ),
            authority_generation=operation.pin().logical_generation,
            covered_from=covered_from,
            covered_until=covered_until,
            history=history,
            taxpayer_workforce=taxpayer_workforce,
            legal_reference=operation.legal_reference,
            requested_free_amount=requested_free_amount,
        )

    def edition(tax_year: int) -> tuple[ActivityAssetEdition, ModeloRevision]:
        revision = operation.revision_for_context("100", filing_year=tax_year, period="0A")
        resolution = revision_temporal_resolution(
            revision,
            filing_year=tax_year,
            period="0A",
            support=operation.supported_filing_years(),
        )
        return (
            ActivityAssetEdition(
                revision_id=revision.id,
                authored_filing_year=resolution.authored_filing_year,
                projected=resolution.projection_direction is not TemporalProjectionDirection.AUTHORED,
            ),
            revision,
        )

    def agrarian_activities(on: date) -> frozenset[TipoActividad]:
        return frozenset(
            TipoActividad(code)
            for code in tipo_actividad_code_set(
                _AGRARIAN_INSTALMENT_SELECTOR,
                effective_date=on,
                authority=operation,
            )
        )

    return ActivityAssetOperations(
        repository=ports.history_repository,
        ledger=ports.ledger,
        forecast_operation=forecast,
        taxpayer_modality=taxpayer_modality,
        register_authority=ActivityAssetRegisterAuthority(
            edition=edition,
            agrarian_activities=agrarian_activities,
            foral_territory=lambda: resident_in_foral_territory(bucket_id=bucket_id, operation=operation),
            claim_consumers=ports.claim_consumers,
            today=lambda: now().date(),
        ),
    )


def _worker_bucket[T: BaseModel](
    request: OperationRequest[T],
    context: OperationExecutorContext,
    *,
    definition_id: str,
    profile_id: UUID,
) -> str:
    bucket_id = str(profile_id)
    expected_subject = profile_operation_subject(bucket_id)
    if (
        request.definition_id != definition_id
        or request.subject_ref != expected_subject
        or context.identity.definition_id != definition_id
        or context.identity.subject_ref != expected_subject
        or require_active_bucket_id() != bucket_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return bucket_id


def _refusal(error: Exception) -> ActivityAssetRefusalResult | None:
    if not isinstance(error, ActividadAssetError):
        return None
    detail: dict[str, object] = {
        "reason_key": error.translated_message,
        "reason_facts": {name: str(value) for name, value in (error.context or {}).items()},
    }
    if isinstance(error, ActividadAssetIncompleteError):
        verdict = error.terminal_precondition_verdict
        return ActivityAssetRefusalResult(
            code=ACTIVITY_ASSET_REFUSED_INCOMPLETE,
            precondition_verdict=verdict if isinstance(verdict, PreconditionVerdict) else None,
            **detail,
        )
    if isinstance(error, ActividadAssetAcceleratedDa18DepreciationError):
        return ActivityAssetRefusalResult(
            code=ACTIVITY_ASSET_REFUSED_ACCELERATED_DA18,
            accelerated_da18=ActivityAssetAcceleratedDa18Facts.from_error(error),
            **detail,
        )
    if isinstance(error, ActividadAssetUnsupportedError):
        return ActivityAssetRefusalResult(code=ACTIVITY_ASSET_REFUSED_UNSUPPORTED, **detail)
    if isinstance(error, ActividadAssetClaimConflictError):
        return ActivityAssetRefusalResult(code=ACTIVITY_ASSET_REFUSED_CLAIM_CONFLICT, **detail)
    if isinstance(error, ActividadAssetValidationError):
        return ActivityAssetRefusalResult(code=ACTIVITY_ASSET_REFUSED_VALIDATION, **detail)
    return None


async def _store_refusal(
    context: OperationExecutorContext,
    *,
    result_type: type[ActivityAssetOperationResult],
    profile_id: UUID,
    authority: ActivityAssetAuthorityProvenance,
    error: Exception,
    asset_id: str | None = None,
    tax_year: int | None = None,
    m130_period: str | None = None,
) -> OperationRefusalEvidence:
    refusal = _refusal(error)
    if refusal is None:
        raise error
    result = result_type(
        profile_id=profile_id,
        authority=authority,
        outcome="refused",
        refusal=refusal,
        **(
            {"asset_id": asset_id}
            if result_type in {ActivityAssetInspectResult, ActivityAssetPlanResult, ActivityAssetTimelineResult}
            else {}
        ),
        **(
            {"tax_year": tax_year, "m130_period": m130_period}
            if result_type is ActivityAssetFilingHandoffResult
            else {}
        ),
    )
    detail_ref = await context.operands.put(result, written_at=now())
    await context.events.effect(OperationEffect.NONE)
    return OperationRefusalEvidence(refusal_code=refusal.code, detail_ref=detail_ref)


async def _load_operations(
    ports_factory: ActivityAssetOperationPortsFactory,
    *,
    bucket_id: str,
    operation: PinnedAuthorityOperation,
) -> ActivityAssetOperations:
    ports = await asyncio.to_thread(ports_factory, bucket_id=bucket_id, operation=operation)
    if not isinstance(ports, ActivityAssetOperationPorts):
        raise TypeError("activity-asset composition returned incompatible operation ports")
    return _activity_asset_operations(bucket_id=bucket_id, ports=ports, operation=operation)


class ActivityAssetCreateExecutor:
    """Execute one profile-bound first revision and preserve terminal effect semantics."""

    def __init__(self, ports_factory: ActivityAssetOperationPortsFactory) -> None:
        """Bind the worker-scoped history port factory."""
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[ActivityAssetCreateRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Run the typed operation and return its terminal reference or refusal."""
        payload = request.payload
        bucket_id = _worker_bucket(
            request,
            context,
            definition_id=ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID,
            profile_id=payload.profile_id,
        )
        authority = _authority_provenance(context.authority_operation)
        await context.events.phase(ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID)

        async def commit() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                operations = await _load_operations(
                    self._ports_factory,
                    bucket_id=bucket_id,
                    operation=context.authority_operation,
                )
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    history = await asyncio.to_thread(
                        operations.create,
                        payload.revision.to_domain(),
                        payload.descriptor,
                        recorded_at=now(),
                        origin=ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID,
                    )
                except (
                    ActividadAssetClaimConflictError,
                    ActividadAssetIncompleteError,
                    ActividadAssetUnsupportedError,
                    ActividadAssetValidationError,
                ) as error:
                    return await _store_refusal(
                        context,
                        result_type=ActivityAssetCreateResult,
                        profile_id=payload.profile_id,
                        authority=authority,
                        error=error,
                    )
                result = ActivityAssetCreateResult(
                    profile_id=payload.profile_id,
                    authority=authority,
                    outcome="succeeded",
                    history=history,
                )
                reference = await context.operands.put(result, written_at=now())
                await context.events.effect(OperationEffect.UPDATED)
                return reference

        return await await_cancellation_complete(commit(), task_name="activity-asset-create")


class ActivityAssetInspectExecutor:
    """Execute a read-only full-chain inspection for one activity asset."""

    def __init__(self, ports_factory: ActivityAssetOperationPortsFactory) -> None:
        """Bind the worker-scoped history port factory."""
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[ActivityAssetInspectRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Run the typed operation and return its terminal reference or refusal."""
        payload = request.payload
        bucket_id = _worker_bucket(
            request,
            context,
            definition_id=ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID,
            profile_id=payload.profile_id,
        )
        authority = _authority_provenance(context.authority_operation)
        await context.events.phase(ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID)

        async def capture() -> str | OperationRefusalEvidence:
            operations = await _load_operations(
                self._ports_factory,
                bucket_id=bucket_id,
                operation=context.authority_operation,
            )
            try:
                revisions = await asyncio.to_thread(operations.inspect, payload.asset_id)
            except (
                ActividadAssetClaimConflictError,
                ActividadAssetIncompleteError,
                ActividadAssetUnsupportedError,
                ActividadAssetValidationError,
            ) as error:
                return await _store_refusal(
                    context,
                    result_type=ActivityAssetInspectResult,
                    profile_id=payload.profile_id,
                    authority=authority,
                    error=error,
                    asset_id=payload.asset_id,
                )
            result = ActivityAssetInspectResult(
                profile_id=payload.profile_id,
                authority=authority,
                outcome="succeeded",
                asset_id=payload.asset_id,
                revisions=tuple(
                    ActivityAssetInspectionRevision(
                        revision=ActivityAssetRevisionSnapshot.from_domain(revision),
                        revision_id=revision.revision_id,
                    )
                    for revision in revisions
                ),
            )
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="activity-asset-inspect")


class ActivityAssetCorrectExecutor:
    """Append one validated revision through the exact profile repository."""

    def __init__(self, ports_factory: ActivityAssetOperationPortsFactory) -> None:
        """Bind the worker-scoped history port factory."""
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[ActivityAssetCorrectRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Run the typed operation and return its terminal reference or refusal."""
        payload = request.payload
        bucket_id = _worker_bucket(
            request,
            context,
            definition_id=ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID,
            profile_id=payload.profile_id,
        )
        authority = _authority_provenance(context.authority_operation)
        await context.events.phase(ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID)

        async def commit() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                operations = await _load_operations(
                    self._ports_factory,
                    bucket_id=bucket_id,
                    operation=context.authority_operation,
                )
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    history = await asyncio.to_thread(
                        operations.correct,
                        payload.revision.to_domain(),
                        tuple(
                            SupersedingClaimRequest(
                                supersedes_claim_id=item.supersedes_claim_id,
                                requested_free_amount=(
                                    None
                                    if item.requested_free_amount is None
                                    else Decimal(item.requested_free_amount.decimal)
                                ),
                            )
                            for item in payload.superseding_claims
                        ),
                        recorded_at=now(),
                        origin=ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID,
                    )
                except (
                    ActividadAssetClaimConflictError,
                    ActividadAssetIncompleteError,
                    ActividadAssetUnsupportedError,
                    ActividadAssetValidationError,
                ) as error:
                    return await _store_refusal(
                        context,
                        result_type=ActivityAssetCorrectResult,
                        profile_id=payload.profile_id,
                        authority=authority,
                        error=error,
                    )
                result = ActivityAssetCorrectResult(
                    profile_id=payload.profile_id,
                    authority=authority,
                    outcome="succeeded",
                    history=history,
                )
                reference = await context.operands.put(result, written_at=now())
                await context.events.effect(OperationEffect.UPDATED)
                return reference

        return await await_cancellation_complete(commit(), task_name="activity-asset-correct")


class ActivityAssetForecastExecutor:
    """Build a non-consuming forecast from the exact authority pin."""

    def __init__(self, ports_factory: ActivityAssetOperationPortsFactory) -> None:
        """Bind the worker-scoped history port factory."""
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[ActivityAssetForecastRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Run the typed operation and return its terminal reference or refusal."""
        payload = request.payload
        bucket_id = _worker_bucket(
            request,
            context,
            definition_id=ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID,
            profile_id=payload.profile_id,
        )
        authority = _authority_provenance(context.authority_operation)
        await context.events.phase(ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID)

        async def capture() -> str | OperationRefusalEvidence:
            operations = await _load_operations(
                self._ports_factory,
                bucket_id=bucket_id,
                operation=context.authority_operation,
            )
            try:
                forecast = await asyncio.to_thread(
                    operations.forecast,
                    asset_id=payload.asset_id,
                    covered_from=payload.covered_from,
                    covered_until=payload.covered_until,
                    requested_free_amount=(
                        Decimal(payload.requested_free_amount.decimal)
                        if payload.requested_free_amount is not None
                        else None
                    ),
                    supersedes_claim_id=payload.supersedes_claim_id,
                )
            except (
                ActividadAssetClaimConflictError,
                ActividadAssetIncompleteError,
                ActividadAssetUnsupportedError,
                ActividadAssetValidationError,
            ) as error:
                return await _store_refusal(
                    context,
                    result_type=ActivityAssetForecastResult,
                    profile_id=payload.profile_id,
                    authority=authority,
                    error=error,
                )
            result = ActivityAssetForecastResult(
                profile_id=payload.profile_id,
                authority=authority,
                outcome="succeeded",
                forecast=forecast,
            )
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="activity-asset-forecast")


class ActivityAssetClaimExecutor:
    """Record or replay one explicit forecast claim."""

    def __init__(self, ports_factory: ActivityAssetOperationPortsFactory) -> None:
        """Bind the worker-scoped history port factory."""
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[ActivityAssetClaimRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Run the typed operation and return its terminal reference or refusal."""
        payload = request.payload
        bucket_id = _worker_bucket(
            request,
            context,
            definition_id=ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID,
            profile_id=payload.profile_id,
        )
        authority = _authority_provenance(context.authority_operation)
        await context.events.phase(ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID)

        async def commit() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                operations = await _load_operations(
                    self._ports_factory,
                    bucket_id=bucket_id,
                    operation=context.authority_operation,
                )
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    claim_result = await asyncio.to_thread(
                        operations.record_claim,
                        payload.forecast.to_domain(),
                        creating_operation=ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID,
                        supersedes_claim_id=payload.supersedes_claim_id,
                        recorded_at=now(),
                    )
                except (
                    ActividadAssetClaimConflictError,
                    ActividadAssetIncompleteError,
                    ActividadAssetUnsupportedError,
                    ActividadAssetValidationError,
                ) as error:
                    return await _store_refusal(
                        context,
                        result_type=ActivityAssetClaimResult,
                        profile_id=payload.profile_id,
                        authority=authority,
                        error=error,
                    )
                result = ActivityAssetClaimResult(
                    profile_id=payload.profile_id,
                    authority=authority,
                    outcome="succeeded",
                    claim_result=claim_result,
                    claim_id=claim_result.claim.claim_id,
                )
                reference = await context.operands.put(result, written_at=now())
                await context.events.effect(
                    OperationEffect.NONE if claim_result.reused_existing_claim else OperationEffect.UPDATED
                )
                return reference

        return await await_cancellation_complete(commit(), task_name="activity-asset-claim")


class ActivityAssetFilingHandoffExecutor:
    """Read existing M100 and M130 claim projections for one frame."""

    def __init__(self, ports_factory: ActivityAssetOperationPortsFactory) -> None:
        """Bind the worker-scoped history port factory."""
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[ActivityAssetFilingHandoffRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Run the typed operation and return its terminal reference or refusal."""
        payload = request.payload
        bucket_id = _worker_bucket(
            request,
            context,
            definition_id=ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID,
            profile_id=payload.profile_id,
        )
        authority = _authority_provenance(context.authority_operation)
        await context.events.phase(ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID)

        async def capture() -> str | OperationRefusalEvidence:
            operations = await _load_operations(
                self._ports_factory,
                bucket_id=bucket_id,
                operation=context.authority_operation,
            )
            period = Period.from_year_and_code(payload.tax_year, payload.m130_period)
            try:
                handoff = await asyncio.to_thread(
                    operations.filing_handoff,
                    tax_year=payload.tax_year,
                    m130_period=period,
                )
            except (
                ActividadAssetClaimConflictError,
                ActividadAssetIncompleteError,
                ActividadAssetUnsupportedError,
                ActividadAssetValidationError,
            ) as error:
                return await _store_refusal(
                    context,
                    result_type=ActivityAssetFilingHandoffResult,
                    profile_id=payload.profile_id,
                    authority=authority,
                    error=error,
                    tax_year=payload.tax_year,
                    m130_period=payload.m130_period,
                )
            result = ActivityAssetFilingHandoffResult(
                profile_id=payload.profile_id,
                authority=authority,
                outcome="succeeded",
                tax_year=payload.tax_year,
                m130_period=payload.m130_period,
                filing_handoff=handoff,
            )
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name="activity-asset-filing-handoff")


class ActivityAssetDescribeExecutor:
    """Append one element's descriptive facts through the exact profile repository."""

    def __init__(self, ports_factory: ActivityAssetOperationPortsFactory) -> None:
        """Bind the worker-scoped history port factory."""
        self._ports_factory = ports_factory

    async def execute(
        self,
        request: OperationRequest[ActivityAssetDescribeRequest],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Run the typed operation and return its terminal reference or refusal."""
        payload = request.payload
        definition_id = ACTIVITY_ASSET_DESCRIBE_OPERATION_DEFINITION_ID
        bucket_id = _worker_bucket(request, context, definition_id=definition_id, profile_id=payload.profile_id)
        authority = _authority_provenance(context.authority_operation)
        await context.events.phase(definition_id)

        async def commit() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                operations = await _load_operations(
                    self._ports_factory,
                    bucket_id=bucket_id,
                    operation=context.authority_operation,
                )
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    history = await asyncio.to_thread(
                        operations.describe,
                        payload.asset_id,
                        payload.descriptor,
                        recorded_at=now(),
                        origin=definition_id,
                    )
                except ActividadAssetError as error:
                    return await _store_refusal(
                        context,
                        result_type=ActivityAssetDescribeResult,
                        profile_id=payload.profile_id,
                        authority=authority,
                        error=error,
                    )
                result = ActivityAssetDescribeResult(
                    profile_id=payload.profile_id,
                    authority=authority,
                    outcome="succeeded",
                    history=history,
                )
                reference = await context.operands.put(result, written_at=now())
                await context.events.effect(OperationEffect.UPDATED)
                return reference

        return await await_cancellation_complete(commit(), task_name="activity-asset-describe")


class _ActivityAssetReadExecutor[RequestT: BaseModel]:
    """One read of the register: bind the profile, run, keep the result or the typed refusal."""

    definition_id: ClassVar[str]
    result_type: ClassVar[type[ActivityAssetOperationResult]]

    def __init__(self, ports_factory: ActivityAssetOperationPortsFactory) -> None:
        """Bind the worker-scoped history port factory."""
        self._ports_factory = ports_factory

    def _read(self, operations: ActivityAssetOperations, payload: RequestT) -> dict[str, object]:
        """Return the result's payload fields."""
        raise NotImplementedError

    async def execute(
        self,
        request: OperationRequest[RequestT],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Run the typed operation and return its terminal reference or refusal."""
        payload = request.payload
        profile_id: UUID = getattr(payload, "profile_id")
        bucket_id = _worker_bucket(request, context, definition_id=self.definition_id, profile_id=profile_id)
        authority = _authority_provenance(context.authority_operation)
        await context.events.phase(self.definition_id)

        async def capture() -> str | OperationRefusalEvidence:
            operations = await _load_operations(
                self._ports_factory,
                bucket_id=bucket_id,
                operation=context.authority_operation,
            )
            try:
                fields = await asyncio.to_thread(self._read, operations, payload)
            except ActividadAssetError as error:
                return await _store_refusal(
                    context,
                    result_type=self.result_type,
                    profile_id=profile_id,
                    authority=authority,
                    error=error,
                    asset_id=getattr(payload, "asset_id", None),
                )
            result = self.result_type(profile_id=profile_id, authority=authority, outcome="succeeded", **fields)
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(capture(), task_name=self.definition_id)


class ActivityAssetListExecutor(_ActivityAssetReadExecutor[ActivityAssetListRequest]):
    """Summarise the exact profile's register."""

    definition_id = ACTIVITY_ASSET_LIST_OPERATION_DEFINITION_ID
    result_type = ActivityAssetListResult

    def _read(self, operations: ActivityAssetOperations, payload: ActivityAssetListRequest) -> dict[str, object]:
        del payload
        return {"rows": operations.list_elements()}


class ActivityAssetPlanExecutor(_ActivityAssetReadExecutor[ActivityAssetPlanRequest]):
    """Work out one element's amortization plan."""

    definition_id = ACTIVITY_ASSET_PLAN_OPERATION_DEFINITION_ID
    result_type = ActivityAssetPlanResult

    def _read(self, operations: ActivityAssetOperations, payload: ActivityAssetPlanRequest) -> dict[str, object]:
        return {"asset_id": payload.asset_id, "rows": operations.plan(payload.asset_id)}


class ActivityAssetTimelineExecutor(_ActivityAssetReadExecutor[ActivityAssetTimelineRequest]):
    """List one element's ordered history."""

    definition_id = ACTIVITY_ASSET_TIMELINE_OPERATION_DEFINITION_ID
    result_type = ActivityAssetTimelineResult

    def _read(self, operations: ActivityAssetOperations, payload: ActivityAssetTimelineRequest) -> dict[str, object]:
        return {"asset_id": payload.asset_id, "events": operations.timeline(payload.asset_id)}


class ActivityAssetFormOptionsExecutor(_ActivityAssetReadExecutor[ActivityAssetFormOptionsRequest]):
    """Read what the registry admits for an asset kind and tax year."""

    definition_id = ACTIVITY_ASSET_FORM_OPTIONS_OPERATION_DEFINITION_ID
    result_type = ActivityAssetFormOptionsResult

    def _read(self, operations: ActivityAssetOperations, payload: ActivityAssetFormOptionsRequest) -> dict[str, object]:
        try:
            options = operations.form_options(asset_kind=payload.asset_kind, tax_year=payload.tax_year)
        except RegistryError as error:
            raise ActividadAssetUnsupportedError(
                context={"tax_year": payload.tax_year},
                translated_message="ledger.actividad_asset.errors.tax_year_without_edition",
            ) from error
        return {"options": options}


class ActivityAssetAcquisitionCandidatesExecutor(_ActivityAssetReadExecutor[ActivityAssetAcquisitionCandidatesRequest]):
    """List the ledger payments an element could name as its acquisition."""

    definition_id = ACTIVITY_ASSET_ACQUISITION_CANDIDATES_OPERATION_DEFINITION_ID
    result_type = ActivityAssetAcquisitionCandidatesResult

    def _read(
        self,
        operations: ActivityAssetOperations,
        payload: ActivityAssetAcquisitionCandidatesRequest,
    ) -> dict[str, object]:
        del payload
        return {"candidates": operations.acquisition_candidates()}
