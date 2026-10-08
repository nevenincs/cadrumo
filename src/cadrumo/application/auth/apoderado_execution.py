"""Exact-profile apoderado service execution under worker custody."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Protocol, cast
from uuid import UUID

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.config import Settings
from ...core.operations import (
    OperationEffect,
)
from ...core.time.clock import now
from ...domain.auth.apoderamientos.catalogue import UnknownScopeError
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_profile_operation_identity
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..user_profile.access_contracts import (
    AccessDenialCode,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .apoderado_contracts import (
    APODERADO_CHECK_OPERATION_DEFINITION_ID,
    APODERADO_CLEAR_OPERATION_DEFINITION_ID,
    APODERADO_CONFIGURE_OPERATION_DEFINITION_ID,
    APODERADO_STATUS_OPERATION_DEFINITION_ID,
    ApoderadoCheckRequest,
    ApoderadoClearRequest,
    ApoderadoConfigurationSnapshot,
    ApoderadoConfigureRequest,
    ApoderadoExecutionResult,
    ApoderadoOperationId,
    ApoderadoOperationProjection,
    ApoderadoOperationRequest,
    ApoderadoStatusRequest,
    ApoderadoStatusSnapshot,
)
from .apoderado_repository import ApoderadoConfigurationRepositoryFactory
from .apoderado_service import (
    ApoderadoLiveCheckUnavailableError,
    ApoderadoRepresentedNifInvalidError,
    ApoderadoService,
)


@dataclass(frozen=True, slots=True)
class ApoderadoOperationPorts:
    """Repository and catalogue inputs bound to one immutable profile and pin."""

    bucket_id: str
    operation: PinnedAuthorityOperation
    repository_factory: ApoderadoConfigurationRepositoryFactory
    settings: Settings


class ApoderadoOperationPortsFactory(Protocol):
    """Compose only the requested profile's canonical apoderado service ports."""

    def __call__(self, *, bucket_id: str, operation: PinnedAuthorityOperation) -> ApoderadoOperationPorts:
        """Return exact-profile ports without ambient profile selection."""
        ...


