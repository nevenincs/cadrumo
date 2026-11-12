"""Profile-scoped executor for the suffered-withholding certificate operations."""

from __future__ import annotations

import asyncio
import mimetypes
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Final
from uuid import UUID

from pydantic import BaseModel, ValidationError

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.async_cleanup import await_cancellation_complete
from ...core.hashing import sha256_hex
from ...core.identity.documents import IdentityError
from ...core.identity.tax_id import tax_id_identity_token
from ...core.operations import OperationEffect
from ...core.retencion_soportada import RetencionSoportadaCantidad
from ...core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ...core.time.clock import now
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.tax_id_runtime import validate_runtime_spanish_tax_id
from ...domain.renta.retencion_soportada import (
    RetencionSoportadaIdentity,
    RetencionSoportadaOrigen,
    RetencionSoportadaRecord,
    class_certificate_figures,
)
from ..aggregation.retencion_soportada_repository import (
    RetencionSoportadaRevisionConflictError,
    RetencionSoportadaWriteRefusedError,
    record_retencion_soportada,
    require_retencion_soportada_writable,
)
from ..ledger.evidence import admit_evidence_file
from ..ledger.evidence_errors import PurchaseInvoiceEvidenceInputError
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.public_scalar import PublicDecimal
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
from .refusal_words import served_refusal_words
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

_UNKNOWN_MIME_TYPE: Final = "application/octet-stream"

_REQUEST_TYPES: Final[dict[str, type[RetencionSoportadaProfileRequest]]] = {
    RETENCION_SOPORTADA_LIST_OPERATION_DEFINITION_ID: RetencionSoportadaListRequest,
    RETENCION_SOPORTADA_RECORD_OPERATION_DEFINITION_ID: RetencionSoportadaRecordRequest,
    RETENCION_SOPORTADA_REMOVE_OPERATION_DEFINITION_ID: RetencionSoportadaRemoveRequest,
}


@dataclass(frozen=True, slots=True)
class _CertificateRefusal:
    """A request the operation refuses with a typed reason, before any record is stored.

    ``bytes_stored`` is set when the certificate bytes had already reached custody
    by the time the refusal was reached, so the operation reports that effect.
    """

    reason: RetencionSoportadaCertificadoRefusalReason
    bytes_stored: bool = False


@dataclass(frozen=True, slots=True)
class _CertificateFile:
    """The bytes of a certificate file the worker read, and the sha256 custody will address them by."""

    path: Path
    data: bytes = field(repr=False)
    fingerprint: str


def _refusal_code(reason: RetencionSoportadaCertificadoRefusalReason) -> str:
    if reason == "stale_revision":
        return RETENCION_SOPORTADA_REVISION_REFUSAL_CODE
    return RETENCION_SOPORTADA_WRITE_REFUSAL_CODE


def _read_certificate(request: RetencionSoportadaRecordRequest) -> _CertificateFile | _CertificateRefusal | None:
    """Read the certificate file the request names, or ``None`` when it names none.

    The fingerprint a request also carries is an integrity cross-check against
    the bytes actually read, never the address custody is given.
    """
    if request.source_path is None or request.source_directory is None:
        return None
    try:
        resolved, _media_kind = admit_evidence_file(request.source_path, Path(request.source_directory))
        data = resolved.read_bytes()
    except (PurchaseInvoiceEvidenceInputError, OSError):
        return _CertificateRefusal("certificate_file_unreadable")
    if not data:
        return _CertificateRefusal("certificate_file_unreadable")
    fingerprint = sha256_hex(data)
    if request.evidence_fingerprint is not None and request.evidence_fingerprint != fingerprint:
        return _CertificateRefusal("certificate_fingerprint_mismatch")
    return _CertificateFile(path=resolved, data=data, fingerprint=fingerprint)


def _optional_decimal(amount: PublicDecimal | None) -> Decimal | None:
    return None if amount is None else Decimal(amount.decimal)


