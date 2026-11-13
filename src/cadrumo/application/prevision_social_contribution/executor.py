"""Profile-scoped executor for the pension contribution certificate operations."""

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
from ...core.operations import OperationEffect
from ...core.prevision_social import is_defined_clave_pair
from ...core.secure_object_write import ABSENT_SECURE_OBJECT_REVISION_ID
from ...core.time.clock import now
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.calculations.registry.tax_id_runtime import validate_runtime_spanish_tax_id
from ...domain.renta.prevision_social_contribution import (
    PrevisionSocialContribution,
    PrevisionSocialContributionIdentity,
)
from ..aggregation.prevision_social_contribution_repository import (
    PrevisionSocialContributionRevisionConflictError,
    PrevisionSocialContributionWriteRefusedError,
    record_prevision_social_contribution,
    require_prevision_social_contribution_writable,
)
from ..ledger.evidence import admit_evidence_file
from ..ledger.evidence_errors import PurchaseInvoiceEvidenceInputError
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.refusal_evidence import OperationRefusalEvidence
from ..user_profile.access_errors import ProfileAccessRefusedError
from .contracts import (
    PREVISION_SOCIAL_LIST_OPERATION_DEFINITION_ID,
    PREVISION_SOCIAL_RECORD_OPERATION_DEFINITION_ID,
    PREVISION_SOCIAL_REMOVE_OPERATION_DEFINITION_ID,
    PREVISION_SOCIAL_REVISION_REFUSAL_CODE,
    PREVISION_SOCIAL_WRITE_REFUSAL_CODE,
    PrevisionSocialOperationId,
    PrevisionSocialRefusalReason,
)
from .ports import PrevisionSocialPorts, PrevisionSocialPortsFactory
from .refusal_words import served_refusal_words
from .requests import (
    PrevisionSocialListRequest,
    PrevisionSocialProfileRequest,
    PrevisionSocialRecordRequest,
    PrevisionSocialRemoveRequest,
)
from .results import (
    PrevisionSocialOperationExecutionResult,
    PrevisionSocialRefusalProjection,
    PrevisionSocialRowProjection,
)
from .rows import contribution_row, contribution_rows

_UNKNOWN_MIME_TYPE: Final = "application/octet-stream"

_REQUEST_TYPES: Final[dict[str, type[PrevisionSocialProfileRequest]]] = {
    PREVISION_SOCIAL_LIST_OPERATION_DEFINITION_ID: PrevisionSocialListRequest,
    PREVISION_SOCIAL_RECORD_OPERATION_DEFINITION_ID: PrevisionSocialRecordRequest,
    PREVISION_SOCIAL_REMOVE_OPERATION_DEFINITION_ID: PrevisionSocialRemoveRequest,
}


@dataclass(frozen=True, slots=True)
class _Refusal:
    """A request the operation refuses with a typed reason, before any record is stored.

    ``bytes_stored`` is set when the certificate bytes had already reached custody
    by the time the refusal was reached, so the operation reports that effect.
    """

    reason: PrevisionSocialRefusalReason
    bytes_stored: bool = False


@dataclass(frozen=True, slots=True)
class _CertificateFile:
    """The bytes of a certificate file the worker read, and the sha256 custody will address them by."""

    path: Path
    data: bytes = field(repr=False)
    fingerprint: str


def _refusal_code(reason: PrevisionSocialRefusalReason) -> str:
    if reason == "stale_revision":
        return PREVISION_SOCIAL_REVISION_REFUSAL_CODE
    return PREVISION_SOCIAL_WRITE_REFUSAL_CODE


def _read_certificate(request: PrevisionSocialRecordRequest) -> _CertificateFile | _Refusal | None:
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
        return _Refusal("certificate_file_unreadable")
    if not data:
        return _Refusal("certificate_file_unreadable")
    fingerprint = sha256_hex(data)
    if request.evidence_fingerprint is not None and request.evidence_fingerprint != fingerprint:
        return _Refusal("certificate_fingerprint_mismatch")
    return _CertificateFile(path=resolved, data=data, fingerprint=fingerprint)


def _canonical_tax_ids(request: PrevisionSocialRecordRequest) -> tuple[str, str | None] | _Refusal:
    """Return the checksum-validated canonical issuer and plan identifiers, which key the row.

    A mistyped identifier would file the certificate under an issuer or plan that
    does not exist, and the printed and the bare forms of one identifier would key
    two rows; the canonical form fixes both.
    """
    try:
        issuer = validate_runtime_spanish_tax_id(request.issuer_tax_id)
        plan = None if request.plan_tax_id is None else validate_runtime_spanish_tax_id(request.plan_tax_id)
    except IdentityError:
        return _Refusal("validation")
    return issuer, plan


