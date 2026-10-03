"""Profile-bound registered operations for the canonical inventory service."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol, cast
from uuid import UUID

from pydantic import BaseModel, ValidationError

from ...core.async_cleanup import await_cancellation_complete
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.contribuyente.inventory.records import (
    InventoryLedgerError,
)
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .errors import (
    InventoryActividadConflictError,
    InventoryActividadNotFoundError,
    InventoryServiceInputError,
)
from .ports import InventoryServicePortsFactory
from .service import (
    InventoryLedgerResult,
    InventoryMovementCommand,
    InventoryService,
    InventoryValuationPreviewResult,
)

if TYPE_CHECKING:
    pass

from .registered_execution_result import (
    InventoryOperationExecutionResult,
    InventoryOperationRefusalDetail,
)
from .registered_requests import (
    INVENTORY_CONFLICT_REFUSAL_CODE,
    INVENTORY_CREATE_OPERATION_DEFINITION_ID,
    INVENTORY_LIST_OPERATION_DEFINITION_ID,
    INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID,
    INVENTORY_NOT_FOUND_REFUSAL_CODE,
    INVENTORY_SERVICE_INPUT_REFUSAL_CODE,
    INVENTORY_VALIDATION_REFUSAL_CODE,
    INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID,
    InventoryClosingAuthorityRecordRequest,
    InventoryCreateRequest,
    InventoryListRequest,
    InventoryMovementAddRequest,
    InventoryMutationOperationId,
    InventoryOperationId,
    InventoryRefusalCode,
    InventoryRefusalReason,
    InventoryValuationPreviewRequest,
)
from .registered_specs import INVENTORY_OPERATION_SHAPES


class _InventoryProfileScopedRequest(Protocol):
    profile_id: UUID


_SERVICE_INPUT_REASONS: dict[str, str] = {
    "application.inventory.service.errors.invalid_valuation_method": "invalid_valuation_method",
    "application.inventory.service.errors.duplicate_movement_id": "duplicate_movement_id",
    "application.inventory.service.errors.closing_authority_conflict": "closing_authority_conflict",
    "errors.refused.refused_profile_inventory_validation": "inventory_validation",
}


class InventoryOperationExecutor:
    """Run one inventory service call under the supervisor's profile custody."""

    def __init__(self, ports_factory: InventoryServicePortsFactory, *, definition_id: str) -> None:
        """Bind the exact operation type to the bucket service factory."""
        self._ports_factory = ports_factory
        self._definition_id = definition_id

    def _service(self, profile_id: UUID) -> InventoryService:
        profile = str(profile_id)
        return InventoryService(ports=self._ports_factory(bucket_id=profile))

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Run one validated request and retain only its typed safe outcome."""
        shape = INVENTORY_OPERATION_SHAPES.get(self._definition_id)
        if shape is None or type(request.payload) is not shape.request_type:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        payload = request.payload
        profile_id = cast(_InventoryProfileScopedRequest, payload).profile_id
        profile = str(profile_id)
        if request.definition_id != self._definition_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, profile_id)
        await context.events.phase(self._definition_id)

        return await self._execute_validated(
            payload=payload,
            context=context,
            profile_id=profile_id,
            profile=profile,
        )

    async def _execute_validated(
        self,
        *,
        payload: BaseModel,
        context: OperationExecutorContext,
        profile_id: UUID,
        profile: str,
    ) -> str | OperationRefusalEvidence:
        if self._definition_id == INVENTORY_LIST_OPERATION_DEFINITION_ID:
            if not isinstance(payload, InventoryListRequest):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            return await self._execute_list(context=context, profile_id=profile_id, profile=profile)
        if self._definition_id == INVENTORY_CREATE_OPERATION_DEFINITION_ID:
            if not isinstance(payload, InventoryCreateRequest):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            return await self._execute_create(
                request=payload,
                context=context,
                profile_id=profile_id,
                profile=profile,
            )
        if self._definition_id == INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID:
            if not isinstance(payload, InventoryMovementAddRequest):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            return await self._execute_movement_add(
                request=payload,
                context=context,
                profile_id=profile_id,
                profile=profile,
            )
        if self._definition_id == INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID:
            if not isinstance(payload, InventoryValuationPreviewRequest):
                raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
            return await self._execute_valuation_preview(
                request=payload,
                context=context,
                profile_id=profile_id,
                profile=profile,
            )
        if not isinstance(payload, InventoryClosingAuthorityRecordRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return await self._execute_closing_authority_record(
            request=payload,
            context=context,
            profile_id=profile_id,
            profile=profile,
        )

    async def _execute_list(
        self,
        *,
        context: OperationExecutorContext,
        profile_id: UUID,
        profile: str,
    ) -> str | OperationRefusalEvidence:
        async def read() -> str:
            rows = await asyncio.to_thread(lambda: self._service(profile_id).list_all(bucket_id=profile))
            result = InventoryOperationExecutionResult(
                operation_id="list",
                outcome="success",
                profile_id=profile_id,
                rows=rows,
            )
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(read(), task_name="inventory-list")

    async def _execute_create(
        self,
        *,
        request: InventoryCreateRequest,
        context: OperationExecutorContext,
        profile_id: UUID,
        profile: str,
    ) -> str | OperationRefusalEvidence:
        def create() -> InventoryLedgerResult:
            return self._service(profile_id).create(
                bucket_id=profile,
                actividad_id=request.actividad_id,
                year=request.year,
                valuation_method=request.valuation_method,
                opening_stock=Decimal(request.opening_stock.decimal),
                actor="runtime",
            )

        return await self._mutate(
            context,
            operation_id="create",
            profile_id=profile_id,
            request=request,
            work=create,
        )

    async def _execute_movement_add(
        self,
        *,
        request: InventoryMovementAddRequest,
        context: OperationExecutorContext,
        profile_id: UUID,
        profile: str,
    ) -> str | OperationRefusalEvidence:
        try:
            movement = InventoryMovementCommand(
                movement_id=request.movement_id,
                movement_date=request.movement_date,
                kind=request.kind,
                quantity=Decimal(request.quantity.decimal),
                unit_cost=Decimal(request.unit_cost.decimal) if request.unit_cost is not None else None,
                taxable_base=Decimal(request.taxable_base.decimal) if request.taxable_base is not None else None,
                acquisition_cost=request.acquisition_cost.to_domain() if request.acquisition_cost is not None else None,
            )
        except (ValidationError, InventoryLedgerError):
            return await _record_precommit_validation_refusal(
                context,
                operation_id="movement.add",
                profile_id=profile_id,
                request=request,
            )

        def add_movement() -> InventoryLedgerResult:
            with validating_governed_facts(context.authority_operation):
                return self._service(profile_id).movement_add(
                    bucket_id=profile,
                    actividad_id=request.actividad_id,
                    year=request.year,
                    movement=movement,
                    actor="runtime",
                )

        return await self._mutate(
            context,
            operation_id="movement.add",
            profile_id=profile_id,
            request=request,
            work=add_movement,
        )

    async def _execute_valuation_preview(
        self,
        *,
        request: InventoryValuationPreviewRequest,
        context: OperationExecutorContext,
        profile_id: UUID,
        profile: str,
    ) -> str | OperationRefusalEvidence:
        def preview() -> InventoryValuationPreviewResult:
            return self._service(profile_id).valuation_preview(
                bucket_id=profile,
                actividad_id=request.actividad_id,
                year=request.year,
                actor="runtime",
            )

        return await self._mutate(
            context,
            operation_id="valuation.preview",
            profile_id=profile_id,
            request=request,
            work=preview,
        )

    async def _execute_closing_authority_record(
        self,
        *,
        request: InventoryClosingAuthorityRecordRequest,
        context: OperationExecutorContext,
        profile_id: UUID,
        profile: str,
    ) -> str | OperationRefusalEvidence:
        try:
            authority_record = request.authority_record.to_domain()
        except (ValidationError, InventoryLedgerError):
            return await _record_precommit_validation_refusal(
                context,
                operation_id="closing-authority.record",
                profile_id=profile_id,
                request=request,
            )

        def record_closing_authority() -> InventoryLedgerResult:
            return self._service(profile_id).closing_authority_record(
                bucket_id=profile,
                actividad_id=request.actividad_id,
                year=request.year,
                authority_record=authority_record,
            )

        return await self._mutate(
            context,
            operation_id="closing-authority.record",
            profile_id=profile_id,
            request=request,
            work=record_closing_authority,
        )

    async def _mutate(
        self,
        context: OperationExecutorContext,
        *,
        operation_id: InventoryMutationOperationId,
        profile_id: UUID,
        request: BaseModel,
        work: Callable[[], object],
    ) -> str | OperationRefusalEvidence:
        """Hold cancellation ownership from UNKNOWN through actual commit receipt."""

        async def commit() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                try:
                    result = await asyncio.to_thread(work)
                except Exception as error:
                    refusal = _refusal_for_error(request=request, error=error)
                    if refusal is None:
                        raise
                    execution = InventoryOperationExecutionResult(
                        operation_id=operation_id,
                        outcome="refused",
                        profile_id=profile_id,
                        refusal=refusal,
                    )
                    detail_ref = await context.operands.put(execution, written_at=now())
                    await context.events.effect(OperationEffect.NONE)
                    return OperationRefusalEvidence(refusal_code=refusal.code, detail_ref=detail_ref)

                execution = _success_execution(operation_id=operation_id, profile_id=profile_id, result=result)
                await context.events.effect(_effect_for_success(execution))
                return await context.operands.put(execution, written_at=now())

        return await await_cancellation_complete(commit(), task_name=f"inventory-{operation_id}")


def _refusal_for_error(
    *,
    request: BaseModel,
    error: Exception,
) -> InventoryOperationRefusalDetail | None:
    identity = _refusal_identity_for_error(error)
    if identity is None:
        return None
    reason, code = identity
    return _request_refusal_detail(request, reason=reason, code=code)


def _refusal_identity_for_error(error: Exception) -> tuple[InventoryRefusalReason, InventoryRefusalCode] | None:
    reason: InventoryRefusalReason | None = None
    code: InventoryRefusalCode | None = None
    if isinstance(error, InventoryActividadConflictError):
        reason, code = "activity_conflict", INVENTORY_CONFLICT_REFUSAL_CODE
    elif isinstance(error, InventoryActividadNotFoundError):
        reason, code = "activity_not_found", INVENTORY_NOT_FOUND_REFUSAL_CODE
    elif isinstance(error, InventoryServiceInputError):
        return _service_input_refusal_identity(error)
    if reason is None or code is None:
        return None
    return reason, code


def _service_input_refusal_identity(
    error: InventoryServiceInputError,
) -> tuple[InventoryRefusalReason, InventoryRefusalCode] | None:
    service_reason = _SERVICE_INPUT_REASONS.get(error.translated_message or "")
    if service_reason is None:
        return None
    reason = cast(InventoryRefusalReason, service_reason)
    code = (
        INVENTORY_VALIDATION_REFUSAL_CODE
        if service_reason == "inventory_validation"
        else INVENTORY_SERVICE_INPUT_REFUSAL_CODE
    )
    return reason, code


def _request_refusal_detail(
    request: BaseModel,
    *,
    reason: InventoryRefusalReason,
    code: InventoryRefusalCode,
) -> InventoryOperationRefusalDetail:
    actividad_id = getattr(request, "actividad_id", None)
    year = getattr(request, "year", None)
    movement_id = getattr(request, "movement_id", None)
    valuation_method = getattr(request, "valuation_method", None)
    return InventoryOperationRefusalDetail(
        code=code,
        reason=reason,
        actividad_id=actividad_id if isinstance(actividad_id, str) else None,
        year=year if isinstance(year, int) else None,
        movement_id=movement_id if isinstance(movement_id, str) else None,
        valuation_method=valuation_method if isinstance(valuation_method, str) else None,
    )


async def _record_precommit_validation_refusal(
    context: OperationExecutorContext,
    *,
    operation_id: InventoryOperationId,
    profile_id: UUID,
    request: BaseModel,
) -> OperationRefusalEvidence:
    """Persist a typed NONE-effect refusal after validation known to precede writes."""
    reason: InventoryRefusalReason = (
        "closing_authority_invalid" if operation_id == "closing-authority.record" else "inventory_validation"
    )
    refusal = InventoryOperationRefusalDetail(
        code=INVENTORY_VALIDATION_REFUSAL_CODE,
        reason=reason,
        actividad_id=getattr(request, "actividad_id", None),
        year=getattr(request, "year", None),
        movement_id=getattr(request, "movement_id", None),
    )

    async def persist_refusal() -> OperationRefusalEvidence:
        async with context.cancellation.irreversible_section():
            execution = InventoryOperationExecutionResult(
                operation_id=operation_id,
                outcome="refused",
                profile_id=profile_id,
                refusal=refusal,
            )
            detail_ref = await context.operands.put(execution, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return OperationRefusalEvidence(refusal_code=refusal.code, detail_ref=detail_ref)

    return await await_cancellation_complete(persist_refusal(), task_name=f"inventory-{operation_id}-refusal")


def _success_execution(
    *,
    operation_id: InventoryMutationOperationId,
    profile_id: UUID,
    result: object,
) -> InventoryOperationExecutionResult:
    if operation_id in {"create", "movement.add"} and isinstance(result, InventoryLedgerResult):
        return InventoryOperationExecutionResult(
            operation_id=operation_id,
            outcome="success",
            profile_id=profile_id,
            ledger_result=result,
        )
    if operation_id == "valuation.preview" and isinstance(result, InventoryValuationPreviewResult):
        return InventoryOperationExecutionResult(
            operation_id=operation_id,
            outcome="success",
            profile_id=profile_id,
            valuation_result=result,
        )
    if operation_id == "closing-authority.record" and isinstance(result, InventoryLedgerResult):
        return InventoryOperationExecutionResult(
            operation_id=operation_id,
            outcome="success",
            profile_id=profile_id,
            ledger_result=result,
            closing_changed=result.changed,
        )
    raise TypeError("inventory service returned an incompatible canonical result")


def _effect_for_success(result: InventoryOperationExecutionResult) -> OperationEffect:
    if result.operation_id == "list":
        return OperationEffect.NONE
    if result.operation_id == "closing-authority.record":
        return OperationEffect.UPDATED if result.closing_changed else OperationEffect.NONE
    if result.operation_id == "valuation.preview":
        if result.valuation_result is None:
            raise ValueError("inventory valuation result is missing")
        return OperationEffect.UPDATED if result.valuation_result.bucket_event_ids else OperationEffect.NONE
    if result.ledger_result is None:
        raise ValueError("inventory ledger result is missing")
    return OperationEffect.UPDATED if result.ledger_result.bucket_event_ids else OperationEffect.NONE


__all__ = ["InventoryOperationExecutor"]