def _build_record(
    request: RetencionSoportadaRecordRequest,
    ports: RetencionSoportadaCertificadoPorts,
    *,
    fingerprint: str | None,
) -> RetencionSoportadaRecord | _CertificateRefusal:
    """Build the record the write path will judge, or name why its shape cannot be represented."""
    amounts = {
        "importe_integro_dinerario": Decimal(request.importe_integro_dinerario.decimal),
        "valoracion_especie": Decimal(request.valoracion_especie.decimal),
        "retencion": Decimal(request.retencion.decimal),
        "ingreso_a_cuenta": Decimal(request.ingreso_a_cuenta.decimal),
        "ingreso_a_cuenta_repercutido": Decimal(request.ingreso_a_cuenta_repercutido.decimal),
    }
    if amounts["ingreso_a_cuenta_repercutido"] > amounts["ingreso_a_cuenta"]:
        return _CertificateRefusal("repercutido_exceeds_ingreso_a_cuenta")
    class_figures = {
        RetencionSoportadaCantidad.REDUCCIONES_APLICABLES: request.reducciones_aplicables,
        RetencionSoportadaCantidad.GASTOS_DEDUCIBLES: request.gastos_deducibles,
    }
    if any(class_figures.get(figure) is None for figure in class_certificate_figures(request.income_class)):
        return _CertificateRefusal("trabajo_certificate_figure_missing")
    if request.origin is RetencionSoportadaOrigen.PAYER_CERTIFICATE and fingerprint is None:
        return _CertificateRefusal("certificate_fingerprint_required")
    # A payer withholds under a Spanish identifier, and the identifier is what keys the row: a mistyped
    # one would file the certificate under a payer that does not exist, and the printed and the bare
    # forms of one identifier would key two rows. The checksum-validated canonical form fixes both.
    try:
        payer_tax_id = validate_runtime_spanish_tax_id(request.payer_tax_id)
    except IdentityError:
        return _CertificateRefusal("validation")
    payer_ref = ports.repository.payer_reference(payer_tax_id)
    identity: RetencionSoportadaIdentity = (request.ejercicio, request.income_class, payer_ref)
    stored, _revision = ports.repository.load_revisioned(identity)
    try:
        return RetencionSoportadaRecord(
            ejercicio=request.ejercicio,
            payer_tax_id=payer_tax_id,
            payer_legal_name=request.payer_legal_name,
            payer_ref=payer_ref,
            income_class=request.income_class,
            origin=request.origin,
            evidence_fingerprint=fingerprint,
            replaces_evidence_fingerprint=stored.evidence_fingerprint if stored is not None else None,
            captured_at=now(),
            reducciones_aplicables=_optional_decimal(request.reducciones_aplicables),
            gastos_deducibles=_optional_decimal(request.gastos_deducibles),
            **amounts,
        )
    except ValidationError:
        return _CertificateRefusal("validation")


def _prepare_record(
    request: RetencionSoportadaRecordRequest,
    ports: RetencionSoportadaCertificadoPorts,
) -> tuple[str, _CertificateFile | None, RetencionSoportadaRecord] | _CertificateRefusal:
    """Settle the taxpayer, the certificate file and the record to write, or name why none can be."""
    taxpayer_tax_id = ports.taxpayer_tax_id()
    if taxpayer_tax_id is None or not tax_id_identity_token(taxpayer_tax_id):
        return _CertificateRefusal("taxpayer_tax_id_unknown")
    certificate = _read_certificate(request)
    if isinstance(certificate, _CertificateRefusal):
        return certificate
    record = _build_record(
        request,
        ports,
        fingerprint=request.evidence_fingerprint if certificate is None else certificate.fingerprint,
    )
    if isinstance(record, _CertificateRefusal):
        return record
    return taxpayer_tax_id, certificate, record


def _stored_projection(
    record: RetencionSoportadaRecord,
    request: RetencionSoportadaRecordRequest,
    ports: RetencionSoportadaCertificadoPorts,
) -> tuple[RetencionSoportadaRowProjection, int]:
    """Read back the record just written, with the count of the year's records."""
    stored, revision_id = ports.repository.load_revisioned(record.identity)
    if stored is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return (
        RetencionSoportadaRowProjection.from_record(stored, revision_id=revision_id),
        len(ports.repository.list_revisioned(request.ejercicio)),
    )


