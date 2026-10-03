"""Exact-profile execution and write custody for Modelo 145 operations."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable
from dataclasses import replace
from typing import Protocol, override, runtime_checkable
from uuid import UUID

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.errors.error_codes import scrub_error_context
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.secure_object_write import SecureObjectWrite
from ...core.time.clock import now
from ...domain.buckets.event import BucketEventHistoryCatalogue
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from ._ports import FicheroBoeRecordRenderer
from .m145_communication_contracts import (
    M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID,
    M145_COMMUNICATION_OPERATION_IDS,
    M145_COMMUNICATION_RECORD_NOT_FOUND_REFUSAL_CODE,
    M145_COMMUNICATION_REFUSAL_CODE_BY_VALUE,
    M145_COMMUNICATION_REFUSAL_CODES_BY_OPERATION,
    M145_COMMUNICATION_REQUEST_TYPES,
    M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID,
    M145CommunicationCreateRequest,
    M145CommunicationErrorContextFact,
    M145CommunicationExecutionResult,
    M145CommunicationExportProjection,
    M145CommunicationExportRequest,
    M145CommunicationMarkCompletedRequest,
    M145CommunicationMarkDeliveredRequest,
    M145CommunicationOperationId,
    M145CommunicationOperationRecordNotFoundError,
    M145CommunicationOperationResult,
    M145CommunicationOutputProjection,
    M145CommunicationRecordProjection,
    M145CommunicationRefusalProjection,
    M145CommunicationRequest,
    M145CommunicationValidateRequest,
    M145CommunicationValidationProjection,
    require_m145_communication_projection_kind,
)
from .m145_communication_records import (
    M145CommunicationExportResult,
    M145CommunicationRecord,
    M145CommunicationRecordAmbiguousError,
    M145CommunicationRecordExportError,
    M145CommunicationRecordNotFoundError,
    M145CommunicationRecordTransitionError,
    M145CommunicationRecordValidationError,
    M145CommunicationServiceError,
    M145CommunicationValidationResult,
    create_m145_communication_record,
    export_m145_communication_record,
    mark_m145_communication_record_delivered_to_payer,
    mark_m145_communication_record_locally_completed,
    validate_m145_communication_record,
)
from .m145_communication_records_ports import (
    M145CommunicationRecordRepositoryPort,
    M145CommunicationRecordsPorts,
    M145CommunicationRecordsPortsFactory,
)


class _WriteGate:
    """Bridge a synchronous canonical repository call to the async effect fence."""

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        self.requested = asyncio.Event()
        self.finished = asyncio.Event()
        self._released = threading.Event()
        self._allowed = False
        self.started = False
        self.succeeded = False

    def enter[T](self, commit: Callable[[], T]) -> T:
        """Wait for the worker to publish UNKNOWN, then execute the repository call."""
        self.started = True
        self._loop.call_soon_threadsafe(self.requested.set)
        self._released.wait()
        if not self._allowed:
            self._loop.call_soon_threadsafe(self.finished.set)
            raise RuntimeError("M145 repository mutation was not admitted by its operation fence")
        try:
            result = commit()
        except BaseException:
            self._loop.call_soon_threadsafe(self.finished.set)
            raise
        self.succeeded = True
        self._loop.call_soon_threadsafe(self.finished.set)
        return result

    def allow(self) -> None:
        self._allowed = True
        self._released.set()

    def deny(self) -> None:
        self._released.set()

    @property
    def released(self) -> bool:
        return self._released.is_set()


class _TrackedM145RecordRepository(M145CommunicationRecordRepositoryPort):
    """Observe only the record/event atomic save; leave reads and write prep outside."""

    def __init__(self, repository: M145CommunicationRecordRepositoryPort, gate: _WriteGate) -> None:
        self._repository = repository
        self._gate = gate

    @override
    def exists(self, communication_record_id: str) -> bool:
        return self._repository.exists(communication_record_id)

    @override
    def load(self, communication_record_id: str) -> M145CommunicationRecord:
        return self._repository.load(communication_record_id)

    @override
    def resolve(self, communication_record_id: str) -> M145CommunicationRecord:
        return self._repository.resolve(communication_record_id)

    @override
    def save_with_secure_object_writes(
        self,
        record: M145CommunicationRecord,
        extra_writes: tuple[SecureObjectWrite, ...],
    ) -> None:
        self._gate.enter(lambda: self._repository.save_with_secure_object_writes(record, extra_writes))


@runtime_checkable
class _RevisionGuardedM145EventAppender(Protocol):
    def append_guarded(
        self,
        appender: Callable[[BucketEventHistoryCatalogue], BucketEventHistoryCatalogue],
        *,
        attempts: int = 4,
    ) -> BucketEventHistoryCatalogue: ...


class _TrackedM145EventRepository(BucketEventHistoryRepositoryProtocol):
    """Fence the standalone export receipt append after canonical rendering."""

    def __init__(self, repository: BucketEventHistoryRepositoryProtocol, gate: _WriteGate) -> None:
        self._repository = repository
        self._gate = gate

    @override
    def exists(self) -> bool:
        return self._repository.exists()

    @override
    def load(self) -> BucketEventHistoryCatalogue:
        return self._repository.load()

    @override
    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        self._gate.enter(lambda: self._repository.save(catalogue))

    def append_guarded(
        self,
        appender: Callable[[BucketEventHistoryCatalogue], BucketEventHistoryCatalogue],
        *,
        attempts: int = 4,
    ) -> BucketEventHistoryCatalogue:
        repository = self._repository
        if not isinstance(repository, _RevisionGuardedM145EventAppender):
            raise RuntimeError("M145 export requires a revision-guarded event-history repository")
        return self._gate.enter(lambda: repository.append_guarded(appender, attempts=attempts))

    @override
    def to_secure_object_write(
        self,
        catalogue: BucketEventHistoryCatalogue,
        *,
        expected_revision_id: str | None = None,
    ) -> SecureObjectWrite:
        return self._repository.to_secure_object_write(catalogue, expected_revision_id=expected_revision_id)


class M145CommunicationExecutor:
    """Delegate one command to the canonical M145 service under exact-profile authority."""

    def __init__(
        self,
        *,
        records_ports_factory: M145CommunicationRecordsPortsFactory,
        renderer_factory: Callable[[], FicheroBoeRecordRenderer],
    ) -> None:
        """Bind the canonical repository and renderer capabilities."""
        self._records_ports_factory = records_ports_factory
        self._renderer_factory = renderer_factory

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Execute one exact-profile M145 command with a fenced write."""
        payload, operation_id = self._validated_request(request, context)
        if request.subject_ref != profile_operation_subject(str(payload.profile_id)):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        bucket_id = str(payload.profile_id)
        if await asyncio.to_thread(require_active_bucket_id) != bucket_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        operation = context.authority_operation
        await context.events.phase(operation_id)
        ports = await asyncio.to_thread(self._records_ports_factory, bucket_id=bucket_id)
        return await await_cancellation_complete(
            self._run_with_write_gate(
                payload=payload,
                operation_id=operation_id,
                bucket_id=bucket_id,
                ports=ports,
                authority=operation,
                context=context,
            ),
            task_name=operation_id,
        )

    @staticmethod
    def _validated_request(
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> tuple[M145CommunicationRequest, M145CommunicationOperationId]:
        payload = request.payload
        operation_id = request.definition_id
        if (
            operation_id not in M145_COMMUNICATION_OPERATION_IDS
            or context.identity.definition_id != operation_id
            or context.identity.subject_ref != request.subject_ref
            or not isinstance(
                payload,
                (
                    M145CommunicationCreateRequest,
                    M145CommunicationValidateRequest,
                    M145CommunicationExportRequest,
                    M145CommunicationMarkDeliveredRequest,
                    M145CommunicationMarkCompletedRequest,
                ),
            )
            or not isinstance(payload, M145_COMMUNICATION_REQUEST_TYPES[operation_id])
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return payload, operation_id

    async def _run_with_write_gate(
        self,
        *,
        payload: M145CommunicationRequest,
        operation_id: M145CommunicationOperationId,
        bucket_id: str,
        ports: M145CommunicationRecordsPorts,
        authority: PinnedAuthorityOperation,
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        gate = _WriteGate(asyncio.get_running_loop())
        tracked_ports = self._tracked_ports(ports, operation_id=operation_id, gate=gate)
        service_task = asyncio.create_task(
            asyncio.to_thread(
                self._invoke,
                payload=payload,
                operation_id=operation_id,
                bucket_id=bucket_id,
                ports=tracked_ports,
                authority=authority,
            ),
            name=f"{operation_id}-canonical-service",
        )
        request_task = asyncio.create_task(gate.requested.wait(), name=f"{operation_id}-write-request")
        try:
            completed, _ = await asyncio.wait(
                (service_task, request_task),
                return_when=asyncio.FIRST_COMPLETED,
            )
            if service_task in completed:
                request_task.cancel()
                return await self._finish_service_first(
                    service_task,
                    gate=gate,
                    payload=payload,
                    operation_id=operation_id,
                    context=context,
                )
            return await self._finish_write_first(
                service_task,
                gate=gate,
                payload=payload,
                operation_id=operation_id,
                context=context,
            )
        finally:
            if not gate.released:
                gate.deny()
            if not request_task.done():
                request_task.cancel()
            if not service_task.done():
                await asyncio.gather(service_task, return_exceptions=True)

    async def _finish_service_first(
        self,
        service_task: asyncio.Task[
            M145CommunicationRecord | M145CommunicationValidationResult | M145CommunicationExportResult
        ],
        *,
        gate: _WriteGate,
        payload: M145CommunicationRequest,
        operation_id: M145CommunicationOperationId,
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        try:
            value = await service_task
        except _CANONICAL_REFUSAL_TYPES as error:
            if gate.started:
                raise
            return await self._publish_refusal(
                context,
                profile_id=payload.profile_id,
                operation_id=operation_id,
                error=error,
            )
        except BaseException:
            if not gate.started:
                await context.events.effect(OperationEffect.NONE)
            raise
        await context.events.effect(OperationEffect.NONE)
        return await self._publish_success(
            context,
            profile_id=payload.profile_id,
            operation_id=operation_id,
            value=value,
            effect=OperationEffect.NONE,
        )

    async def _finish_write_first(
        self,
        service_task: asyncio.Task[
            M145CommunicationRecord | M145CommunicationValidationResult | M145CommunicationExportResult
        ],
        *,
        gate: _WriteGate,
        payload: M145CommunicationRequest,
        operation_id: M145CommunicationOperationId,
        context: OperationExecutorContext,
    ) -> str:
        async with context.cancellation.irreversible_section():
            await context.events.effect(OperationEffect.UNKNOWN)
            gate.allow()
            await gate.finished.wait()
            if gate.succeeded:
                await context.events.effect(OperationEffect.UPDATED)
            value = await service_task
            effect = OperationEffect.UPDATED if gate.succeeded else OperationEffect.UNKNOWN
        return await self._publish_success(
            context,
            profile_id=payload.profile_id,
            operation_id=operation_id,
            value=value,
            effect=effect,
        )

    def _tracked_ports(
        self,
        ports: M145CommunicationRecordsPorts,
        *,
        operation_id: M145CommunicationOperationId,
        gate: _WriteGate,
    ) -> M145CommunicationRecordsPorts:
        if operation_id == M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID:
            return replace(
                ports, bucket_event_repository=_TrackedM145EventRepository(ports.bucket_event_repository, gate)
            )
        if operation_id in {
            M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID,
            M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID,
            M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID,
        }:
            return replace(ports, record_repository=_TrackedM145RecordRepository(ports.record_repository, gate))
        return ports

    def _invoke(
        self,
        *,
        payload: BaseModel,
        operation_id: M145CommunicationOperationId,
        bucket_id: str,
        ports: M145CommunicationRecordsPorts,
        authority: PinnedAuthorityOperation,
    ) -> M145CommunicationRecord | M145CommunicationValidationResult | M145CommunicationExportResult:
        handlers = {
            M145_COMMUNICATION_CREATE_OPERATION_DEFINITION_ID: self._invoke_create,
            M145_COMMUNICATION_VALIDATE_OPERATION_DEFINITION_ID: self._invoke_validate,
            M145_COMMUNICATION_EXPORT_OPERATION_DEFINITION_ID: self._invoke_export,
            M145_COMMUNICATION_MARK_DELIVERED_OPERATION_DEFINITION_ID: self._invoke_mark_delivered,
            M145_COMMUNICATION_MARK_COMPLETED_OPERATION_DEFINITION_ID: self._invoke_mark_completed,
        }
        handler = handlers.get(operation_id)
        if handler is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return handler(payload, bucket_id, ports, authority)

    def _invoke_create(
        self,
        payload: BaseModel,
        bucket_id: str,
        ports: M145CommunicationRecordsPorts,
        authority: PinnedAuthorityOperation,
    ) -> M145CommunicationRecord:
        if not isinstance(payload, M145CommunicationCreateRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return create_m145_communication_record(
            payload.to_command(),
            bucket_id=bucket_id,
            ports=ports,
            operation=authority,
            actor=payload.actor,
        )

    @staticmethod
    def _invoke_validate(
        payload: BaseModel,
        bucket_id: str,
        ports: M145CommunicationRecordsPorts,
        authority: PinnedAuthorityOperation,
    ) -> M145CommunicationValidationResult:
        if not isinstance(payload, M145CommunicationValidateRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return validate_m145_communication_record(
            payload.communication_record_id,
            bucket_id=bucket_id,
            ports=ports,
            operation=authority,
        )

    def _invoke_export(
        self,
        payload: BaseModel,
        bucket_id: str,
        ports: M145CommunicationRecordsPorts,
        authority: PinnedAuthorityOperation,
    ) -> M145CommunicationExportResult:
        if not isinstance(payload, M145CommunicationExportRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return export_m145_communication_record(
            payload.communication_record_id,
            bucket_id=bucket_id,
            renderer=self._renderer_factory(),
            ports=ports,
            operation=authority,
            actor=payload.actor,
        )

    @staticmethod
    def _invoke_mark_delivered(
        payload: BaseModel,
        bucket_id: str,
        ports: M145CommunicationRecordsPorts,
        authority: PinnedAuthorityOperation,
    ) -> M145CommunicationRecord:
        if not isinstance(payload, M145CommunicationMarkDeliveredRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return mark_m145_communication_record_delivered_to_payer(
            payload.communication_record_id,
            bucket_id=bucket_id,
            ports=ports,
            operation=authority,
            actor=payload.actor,
        )

    @staticmethod
    def _invoke_mark_completed(
        payload: BaseModel,
        bucket_id: str,
        ports: M145CommunicationRecordsPorts,
        authority: PinnedAuthorityOperation,
    ) -> M145CommunicationRecord:
        if not isinstance(payload, M145CommunicationMarkCompletedRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        return mark_m145_communication_record_locally_completed(
            payload.communication_record_id,
            bucket_id=bucket_id,
            ports=ports,
            operation=authority,
            actor=payload.actor,
        )

    async def _publish_success(
        self,
        context: OperationExecutorContext,
        *,
        profile_id: UUID,
        operation_id: M145CommunicationOperationId,
        value: M145CommunicationRecord | M145CommunicationValidationResult | M145CommunicationExportResult,
        effect: OperationEffect,
    ) -> str:
        if isinstance(value, M145CommunicationRecord):
            projected: M145CommunicationOutputProjection = M145CommunicationRecordProjection.from_record(value)
        elif isinstance(value, M145CommunicationValidationResult):
            projected = M145CommunicationValidationProjection.from_result(value)
        else:
            projected = M145CommunicationExportProjection.from_result(value)
        require_m145_communication_projection_kind(operation_id, projected)
        result = M145CommunicationOperationResult(
            profile_id=profile_id,
            operation_id=operation_id,
            outcome="completed",
            effect=effect,
            result=projected,
        )
        detail = M145CommunicationExecutionResult(result=result)
        reference = await context.operands.put(detail, written_at=now())
        return reference

    async def _publish_refusal(
        self,
        context: OperationExecutorContext,
        *,
        profile_id: UUID,
        operation_id: M145CommunicationOperationId,
        error: M145CommunicationServiceError,
    ) -> OperationRefusalEvidence:
        if isinstance(error, M145CommunicationRecordNotFoundError):
            operation_error = M145CommunicationOperationRecordNotFoundError(
                str(error),
                context=error.context,
            )
            refusal_code = M145_COMMUNICATION_RECORD_NOT_FOUND_REFUSAL_CODE
        else:
            operation_error = error
            refusal_code = error.code.code
        typed_refusal_code = M145_COMMUNICATION_REFUSAL_CODE_BY_VALUE.get(refusal_code)
        if (
            typed_refusal_code is None
            or typed_refusal_code not in M145_COMMUNICATION_REFUSAL_CODES_BY_OPERATION[operation_id]
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE) from None
        safe_context = scrub_error_context(operation_error.context) or {}
        refusal = M145CommunicationRefusalProjection(
            code=typed_refusal_code,
            message=str(operation_error) or operation_error.translated_message or operation_error.code.message_key,
            context=tuple(
                M145CommunicationErrorContextFact(key=key, value=value) for key, value in safe_context.items()
            ),
        )
        result = M145CommunicationOperationResult(
            profile_id=profile_id,
            operation_id=operation_id,
            outcome="prewrite_refusal",
            effect=OperationEffect.NONE,
            refusal=refusal,
        )
        reference = await context.operands.put(M145CommunicationExecutionResult(result=result), written_at=now())
        await context.events.effect(OperationEffect.NONE)
        return OperationRefusalEvidence(refusal_code=refusal_code, detail_ref=reference)


_CANONICAL_REFUSAL_TYPES = (
    M145CommunicationRecordNotFoundError,
    M145CommunicationRecordAmbiguousError,
    M145CommunicationRecordValidationError,
    M145CommunicationRecordExportError,
    M145CommunicationRecordTransitionError,
)

__all__ = ["M145CommunicationExecutor"]