def _require_apoderado_request(
    request: OperationRequest[BaseModel],
) -> tuple[ApoderadoOperationId, ApoderadoOperationRequest]:
    request_types = {
        APODERADO_STATUS_OPERATION_DEFINITION_ID: ApoderadoStatusRequest,
        APODERADO_CONFIGURE_OPERATION_DEFINITION_ID: ApoderadoConfigureRequest,
        APODERADO_CLEAR_OPERATION_DEFINITION_ID: ApoderadoClearRequest,
        APODERADO_CHECK_OPERATION_DEFINITION_ID: ApoderadoCheckRequest,
    }
    operation_id = request.definition_id
    payload = request.payload
    if (
        not isinstance(
            payload, (ApoderadoStatusRequest, ApoderadoConfigureRequest, ApoderadoClearRequest, ApoderadoCheckRequest)
        )
        or operation_id not in request_types
        or type(payload) is not request_types[operation_id]
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return cast(ApoderadoOperationId, operation_id), payload


def _make_apoderado_service(
    factory: ApoderadoOperationPortsFactory, *, bucket_id: str, authority: PinnedAuthorityOperation
) -> ApoderadoService:
    if require_active_bucket_id() != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    ports = factory(bucket_id=bucket_id, operation=authority)
    if ports.bucket_id != bucket_id or ports.operation is not authority:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return ApoderadoService(repository_factory=ports.repository_factory, operation=authority, settings=ports.settings)


async def _publish_apoderado_projection(
    context: OperationExecutorContext, projection: ApoderadoOperationProjection
) -> str:
    reference = await context.operands.put(ApoderadoExecutionResult(projection=projection), written_at=now())
    await context.events.effect(projection.effect)
    return reference


async def _refuse_apoderado(
    context: OperationExecutorContext,
    *,
    profile_id: UUID,
    operation_id: ApoderadoOperationId,
    code: str,
) -> OperationRefusalEvidence:
    projection = ApoderadoOperationProjection(
        profile_id=profile_id,
        operation_id=operation_id,
        outcome="prewrite_refusal",
        effect=OperationEffect.NONE,
        refusal_code=code,
    )
    reference = await _publish_apoderado_projection(context, projection)
    return OperationRefusalEvidence(refusal_code=code, detail_ref=reference)


async def _run_apoderado_status(
    service: ApoderadoService,
    context: OperationExecutorContext,
    *,
    profile_id: UUID,
    operation_id: ApoderadoOperationId,
) -> str:
    status = await asyncio.to_thread(service.status, bucket_id=str(profile_id))
    return await _publish_apoderado_projection(
        context,
        ApoderadoOperationProjection(
            profile_id=profile_id,
            operation_id=operation_id,
            outcome="completed",
            effect=OperationEffect.NONE,
            status=ApoderadoStatusSnapshot.from_status(status),
        ),
    )


async def _run_apoderado_check(
    service: ApoderadoService,
    context: OperationExecutorContext,
    *,
    profile_id: UUID,
    operation_id: ApoderadoOperationId,
) -> OperationRefusalEvidence:
    try:
        await asyncio.to_thread(service.check, bucket_id=str(profile_id))
    except ApoderadoLiveCheckUnavailableError:
        return await _refuse_apoderado(
            context,
            profile_id=profile_id,
            operation_id=operation_id,
            code="REFUSED_APODERADO_LIVE_CHECK_UNAVAILABLE",
        )
    raise ValueError("apoderado live check returned without a verified live result")


async def _run_apoderado_configure(
    service: ApoderadoService,
    context: OperationExecutorContext,
    *,
    profile_id: UUID,
    operation_id: ApoderadoOperationId,
    payload: ApoderadoOperationRequest,
) -> str | OperationRefusalEvidence:
    if not isinstance(payload, ApoderadoConfigureRequest):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    async with context.ephemeral_secret.consume() as secret:
        try:
            represented_nif = bytes(secret).decode("utf-8")
        except UnicodeDecodeError:
            return await _refuse_apoderado(
                context,
                profile_id=profile_id,
                operation_id=operation_id,
                code="REFUSED_APODERADO_INVALID_REPRESENTED_NIF",
            )
        try:
            try:
                configuration = await asyncio.to_thread(
                    service.prepare_configuration,
                    bucket_id=str(profile_id),
                    represented_nif=represented_nif,
                    scope_tokens=payload.scope_tokens,
                    notes=payload.notes,
                )
            except ApoderadoRepresentedNifInvalidError:
                return await _refuse_apoderado(
                    context,
                    profile_id=profile_id,
                    operation_id=operation_id,
                    code="REFUSED_APODERADO_INVALID_REPRESENTED_NIF",
                )
            except UnknownScopeError:
                return await _refuse_apoderado(
                    context,
                    profile_id=profile_id,
                    operation_id=operation_id,
                    code="REFUSED_APODERADO_UNKNOWN_SCOPE",
                )
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                await asyncio.to_thread(service.persist_configuration, configuration)
                await context.events.effect(OperationEffect.UPDATED)
        finally:
            represented_nif = ""
    return await _publish_apoderado_projection(
        context,
        ApoderadoOperationProjection(
            profile_id=profile_id,
            operation_id=operation_id,
            outcome="completed",
            effect=OperationEffect.UPDATED,
            configuration=ApoderadoConfigurationSnapshot.from_configuration(configuration),
        ),
    )


async def _run_apoderado_clear(
    service: ApoderadoService,
    context: OperationExecutorContext,
    *,
    profile_id: UUID,
    operation_id: ApoderadoOperationId,
) -> str:
    async with context.cancellation.irreversible_section():
        await context.events.effect(OperationEffect.UNKNOWN)
        cleared = await asyncio.to_thread(service.clear, bucket_id=str(profile_id))
        effect = OperationEffect.UPDATED if cleared else OperationEffect.NONE
        await context.events.effect(effect)
    return await _publish_apoderado_projection(
        context,
        ApoderadoOperationProjection(
            profile_id=profile_id,
            operation_id=operation_id,
            outcome="completed",
            effect=effect,
            cleared=cleared,
        ),
    )


async def _run_apoderado_operation(
    service: ApoderadoService,
    context: OperationExecutorContext,
    *,
    profile_id: UUID,
    operation_id: ApoderadoOperationId,
    payload: ApoderadoOperationRequest,
) -> str | OperationRefusalEvidence:
    if operation_id == APODERADO_STATUS_OPERATION_DEFINITION_ID:
        return await _run_apoderado_status(service, context, profile_id=profile_id, operation_id=operation_id)
    if operation_id == APODERADO_CHECK_OPERATION_DEFINITION_ID:
        return await _run_apoderado_check(service, context, profile_id=profile_id, operation_id=operation_id)
    if operation_id == APODERADO_CONFIGURE_OPERATION_DEFINITION_ID:
        return await _run_apoderado_configure(
            service, context, profile_id=profile_id, operation_id=operation_id, payload=payload
        )
    if operation_id == APODERADO_CLEAR_OPERATION_DEFINITION_ID:
        return await _run_apoderado_clear(service, context, profile_id=profile_id, operation_id=operation_id)
    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


class ApoderadoOperationExecutor:
    """Use the canonical service under one retained authority and write fence."""

    def __init__(self, factory: ApoderadoOperationPortsFactory) -> None:
        """Retain the exact-profile factory until owner execution."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[BaseModel], context: OperationExecutorContext
    ) -> str | OperationRefusalEvidence:
        """Validate before entry; fence only the encrypted save or delete."""
        operation_id, payload = _require_apoderado_request(request)
        profile_id = payload.profile_id
        bucket_id = str(profile_id)
        require_profile_operation_identity(request, context, profile_id)
        if await asyncio.to_thread(require_active_bucket_id) != bucket_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        authority = context.authority_operation
        await context.events.phase(operation_id)

        async def run() -> str | OperationRefusalEvidence:
            service = await asyncio.to_thread(
                _make_apoderado_service, self._factory, bucket_id=bucket_id, authority=authority
            )
            return await _run_apoderado_operation(
                service,
                context,
                profile_id=profile_id,
                operation_id=operation_id,
                payload=payload,
            )

        return await await_cancellation_complete(run(), task_name=operation_id)
