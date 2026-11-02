"""Profile-scoped executor for the suffered-withholding certificate operations."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Final
from uuid import UUID

from pydantic import BaseModel, ValidationError

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.async_cleanup import await_cancellation_complete
from ...core.identity.tax_id import tax_id_identity_token
from ...core.operations import OperationEffect
from ...core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ...core.time.clock import now
from ...domain.renta.retencion_soportada import (
    RetencionSoportadaIdentity,
    RetencionSoportadaOrigen,
    RetencionSoportadaRecord,
)
from ..aggregation.retencion_soportada_repository import (
    RetencionSoportadaRevisionConflictError,
    RetencionSoportadaWriteRefusedError,
    record_retencion_soportada,
)
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..user_profile.access_errors import ProfileAccessRefusedError
from .contracts import (
    RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_REMOVE_OPERATION_DEFINITION_ID,
    RETENCION_SOPORTADA_REVISION_REFUSAL_CODE,
    RETENCION_SOPORTADA_WRITE_REFUSAL_CODE,
    RetencionSoportadaCertificadoRefusalReason,
    RetencionSoportadaOperationId,
)
from .ports import RetencionSoportadaCertificadoPorts, RetencionSoportadaCertificadoPortsFactory
from .requests import (
    RetencionSoportadaListRequest,
    RetencionSoportadaProfileRequest,
    RetencionSoportadaRecordRequest,
    RetencionSoportadaRemoveRequest,
)
from .results import (
    RetencionSoportadaOperationExecutionResult,
    RetencionSoportadaRefusalProjection,
    RetencionSoportadaRowProjection,
)

_REQUEST_TYPES: Final[dict[str, type[RetencionSoportadaProfileRequest]]] = {
    RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID: RetencionSoportadaListRequest,
    RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID: RetencionSoportadaRecordRequest,
    RETENCION_SOPORTADA_REMOVE_OPERATION_DEFINITION_ID: RetencionSoportadaRemoveRequest,
}
_OPERATION_IDS: Final[dict[str, RetencionSoportadaOperationId]] = {
    RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID: "list",
    RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID: "record",
    RETENCION_SOPORTADA_REMOVE_OPERATION_DEFINITION_ID: "remove",
}


class _CertificateRefusalError(Exception):
    """A request the operation refuses with a typed reason before anything is stored."""

    def __init__(self, reason: RetencionSoportadaCertificadoRefusalReason) -> None:
        self.reason: RetencionSoportadaCertificadoRefusalReason = reason
        super().__init__(reason)


def _refusal_code(reason: RetencionSoportadaCertificadoRefusalReason) -> str:
    if reason == "stale_revision":
        return RETENCION_SOPORTADA_REVISION_REFUSAL_CODE
    return RETENCION_SOPORTADA_WRITE_REFUSAL_CODE


def _build_record(
    request: RetencionSoportadaRecordRequest,
    ports: RetencionSoportadaCertificadoPorts,
) -> RetencionSoportadaRecord:
    """Build the record the write path will judge, refusing the shapes it cannot represent."""
    amounts = {
        "importe_integro_dinerario": Decimal(request.importe_integro_dinerario.decimal),
        "valoracion_especie": Decimal(request.valoracion_especie.decimal),
        "retencion": Decimal(request.retencion.decimal),
        "ingreso_a_cuenta": Decimal(request.ingreso_a_cuenta.decimal),
        "ingreso_a_cuenta_repercutido": Decimal(request.ingreso_a_cuenta_repercutido.decimal),
    }
    if amounts["ingreso_a_cuenta_repercutido"] > amounts["ingreso_a_cuenta"]:
        raise _CertificateRefusalError("repercutido_exceeds_ingreso_a_cuenta")
    if request.origin is RetencionSoportadaOrigen.PAYER_CERTIFICATE and request.evidence_fingerprint is None:
        raise _CertificateRefusalError("certificate_fingerprint_required")
    if not tax_id_identity_token(request.payer_tax_id):
        raise _CertificateRefusalError("validation")
    payer_ref = ports.repository.payer_reference(request.payer_tax_id)
    identity: RetencionSoportadaIdentity = (request.ejercicio, request.income_class, payer_ref)
    stored, _revision = ports.repository.load_revisioned(identity)
    try:
        return RetencionSoportadaRecord(
            ejercicio=request.ejercicio,
            payer_tax_id=request.payer_tax_id,
            payer_legal_name=request.payer_legal_name,
            payer_ref=payer_ref,
            income_class=request.income_class,
            origin=request.origin,
            evidence_fingerprint=request.evidence_fingerprint,
            replaces_evidence_fingerprint=stored.evidence_fingerprint if stored is not None else None,
            captured_at=now(),
            **amounts,
        )
    except ValidationError:
        raise _CertificateRefusalError("validation") from None


def _record_certificate(
    request: RetencionSoportadaRecordRequest,
    ports: RetencionSoportadaCertificadoPorts,
) -> tuple[RetencionSoportadaRowProjection, int]:
    taxpayer_tax_id = ports.taxpayer_tax_id()
    if taxpayer_tax_id is None or not tax_id_identity_token(taxpayer_tax_id):
        raise _CertificateRefusalError("taxpayer_tax_id_unknown")
    record = _build_record(request, ports)
    try:
        record_retencion_soportada(
            record,
            repository=ports.repository,
            authority=ports.authority,
            taxpayer_tax_id=taxpayer_tax_id,
            expected_revision_id=request.expected_revision_id or ABSENT_SECURE_OBJECT_REVISION_ID,
        )
    except RetencionSoportadaWriteRefusedError as exc:
        raise _CertificateRefusalError(exc.reason) from None
    except RetencionSoportadaRevisionConflictError:
        raise _CertificateRefusalError("stale_revision") from None
    stored, revision_id = ports.repository.load_revisioned(record.identity)
    if stored is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return (
        RetencionSoportadaRowProjection.from_record(stored, revision_id=revision_id),
        len(ports.repository.list_revisioned(request.ejercicio)),
    )


def _remove_certificate(
    request: RetencionSoportadaRemoveRequest,
    ports: RetencionSoportadaCertificadoPorts,
) -> int:
    identity: RetencionSoportadaIdentity = (request.ejercicio, request.income_class, request.payer_ref)
    stored, revision_id = ports.repository.load_revisioned(identity)
    if stored is None:
        raise _CertificateRefusalError("not_found")
    if revision_id != request.expected_revision_id:
        raise _CertificateRefusalError("stale_revision")
    try:
        ports.repository.delete_revisioned(identity, expected_revision_id=request.expected_revision_id)
    except RetencionSoportadaRevisionConflictError:
        raise _CertificateRefusalError("stale_revision") from None
    return len(ports.repository.list_revisioned(request.ejercicio))


class RetencionSoportadaCertificadoExecutor:
    """Run the family's one write path under exact-profile worker custody."""

    def __init__(self, ports_factory: RetencionSoportadaCertificadoPortsFactory, *, definition_id: str) -> None:
        """Bind the capability factory and the exact public operation id."""
        self._ports_factory = ports_factory
        self._definition_id = definition_id

    async def execute(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> str | OperationRefusalEvidence:
        """Run one list, record or removal and retain its receipt-correlated outcome."""
        payload = self._validate_request(request, context)
        await context.events.phase(self._definition_id)
        if isinstance(payload, RetencionSoportadaListRequest):
            return await self._list(context, payload)
        if isinstance(payload, RetencionSoportadaRecordRequest):
            return await self._mutate(context, payload, "record")
        if isinstance(payload, RetencionSoportadaRemoveRequest):
            return await self._mutate(context, payload, "remove")
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

    def _validate_request(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> RetencionSoportadaProfileRequest:
        request_type = _REQUEST_TYPES.get(self._definition_id)
        payload = request.payload
        if request_type is None or type(payload) is not request_type:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if not isinstance(payload, RetencionSoportadaProfileRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if request.definition_id != self._definition_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        return payload

    def _ports(self, context: OperationExecutorContext, profile_id: UUID) -> RetencionSoportadaCertificadoPorts:
        return self._ports_factory(profile_id=profile_id, operation=context.authority_operation)

    async def _list(self, context: OperationExecutorContext, request: RetencionSoportadaListRequest) -> str:
        async def read() -> str:
            def work() -> tuple[RetencionSoportadaRowProjection, ...]:
                ports = self._ports(context, request.profile_id)
                return tuple(
                    RetencionSoportadaRowProjection.from_record(record, revision_id=revision_id)
                    for record, revision_id in ports.repository.list_revisioned(request.ejercicio)
                )

            rows = await asyncio.to_thread(work)
            result = RetencionSoportadaOperationExecutionResult(
                operation_id="list",
                outcome="success",
                profile_id=request.profile_id,
                ejercicio=request.ejercicio,
                rows=rows,
            )
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(read(), task_name="retencion-soportada-list")

    async def _mutate(
        self,
        context: OperationExecutorContext,
        request: RetencionSoportadaRecordRequest | RetencionSoportadaRemoveRequest,
        operation_id: RetencionSoportadaOperationId,
    ) -> str | OperationRefusalEvidence:
        async def commit() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)

                def work() -> tuple[RetencionSoportadaRowProjection | None, int]:
                    ports = self._ports(context, request.profile_id)
                    if isinstance(request, RetencionSoportadaRecordRequest):
                        row, count = _record_certificate(request, ports)
                        return row, count
                    return None, _remove_certificate(request, ports)

                try:
                    row, count = await asyncio.to_thread(work)
                except _CertificateRefusalError as refused:
                    return await self._persist_refusal(context, request, operation_id, refused.reason)
                result = RetencionSoportadaOperationExecutionResult(
                    operation_id=operation_id,
                    outcome="success",
                    profile_id=request.profile_id,
                    ejercicio=request.ejercicio,
                    row=row,
                    count=count,
                )
                reference = await context.operands.put(result, written_at=now())
                await context.events.effect(OperationEffect.UPDATED)
                return reference

        return await await_cancellation_complete(commit(), task_name=f"retencion-soportada-{operation_id}")

    async def _persist_refusal(
        self,
        context: OperationExecutorContext,
        request: RetencionSoportadaRecordRequest | RetencionSoportadaRemoveRequest,
        operation_id: RetencionSoportadaOperationId,
        reason: RetencionSoportadaCertificadoRefusalReason,
    ) -> OperationRefusalEvidence:
        code = _refusal_code(reason)
        refusal = RetencionSoportadaRefusalProjection.model_validate(
            {"code": code, "reason": reason, "ejercicio": request.ejercicio},
        )
        result = RetencionSoportadaOperationExecutionResult(
            operation_id=operation_id,
            outcome="refused",
            profile_id=request.profile_id,
            ejercicio=request.ejercicio,
            refusal=refusal,
        )
        detail_ref = await context.operands.put(result, written_at=now())
        await context.events.effect(OperationEffect.NONE)
        return OperationRefusalEvidence(refusal_code=code, detail_ref=detail_ref)