def _record_certificate(
    request: RetencionSoportadaRecordRequest,
    ports: RetencionSoportadaCertificadoPorts,
) -> tuple[RetencionSoportadaRowProjection, int] | _CertificateRefusal:
    prepared = _prepare_record(request, ports)
    if isinstance(prepared, _CertificateRefusal):
        return prepared
    taxpayer_tax_id, certificate, record = prepared
    expected_revision_id = request.expected_revision_id or ABSENT_SECURE_OBJECT_REVISION_ID
    stored_bytes = False
    try:
        # Every refusal that does not depend on custody is settled before the bytes are kept, so a record
        # the write would refuse leaves nothing behind.
        require_retencion_soportada_writable(
            record,
            repository=ports.repository,
            authority=ports.authority,
            taxpayer_tax_id=taxpayer_tax_id,
            expected_revision_id=expected_revision_id,
        )
        if certificate is not None:
            ports.custody.ingest(
                source_path=certificate.path,
                data=certificate.data,
                mime_type=mimetypes.guess_type(certificate.path.name)[0] or _UNKNOWN_MIME_TYPE,
                captured_at=now(),
            )
            stored_bytes = True
        record_retencion_soportada(
            record,
            repository=ports.repository,
            authority=ports.authority,
            custody=ports.custody,
            taxpayer_tax_id=taxpayer_tax_id,
            expected_revision_id=expected_revision_id,
        )
    except RetencionSoportadaWriteRefusedError as exc:
        return _CertificateRefusal(exc.reason, bytes_stored=stored_bytes)
    except RetencionSoportadaRevisionConflictError:
        return _CertificateRefusal("stale_revision", bytes_stored=stored_bytes)
    return _stored_projection(record, request, ports)


def _remove_certificate(
    request: RetencionSoportadaRemoveRequest,
    ports: RetencionSoportadaCertificadoPorts,
) -> int | _CertificateRefusal:
    identity: RetencionSoportadaIdentity = (request.ejercicio, request.income_class, request.payer_ref)
    stored, revision_id = ports.repository.load_revisioned(identity)
    if stored is None:
        return _CertificateRefusal("not_found")
    if revision_id != request.expected_revision_id:
        return _CertificateRefusal("stale_revision")
    try:
        ports.repository.delete_revisioned(identity, expected_revision_id=request.expected_revision_id)
    except RetencionSoportadaRevisionConflictError:
        return _CertificateRefusal("stale_revision")
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

                def work() -> tuple[RetencionSoportadaRowProjection | None, int] | _CertificateRefusal:
                    ports = self._ports(context, request.profile_id)
                    if isinstance(request, RetencionSoportadaRecordRequest):
                        with validating_governed_facts(context.authority_operation):
                            return _record_certificate(request, ports)
                    removed = _remove_certificate(request, ports)
                    if isinstance(removed, _CertificateRefusal):
                        return removed
                    return None, removed

                outcome = await asyncio.to_thread(work)
                if isinstance(outcome, _CertificateRefusal):
                    return await self._persist_refusal(context, request, operation_id, outcome)
                row, count = outcome
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
        refused: _CertificateRefusal,
    ) -> OperationRefusalEvidence:
        code = _refusal_code(refused.reason)
        words, language = served_refusal_words(refused.reason, error_code=code)
        refusal = RetencionSoportadaRefusalProjection.model_validate(
            {
                "code": code,
                "reason": refused.reason,
                "ejercicio": request.ejercicio,
                "refusal_words": words,
                "refusal_words_language": language,
            },
        )
        result = RetencionSoportadaOperationExecutionResult(
            operation_id=operation_id,
            outcome="refused",
            profile_id=request.profile_id,
            ejercicio=request.ejercicio,
            refusal=refusal,
        )
        detail_ref = await context.operands.put(result, written_at=now())
        await context.events.effect(OperationEffect.PARTIAL if refused.bytes_stored else OperationEffect.NONE)
        return OperationRefusalEvidence(refusal_code=code, detail_ref=detail_ref)
