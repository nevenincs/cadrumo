"""Profile-bound execution stages for activity-asset operations."""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.renta.actividad_asset.errors import (
    ActividadAssetClaimConflictError,
    ActividadAssetIncompleteError,
    ActividadAssetUnsupportedError,
    ActividadAssetValidationError,
)
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.renta.actividad_asset.schedule import AssetScheduleHistory, ScheduledAmortizationCharge
from ...domain.user_profile.plantilla_media import plantilla_media_years
from ..calculations.actividad_asset_schedule import forecast_activity_asset_charge
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..operator_actions.models import PreconditionVerdict
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .activity_asset_contracts import (
    ACTIVITY_ASSET_CLAIM_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_CORRECT_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_CREATE_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_FILING_HANDOFF_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_FORECAST_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_INSPECT_OPERATION_DEFINITION_ID,
    ACTIVITY_ASSET_REFUSED_CLAIM_CONFLICT,
    ACTIVITY_ASSET_REFUSED_INCOMPLETE,
    ACTIVITY_ASSET_REFUSED_UNSUPPORTED,
    ACTIVITY_ASSET_REFUSED_VALIDATION,
    ActivityAssetAuthorityProvenance,
    ActivityAssetClaimRequest,
    ActivityAssetCorrectRequest,
    ActivityAssetCreateRequest,
    ActivityAssetFilingHandoffRequest,
    ActivityAssetForecastRequest,
    ActivityAssetInspectRequest,
    ActivityAssetOperationPorts,
    ActivityAssetOperationPortsFactory,
)
from .activity_asset_results import (
    ActivityAssetClaimResult,
    ActivityAssetCorrectResult,
    ActivityAssetCreateResult,
    ActivityAssetFilingHandoffResult,
    ActivityAssetForecastResult,
    ActivityAssetInspectionRevision,
    ActivityAssetInspectResult,
    ActivityAssetOperationResult,
    ActivityAssetRefusalResult,
)
from .modality import direct_estimation_modality
from .operation_dtos import ActivityAssetRevisionSnapshot
from .operations import ActivityAssetOperations


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
        requested_free_amount: Decimal | None,
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

    return ActivityAssetOperations(
        repository=ports.history_repository,
        forecast_operation=forecast,
        taxpayer_modality=taxpayer_modality,
    )


def _worker_bucket(
    request: OperationRequest[Any],
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
    if isinstance(error, ActividadAssetIncompleteError):
        verdict = error.terminal_precondition_verdict
        return ActivityAssetRefusalResult(
            code=ACTIVITY_ASSET_REFUSED_INCOMPLETE,
            precondition_verdict=verdict if isinstance(verdict, PreconditionVerdict) else None,
        )
    if isinstance(error, ActividadAssetUnsupportedError):
        return ActivityAssetRefusalResult(code=ACTIVITY_ASSET_REFUSED_UNSUPPORTED)
    if isinstance(error, ActividadAssetClaimConflictError):
        return ActivityAssetRefusalResult(code=ACTIVITY_ASSET_REFUSED_CLAIM_CONFLICT)
    if isinstance(error, ActividadAssetValidationError):
        return ActivityAssetRefusalResult(code=ACTIVITY_ASSET_REFUSED_VALIDATION)
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
        **({"asset_id": asset_id} if result_type is ActivityAssetInspectResult else {}),
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
            cast(OperationRequest[Any], request),
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
                    history = await asyncio.to_thread(operations.create, payload.revision.to_domain())
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
            cast(OperationRequest[Any], request),
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
            cast(OperationRequest[Any], request),
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
                    history = await asyncio.to_thread(operations.correct, payload.revision.to_domain())
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
            cast(OperationRequest[Any], request),
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
            cast(OperationRequest[Any], request),
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
                        creating_operation=payload.creating_operation,
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
            cast(OperationRequest[Any], request),
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
