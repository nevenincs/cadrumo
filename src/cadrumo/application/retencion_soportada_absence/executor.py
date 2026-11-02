"""Profile-scoped executor for the suffered-withholding absence attestations."""

from __future__ import annotations

import asyncio
from typing import Final
from uuid import UUID

from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.async_cleanup import await_cancellation_complete
from ...core.operations import OperationEffect
from ...core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ...core.time.clock import now
from ...domain.renta.retencion_soportada_absence import RetencionSoportadaAbsence
from ..aggregation.retencion_soportada_absence_repository import (
    RetencionSoportadaAbsenceRefusedError,
    RetencionSoportadaAbsenceWritePorts,
    attest_retencion_soportada_absence,
    withdraw_retencion_soportada_absence,
)
from ..aggregation.retencion_soportada_repository import RetencionSoportadaRevisionConflictError
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..user_profile.access_errors import ProfileAccessRefusedError
from .contracts import (
    RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_ABSENCE_LIST_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_ABSENCE_REFUSAL_CODE,
    RETENCION_SOPORTADA_ABSENCE_REVISION_REFUSAL_CODE,
    RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID,
    RetencionSoportadaAbsenceOperationId,
    RetencionSoportadaAbsenceOperationRefusalReason,
)
from .ports import RetencionSoportadaAbsencePortsFactory
from .requests import (
    RetencionSoportadaAbsenceAttestRequest,
    RetencionSoportadaAbsenceListRequest,
    RetencionSoportadaAbsenceProfileRequest,
    RetencionSoportadaAbsenceRequest,
    RetencionSoportadaAbsenceWithdrawRequest,
)
from .results import (
    RetencionSoportadaAbsenceExecutionResult,
    RetencionSoportadaAbsenceProjection,
    RetencionSoportadaAbsenceRefusalProjection,
    RetencionSoportadaAbsenceRowProjection,
)

__all__ = ["RetencionSoportadaAbsenceExecutor"]

_REQUEST_TYPES: Final[dict[str, type[RetencionSoportadaAbsenceProfileRequest]]] = {
    RETENCION_SOPORTADA_ABSENCE_LIST_OPERATION_DEFINITION_ID: RetencionSoportadaAbsenceListRequest,
    RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID: RetencionSoportadaAbsenceAttestRequest,
    RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID: RetencionSoportadaAbsenceWithdrawRequest,
}
_OPERATION_IDS: Final[dict[str, RetencionSoportadaAbsenceOperationId]] = {
    RETENCION_SOPORTADA_ABSENCE_ATTEST_OPERATION_DEFINITION_ID: "attest",
    RETENCION_SOPORTADA_ABSENCE_WITHDRAW_OPERATION_DEFINITION_ID: "withdraw",
    RETENCION_SOPORTADA_ABSENCE_LIST_OPERATION_DEFINITION_ID: "list",
}


def _attest(
    request: RetencionSoportadaAbsenceAttestRequest, ports: RetencionSoportadaAbsenceWritePorts
) -> RetencionSoportadaAbsenceProjection | RetencionSoportadaAbsenceOperationRefusalReason:
    """Store the attestation, or name why the write path refused it before anything was stored."""
    attestation = RetencionSoportadaAbsence(
        ejercicio=request.ejercicio,
        income_class=request.income_class,
        note=request.note,
        attested_at=now(),
    )
    try:
        revision_id = attest_retencion_soportada_absence(
            attestation,
            ports=ports,
            expected_revision_id=request.expected_revision_id or ABSENT_SECURE_OBJECT_REVISION_ID,
        )
    except RetencionSoportadaAbsenceRefusedError as exc:
        return exc.reason
    except RetencionSoportadaRevisionConflictError:
        return "stale_revision"
    return RetencionSoportadaAbsenceProjection.from_attestation(attestation, revision_id=revision_id)


def _withdraw(
    request: RetencionSoportadaAbsenceWithdrawRequest, ports: RetencionSoportadaAbsenceWritePorts
) -> RetencionSoportadaAbsenceProjection | RetencionSoportadaAbsenceOperationRefusalReason:
    """Withdraw the attestation, or name why the write path refused it before anything was stored."""
    try:
        withdrawn, revision_id = withdraw_retencion_soportada_absence(
            (request.ejercicio, request.income_class),
            at=now(),
            ports=ports,
            expected_revision_id=request.expected_revision_id,
        )
    except RetencionSoportadaAbsenceRefusedError as exc:
        return exc.reason
    except RetencionSoportadaRevisionConflictError:
        return "stale_revision"
    return RetencionSoportadaAbsenceProjection.from_attestation(withdrawn, revision_id=revision_id)