def _build_record(
    request: PrevisionSocialRecordRequest, ports: PrevisionSocialPorts, *, fingerprint: str
) -> PrevisionSocialContribution | _Refusal:
    """Build the record the write path will judge, or name why its shape cannot be represented."""
    if not is_defined_clave_pair(request.clave, request.subclave):
        return _Refusal("clave_pair_undefined")
    tax_ids = _canonical_tax_ids(request)
    if isinstance(tax_ids, _Refusal):
        return tax_ids
    issuer_tax_id, plan_tax_id = tax_ids
    issuer_ref = ports.repository.issuer_reference(issuer_tax_id)
    plan_ref = None if plan_tax_id is None else ports.repository.plan_reference(plan_tax_id)
    identity: PrevisionSocialContributionIdentity = (
        request.ejercicio,
        issuer_ref,
        plan_ref,
        request.clave,
        request.subclave,
    )
    stored, _revision = ports.repository.load_revisioned(identity)
    try:
        return PrevisionSocialContribution(
            ejercicio=request.ejercicio,
            issuer_tax_id=issuer_tax_id,
            issuer_legal_name=request.issuer_legal_name,
            issuer_ref=issuer_ref,
            plan_tax_id=plan_tax_id,
            plan_name=request.plan_name,
            plan_ref=plan_ref,
            clave=request.clave,
            subclave=request.subclave,
            amount=Decimal(request.amount.decimal),
            beneficiary=request.beneficiary,
            employer_contributed_to_same_plan=request.employer_contributed_to_same_plan,
            evidence_fingerprint=fingerprint,
            replaces_evidence_fingerprint=None if stored is None else stored.evidence_fingerprint,
            captured_at=now(),
        )
    except ValidationError:
        return _Refusal("validation")


def _prepare_record(
    request: PrevisionSocialRecordRequest, ports: PrevisionSocialPorts
) -> tuple[_CertificateFile | None, PrevisionSocialContribution] | _Refusal:
    """Settle the certificate file and the record to write, or name why none can be."""
    certificate = _read_certificate(request)
    if isinstance(certificate, _Refusal):
        return certificate
    fingerprint = request.evidence_fingerprint if certificate is None else certificate.fingerprint
    if fingerprint is None:
        return _Refusal("certificate_fingerprint_required")
    record = _build_record(request, ports, fingerprint=fingerprint)
    if isinstance(record, _Refusal):
        return record
    return certificate, record


def _stored_projection(
    record: PrevisionSocialContribution, ports: PrevisionSocialPorts
) -> tuple[PrevisionSocialRowProjection, int]:
    """Read back the record just written, with the count of the year's records."""
    stored, revision_id = ports.repository.load_revisioned(record.identity)
    if stored is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return contribution_row(ports, stored, revision_id), len(ports.repository.list_revisioned(record.ejercicio))


def _keep_certificate(certificate: _CertificateFile, ports: PrevisionSocialPorts) -> None:
    ports.custody.ingest(
        source_path=certificate.path,
        data=certificate.data,
        mime_type=mimetypes.guess_type(certificate.path.name)[0] or _UNKNOWN_MIME_TYPE,
        captured_at=now(),
    )


def _record_contribution(
    request: PrevisionSocialRecordRequest, ports: PrevisionSocialPorts
) -> tuple[PrevisionSocialRowProjection, int] | _Refusal:
    prepared = _prepare_record(request, ports)
    if isinstance(prepared, _Refusal):
        return prepared
    certificate, record = prepared
    expected_revision_id = request.expected_revision_id or ABSENT_SECURE_OBJECT_REVISION_ID
    stored_bytes = False
    try:
        # Every refusal that does not depend on custody, the placement refusals among them, is settled before
        # the bytes are kept, so a record the write would refuse leaves nothing behind.
        require_prevision_social_contribution_writable(
            record, repository=ports.repository, authority=ports.authority, expected_revision_id=expected_revision_id
        )
        if certificate is not None:
            _keep_certificate(certificate, ports)
            stored_bytes = True
        record_prevision_social_contribution(
            record,
            repository=ports.repository,
            authority=ports.authority,
            custody=ports.custody,
            expected_revision_id=expected_revision_id,
        )
    except PrevisionSocialContributionWriteRefusedError as exc:
        return _Refusal(exc.reason, bytes_stored=stored_bytes)
    except PrevisionSocialContributionRevisionConflictError:
        return _Refusal("stale_revision", bytes_stored=stored_bytes)
    return _stored_projection(record, ports)


def _remove_contribution(request: PrevisionSocialRemoveRequest, ports: PrevisionSocialPorts) -> int | _Refusal:
    identity: PrevisionSocialContributionIdentity = (
        request.ejercicio,
        request.issuer_ref,
        request.plan_ref,
        request.clave,
        request.subclave,
    )
    stored, revision_id = ports.repository.load_revisioned(identity)
    if stored is None:
        return _Refusal("not_found")
    if revision_id != request.expected_revision_id:
        return _Refusal("stale_revision")
    try:
        ports.repository.delete_revisioned(identity, expected_revision_id=request.expected_revision_id)
    except PrevisionSocialContributionRevisionConflictError:
        return _Refusal("stale_revision")
    return len(ports.repository.list_revisioned(request.ejercicio))


