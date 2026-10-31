"""Profile-bound registered operations for the canonical inventory service."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from decimal import Decimal
from typing import TYPE_CHECKING, Protocol, cast, get_args
from uuid import UUID

from pydantic import BaseModel, ValidationError

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.async_cleanup import await_cancellation_complete
from ...core.errors.hierarchy import CadrumoError
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.contribuyente.inventory.closing_foundations import InventoryLedgerError
from ...domain.contribuyente.inventory.corrections import (
    INVENTORY_CORRECTION_REFUSAL_REASONS,
    inventory_refusal_key,
    is_inventory_correction_refusal_reason,
)
from ..operations.execution_actor import OperationExecutionCallerReader, execution_actor_label
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.refusal_evidence import OperationRefusalEvidence
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
    INVENTORY_CLOSING_VALUE_RECORD_OPERATION_DEFINITION_ID,
    INVENTORY_CONFLICT_REFUSAL_CODE,
    INVENTORY_CORRECT_OPERATION_DEFINITION_ID,
    INVENTORY_CREATE_OPERATION_DEFINITION_ID,
    INVENTORY_DESCRIBE_OPERATION_DEFINITION_ID,
    INVENTORY_INSPECT_OPERATION_DEFINITION_ID,
    INVENTORY_LIST_OPERATION_DEFINITION_ID,
    INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID,
    INVENTORY_MOVEMENT_CORRECT_OPERATION_DEFINITION_ID,
    INVENTORY_MOVEMENT_REVERSE_OPERATION_DEFINITION_ID,
    INVENTORY_NOT_FOUND_REFUSAL_CODE,
    INVENTORY_RESTORE_OPERATION_DEFINITION_ID,
    INVENTORY_RETIRE_OPERATION_DEFINITION_ID,
    INVENTORY_SERVICE_INPUT_REFUSAL_CODE,
    INVENTORY_VALIDATION_REFUSAL_CODE,
    INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID,
    InventoryClosingAuthorityRecordRequest,
    InventoryClosingValueRecordRequest,
    InventoryCorrectRequest,
    InventoryCreateRequest,
    InventoryDescribeRequest,
    InventoryInspectRequest,
    InventoryLedgerChangeOperationId,
    InventoryListRequest,
    InventoryMovementAddRequest,
    InventoryMovementCorrectRequest,
    InventoryMovementReverseRequest,
    InventoryMutationOperationId,
    InventoryOperationId,
    InventoryRefusalCode,
    InventoryRefusalReason,
    InventoryRestoreRequest,
    InventoryRetireRequest,
    InventoryValuationPreviewRequest,
)
from .registered_specs import INVENTORY_OPERATION_SHAPES


class _InventoryProfileScopedRequest(Protocol):
    profile_id: UUID


_SERVICE_INPUT_REASONS: dict[str, InventoryRefusalReason] = {
    "application.inventory.service.errors.invalid_valuation_method": "invalid_valuation_method",
    "application.inventory.service.errors.duplicate_movement_id": "duplicate_movement_id",
    "application.inventory.service.errors.closing_authority_conflict": "closing_authority_conflict",
    "errors.refused.refused_profile_inventory_validation": "inventory_validation",
    inventory_refusal_key("closing_authority_invalid"): "closing_authority_invalid",
    inventory_refusal_key("prior_closing_document_needed"): "prior_closing_document_needed",
    **{
        inventory_refusal_key(reason): reason
        for reason in INVENTORY_CORRECTION_REFUSAL_REASONS
        if is_inventory_correction_refusal_reason(reason)
    },
}

_LEDGER_CHANGE_OPERATION_IDS: dict[str, InventoryLedgerChangeOperationId] = {
    INVENTORY_DESCRIBE_OPERATION_DEFINITION_ID: "describe",
    INVENTORY_CORRECT_OPERATION_DEFINITION_ID: "correct",
    INVENTORY_MOVEMENT_CORRECT_OPERATION_DEFINITION_ID: "movement.correct",
    INVENTORY_MOVEMENT_REVERSE_OPERATION_DEFINITION_ID: "movement.reverse",
    INVENTORY_RETIRE_OPERATION_DEFINITION_ID: "retire",
    INVENTORY_RESTORE_OPERATION_DEFINITION_ID: "restore",
}


_RUNTIME_ACTOR = "runtime"


class InventoryOperationExecutor:
    """Run one inventory service call under the supervisor's profile custody."""

    def __init__(
        self,
        ports_factory: InventoryServicePortsFactory,
        *,
        definition_id: str,
        execution_caller_reader: OperationExecutionCallerReader | None = None,
    ) -> None:
        """Bind the exact operation type to the bucket service factory."""
        self._ports_factory = ports_factory
        self._definition_id = definition_id
        self._execution_caller_reader = execution_caller_reader

    def _recorded_actor(self, context: OperationExecutorContext) -> str:
        """Name the session of an automation, and the runtime for the person's frontends."""
        return execution_actor_label(self._execution_caller_reader, context, supplied=_RUNTIME_ACTOR)

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
        # Cast rationale: exact registered request class was checked above; every inventory request carries
        # profile_id.
        profile_id = cast(  # nosemgrep: no-cast-in-domain-application
            _InventoryProfileScopedRequest, payload
        ).profile_id
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
        if self._definition_id == INVENTORY_INSPECT_OPERATION_DEFINITION_ID:
            inspect_request = _require_request(payload, InventoryInspectRequest)
            return await self._execute_inspect(
                request=inspect_request, context=context, profile_id=profile_id, profile=profile
            )
        if self._definition_id in _LEDGER_CHANGE_OPERATION_IDS:
            return await self._execute_ledger_change(
                request=payload,
                context=context,
                profile_id=profile_id,
                profile=profile,
            )
        if self._definition_id == INVENTORY_LIST_OPERATION_DEFINITION_ID:
            _require_request(payload, InventoryListRequest)
            return await self._execute_list(context=context, profile_id=profile_id, profile=profile)
        if self._definition_id == INVENTORY_CREATE_OPERATION_DEFINITION_ID:
            create_request = _require_request(payload, InventoryCreateRequest)
            return await self._execute_create(
                request=create_request,
                context=context,
                profile_id=profile_id,
                profile=profile,
            )
        if self._definition_id == INVENTORY_MOVEMENT_ADD_OPERATION_DEFINITION_ID:
            movement_request = _require_request(payload, InventoryMovementAddRequest)
            return await self._execute_movement_add(
                request=movement_request,
                context=context,
                profile_id=profile_id,
                profile=profile,
            )
        if self._definition_id == INVENTORY_VALUATION_PREVIEW_OPERATION_DEFINITION_ID:
            preview_request = _require_request(payload, InventoryValuationPreviewRequest)
            return await self._execute_valuation_preview(
                request=preview_request,
                context=context,
                profile_id=profile_id,
                profile=profile,
            )
        if self._definition_id == INVENTORY_CLOSING_VALUE_RECORD_OPERATION_DEFINITION_ID:
            closing_value_request = _require_request(payload, InventoryClosingValueRecordRequest)
            return await self._execute_closing_value_record(
                request=closing_value_request,
                context=context,
                profile_id=profile_id,
                profile=profile,
            )
        closing_request = _require_request(payload, InventoryClosingAuthorityRecordRequest)
        return await self._execute_closing_authority_record(
            request=closing_request,
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

    async def _execute_inspect(
        self,
        *,
        request: InventoryInspectRequest,
        context: OperationExecutorContext,
        profile_id: UUID,
        profile: str,
    ) -> str | OperationRefusalEvidence:
        async def read() -> str | OperationRefusalEvidence:
            try:
                service = self._service(profile_id)
                ledger = await asyncio.to_thread(
                    lambda: service.show(
                        bucket_id=profile,
                        actividad_id=request.actividad_id,
                        year=request.year,
                    )
                )
            except InventoryActividadNotFoundError as error:
                refusal = _refusal_for_error(request=request, error=error)
                if refusal is None:
                    raise
                execution = InventoryOperationExecutionResult(
                    operation_id="inspect",
                    outcome="refused",
                    profile_id=profile_id,
                    refusal=refusal,
                )
                detail_ref = await context.operands.put(execution, written_at=now())
                await context.events.effect(OperationEffect.NONE)
                return OperationRefusalEvidence(refusal_code=refusal.code, detail_ref=detail_ref)
            file_names = await asyncio.to_thread(service.document_file_names, ledger)
            result = InventoryOperationExecutionResult(
                operation_id="inspect",
                outcome="success",
                profile_id=profile_id,
                ledger_result=InventoryLedgerResult(ledger=ledger, changed=False, document_file_names=file_names),
            )
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(read(), task_name="inventory-inspect")

    async def _execute_ledger_change(
        self,
        *,
        request: BaseModel,
        context: OperationExecutorContext,
        profile_id: UUID,
        profile: str,
    ) -> str | OperationRefusalEvidence:
        operation_id = _LEDGER_CHANGE_OPERATION_IDS[self._definition_id]
        try:
            work = _ledger_change_work(
                request,
                service=self._service(profile_id),
                profile=profile,
                actor=self._recorded_actor(context),
            )
        except (ValidationError, InventoryLedgerError):
            return await _record_precommit_validation_refusal(
                context,
                operation_id=operation_id,
                profile_id=profile_id,
                request=request,
            )

        def apply_change() -> InventoryLedgerResult:
            # An omitted movement IVA rate resolves through the pinned authority.
            with validating_governed_facts(context.authority_operation):
                return work()

        return await self._mutate(
            context,
            operation_id=operation_id,
            profile_id=profile_id,
            request=request,
            work=apply_change,
        )

    async def _execute_create(
        self,
        *,
        request: InventoryCreateRequest,
        context: OperationExecutorContext,
        profile_id: UUID,
        profile: str,
    ) -> str | OperationRefusalEvidence:
        actor = self._recorded_actor(context)

        def create() -> InventoryLedgerResult:
            return self._service(profile_id).create(
                bucket_id=profile,
                actividad_id=request.actividad_id,
                year=request.year,
                valuation_method=request.valuation_method,
                opening_stock=Decimal(request.opening_stock.decimal),
                actor=actor,
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
            movement = _movement_command(request)
        except (ValidationError, InventoryLedgerError):
            return await _record_precommit_validation_refusal(
                context,
                operation_id="movement.add",
                profile_id=profile_id,
                request=request,
            )

        actor = self._recorded_actor(context)

        def add_movement() -> InventoryLedgerResult:
            with validating_governed_facts(context.authority_operation):
                return self._service(profile_id).movement_add(
                    bucket_id=profile,
                    actividad_id=request.actividad_id,
                    year=request.year,
                    movement=movement,
                    actor=actor,
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
        actor = self._recorded_actor(context)

        def preview() -> InventoryValuationPreviewResult:
            return self._service(profile_id).valuation_preview(
                bucket_id=profile,
                actividad_id=request.actividad_id,
                year=request.year,
                actor=actor,
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
        actor = execution_actor_label(
            self._execution_caller_reader, context, supplied=request.authority_record.decision.actor
        )
        try:
            authority_record = request.authority_record.to_domain(actor=actor)
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

    async def _execute_closing_value_record(
        self,
        *,
        request: InventoryClosingValueRecordRequest,
        context: OperationExecutorContext,
        profile_id: UUID,
        profile: str,
    ) -> str | OperationRefusalEvidence:
        actor = self._recorded_actor(context)

        def record_closing_value() -> InventoryLedgerResult:
            return self._service(profile_id).closing_value_record(
                bucket_id=profile,
                facts=request.facts.to_domain(actividad_id=request.actividad_id, year=request.year),
                actor=actor,
                source_command=INVENTORY_CLOSING_VALUE_RECORD_OPERATION_DEFINITION_ID,
            )

        return await self._mutate(
            context,
            operation_id="closing-value.record",
            profile_id=profile_id,
            request=request,
            work=record_closing_value,
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


def _require_request[Request: BaseModel](payload: BaseModel, expected: type[Request]) -> Request:
    if not isinstance(payload, expected):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return payload


def _ledger_change_work(
    request: BaseModel,
    *,
    service: InventoryService,
    profile: str,
    actor: str,
) -> Callable[[], InventoryLedgerResult]:
    """Bind one change request to its service verb; a malformed movement raises before any write."""
    if isinstance(request, InventoryDescribeRequest):
        return lambda: service.describe(
            bucket_id=profile,
            actividad_id=request.actividad_id,
            year=request.year,
            correction_id=request.correction_id,
            label=request.label,
            description=request.description,
            actor=actor,
        )
    if isinstance(request, InventoryCorrectRequest):
        opening_stock = Decimal(request.opening_stock.decimal) if request.opening_stock is not None else None
        return lambda: service.correct_opening(
            bucket_id=profile,
            actividad_id=request.actividad_id,
            year=request.year,
            correction_id=request.correction_id,
            reason=request.reason,
            opening_stock=opening_stock,
            valuation_method=request.valuation_method,
            actor=actor,
        )
    if isinstance(request, InventoryMovementCorrectRequest):
        replacement = _movement_command(request)
        return lambda: service.movement_correct(
            bucket_id=profile,
            actividad_id=request.actividad_id,
            year=request.year,
            correction_id=request.correction_id,
            target_movement_id=request.target_movement_id,
            replacement=replacement,
            reason=request.reason,
            actor=actor,
        )
    if isinstance(request, InventoryMovementReverseRequest):
        return lambda: service.movement_reverse(
            bucket_id=profile,
            actividad_id=request.actividad_id,
            year=request.year,
            correction_id=request.correction_id,
            target_movement_id=request.target_movement_id,
            reason=request.reason,
            actor=actor,
        )
    if isinstance(request, InventoryRetireRequest):
        return lambda: service.retire(
            bucket_id=profile,
            actividad_id=request.actividad_id,
            year=request.year,
            correction_id=request.correction_id,
            reason=request.reason,
            actor=actor,
        )
    if isinstance(request, InventoryRestoreRequest):
        return lambda: service.restore(
            bucket_id=profile,
            actividad_id=request.actividad_id,
            year=request.year,
            correction_id=request.correction_id,
            actor=actor,
        )
    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


def _movement_command(
    request: InventoryMovementAddRequest | InventoryMovementCorrectRequest,
) -> InventoryMovementCommand:
    return InventoryMovementCommand(
        movement_id=request.movement_id,
        movement_date=request.movement_date,
        kind=request.kind,
        quantity=Decimal(request.quantity.decimal),
        unit_cost=Decimal(request.unit_cost.decimal) if request.unit_cost is not None else None,
        taxable_base=Decimal(request.taxable_base.decimal) if request.taxable_base is not None else None,
        acquisition_cost=request.acquisition_cost.to_domain() if request.acquisition_cost is not None else None,
    )


def _refusal_for_error(
    *,
    request: BaseModel,
    error: Exception,
) -> InventoryOperationRefusalDetail | None:
    identity = _refusal_identity_for_error(error)
    if identity is None:
        return None
    reason, code = identity
    detail = _request_refusal_detail(request, reason=reason, code=code)
    if not isinstance(error, CadrumoError):
        return detail
    return detail.model_copy(
        update={"reason_facts": {key: str(value) for key, value in (error.context or {}).items()}},
    )


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
    reason = service_reason
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
        reason_key=inventory_refusal_key(reason),
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
        "closing_authority_invalid"
        if operation_id in {"closing-authority.record", "closing-value.record"}
        else "inventory_validation"
    )
    refusal = InventoryOperationRefusalDetail(
        code=INVENTORY_VALIDATION_REFUSAL_CODE,
        reason=reason,
        actividad_id=getattr(request, "actividad_id", None),
        year=getattr(request, "year", None),
        movement_id=getattr(request, "movement_id", None),
        reason_key=inventory_refusal_key(reason),
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
    if (operation_id in {"create", "movement.add"} or operation_id in get_args(InventoryLedgerChangeOperationId)) and (
        isinstance(result, InventoryLedgerResult)
    ):
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
    if operation_id in {"closing-authority.record", "closing-value.record"} and isinstance(
        result, InventoryLedgerResult
    ):
        return InventoryOperationExecutionResult(
            operation_id=operation_id,
            outcome="success",
            profile_id=profile_id,
            ledger_result=result,
            closing_changed=result.changed,
        )
    raise TypeError("inventory service returned an incompatible canonical result")


def _effect_for_success(result: InventoryOperationExecutionResult) -> OperationEffect:
    if result.operation_id in {"list", "inspect"}:
        return OperationEffect.NONE
    if result.operation_id in {"closing-authority.record", "closing-value.record"}:
        return OperationEffect.UPDATED if (result.closing_changed is True) else OperationEffect.NONE
    if result.operation_id == "valuation.preview":
        if result.valuation_result is None:
            raise ValueError("inventory valuation result is missing")
        return OperationEffect.UPDATED if result.valuation_result.bucket_event_ids else OperationEffect.NONE
    if result.ledger_result is None:
        raise ValueError("inventory ledger result is missing")
    return OperationEffect.UPDATED if result.ledger_result.bucket_event_ids else OperationEffect.NONE


__all__ = ["InventoryOperationExecutor"]