class RetencionSoportadaAbsenceExecutor:
    """Run the attestation write path under exact-profile worker custody."""

    def __init__(self, ports_factory: RetencionSoportadaAbsencePortsFactory, *, definition_id: str) -> None:
        """Bind the capability factory and the exact public operation id."""
        self._ports_factory = ports_factory
        self._definition_id = definition_id

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Run one list, attestation or withdrawal and retain its receipt-correlated outcome."""
        payload = self._validate_request(request, context)
        await context.events.phase(self._definition_id)
        operation_id = _OPERATION_IDS[self._definition_id]
        if isinstance(payload, RetencionSoportadaAbsenceListRequest):
            return await self._list(context, payload)
        if not isinstance(payload, RetencionSoportadaAbsenceRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

        async def commit() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)

                def work() -> RetencionSoportadaAbsenceProjection | RetencionSoportadaAbsenceOperationRefusalReason:
                    ports = self._ports(context, payload.profile_id)
                    if isinstance(payload, RetencionSoportadaAbsenceAttestRequest):
                        return _attest(payload, ports)
                    if isinstance(payload, RetencionSoportadaAbsenceWithdrawRequest):
                        return _withdraw(payload, ports)
                    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

                attestation = await asyncio.to_thread(work)
                if isinstance(attestation, str):
                    return await self._persist_refusal(context, payload, operation_id, attestation)
                result = RetencionSoportadaAbsenceExecutionResult(
                    operation_id=operation_id,
                    outcome="success",
                    profile_id=payload.profile_id,
                    ejercicio=payload.ejercicio,
                    attestation=attestation,
                )
                reference = await context.operands.put(result, written_at=now())
                await context.events.effect(OperationEffect.UPDATED)
                return reference

        return await await_cancellation_complete(commit(), task_name=f"retencion-soportada-absence-{operation_id}")

    def _validate_request(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> RetencionSoportadaAbsenceProfileRequest:
        request_type = _REQUEST_TYPES.get(self._definition_id)
        payload = request.payload
        if request_type is None or type(payload) is not request_type:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if not isinstance(payload, RetencionSoportadaAbsenceProfileRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if request.definition_id != self._definition_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        return payload

    def _ports(self, context: OperationExecutorContext, profile_id: UUID) -> RetencionSoportadaAbsenceWritePorts:
        return self._ports_factory(profile_id=profile_id, operation=context.authority_operation)

    async def _list(self, context: OperationExecutorContext, request: RetencionSoportadaAbsenceListRequest) -> str:
        async def read() -> str:
            def work() -> tuple[RetencionSoportadaAbsenceRowProjection, ...]:
                ports = self._ports(context, request.profile_id)
                return tuple(
                    RetencionSoportadaAbsenceRowProjection.from_attestation(attestation, revision_id=revision_id)
                    for attestation, revision_id in ports.attestations.list_revisioned(request.ejercicio)
                )

            attestations = await asyncio.to_thread(work)
            result = RetencionSoportadaAbsenceExecutionResult(
                operation_id="list",
                outcome="success",
                profile_id=request.profile_id,
                ejercicio=request.ejercicio,
                attestations=attestations,
            )
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(read(), task_name="retencion-soportada-absence-list")

    async def _persist_refusal(
        self,
        context: OperationExecutorContext,
        request: RetencionSoportadaAbsenceRequest,
        operation_id: RetencionSoportadaAbsenceOperationId,
        reason: RetencionSoportadaAbsenceOperationRefusalReason,
    ) -> OperationRefusalEvidence:
        code = (
            RETENCION_SOPORTADA_ABSENCE_REVISION_REFUSAL_CODE
            if reason == "stale_revision"
            else RETENCION_SOPORTADA_ABSENCE_REFUSAL_CODE
        )
        refusal = RetencionSoportadaAbsenceRefusalProjection.model_validate(
            {"code": code, "reason": reason, "ejercicio": request.ejercicio, "income_class": request.income_class},
        )
        result = RetencionSoportadaAbsenceExecutionResult(
            operation_id=operation_id,
            outcome="refused",
            profile_id=request.profile_id,
            ejercicio=request.ejercicio,
            refusal=refusal,
        )
        detail_ref = await context.operands.put(result, written_at=now())
        await context.events.effect(OperationEffect.NONE)
        return OperationRefusalEvidence(refusal_code=code, detail_ref=detail_ref)