class PrevisionSocialContributionExecutor:
    """Run the family's one write path under exact-profile worker custody."""

    def __init__(self, ports_factory: PrevisionSocialPortsFactory, *, definition_id: str) -> None:
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
        if isinstance(payload, PrevisionSocialListRequest):
            return await self._list(context, payload)
        if isinstance(payload, PrevisionSocialRecordRequest):
            return await self._mutate(context, payload, "record")
        if isinstance(payload, PrevisionSocialRemoveRequest):
            return await self._mutate(context, payload, "remove")
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)

    def _validate_request(
        self,
        request: OperationRequest[BaseModel],
        context: OperationExecutorContext,
    ) -> PrevisionSocialProfileRequest:
        request_type = _REQUEST_TYPES.get(self._definition_id)
        payload = request.payload
        if request_type is None or type(payload) is not request_type:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if not isinstance(payload, PrevisionSocialProfileRequest):
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        if request.definition_id != self._definition_id:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        return payload

    def _ports(self, context: OperationExecutorContext, profile_id: UUID) -> PrevisionSocialPorts:
        return self._ports_factory(profile_id=profile_id, operation=context.authority_operation)

    def _list_rows(
        self, context: OperationExecutorContext, request: PrevisionSocialListRequest
    ) -> tuple[PrevisionSocialRowProjection, ...]:
        ports = self._ports(context, request.profile_id)
        return contribution_rows(ports, request.ejercicio, operation=context.authority_operation)

    async def _list(self, context: OperationExecutorContext, request: PrevisionSocialListRequest) -> str:
        async def read() -> str:
            rows = await asyncio.to_thread(self._list_rows, context, request)
            result = PrevisionSocialOperationExecutionResult(
                operation_id="list",
                outcome="success",
                profile_id=request.profile_id,
                ejercicio=request.ejercicio,
                rows=rows,
                ejercicios=tuple(sorted(context.authority_operation.supported_filing_years().years)),
            )
            reference = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return reference

        return await await_cancellation_complete(read(), task_name="prevision-social-list")

    def _commit_work(
        self,
        context: OperationExecutorContext,
        request: PrevisionSocialRecordRequest | PrevisionSocialRemoveRequest,
    ) -> tuple[PrevisionSocialRowProjection | None, int] | _Refusal:
        ports = self._ports(context, request.profile_id)
        if isinstance(request, PrevisionSocialRecordRequest):
            with validating_governed_facts(context.authority_operation):
                return _record_contribution(request, ports)
        removed = _remove_contribution(request, ports)
        if isinstance(removed, _Refusal):
            return removed
        return None, removed

    async def _mutate(
        self,
        context: OperationExecutorContext,
        request: PrevisionSocialRecordRequest | PrevisionSocialRemoveRequest,
        operation_id: PrevisionSocialOperationId,
    ) -> str | OperationRefusalEvidence:
        async def commit() -> str | OperationRefusalEvidence:
            async with context.cancellation.irreversible_section():
                await context.events.effect(OperationEffect.UNKNOWN)
                outcome = await asyncio.to_thread(self._commit_work, context, request)
                if isinstance(outcome, _Refusal):
                    return await self._persist_refusal(context, request, operation_id, outcome)
                row, count = outcome
                result = PrevisionSocialOperationExecutionResult(
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

        return await await_cancellation_complete(commit(), task_name=f"prevision-social-{operation_id}")

    async def _persist_refusal(
        self,
        context: OperationExecutorContext,
        request: PrevisionSocialRecordRequest | PrevisionSocialRemoveRequest,
        operation_id: PrevisionSocialOperationId,
        refused: _Refusal,
    ) -> OperationRefusalEvidence:
        code = _refusal_code(refused.reason)
        words, language = served_refusal_words(refused.reason, error_code=code)
        refusal = PrevisionSocialRefusalProjection.model_validate(
            {
                "code": code,
                "reason": refused.reason,
                "ejercicio": request.ejercicio,
                "refusal_words": words,
                "refusal_words_language": language,
            },
        )
        result = PrevisionSocialOperationExecutionResult(
            operation_id=operation_id,
            outcome="refused",
            profile_id=request.profile_id,
            ejercicio=request.ejercicio,
            refusal=refusal,
        )
        detail_ref = await context.operands.put(result, written_at=now())
        await context.events.effect(OperationEffect.PARTIAL if refused.bytes_stored else OperationEffect.NONE)
        return OperationRefusalEvidence(refusal_code=code, detail_ref=detail_ref)
