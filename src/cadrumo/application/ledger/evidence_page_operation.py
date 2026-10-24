"""Worker read that draws one page of a stored document, and its registration.

The worker loads the document's encrypted bytes from the profile's attachment
custody, checks them against the digest its record names, and has the
renderer draw the requested page. Only the bounded image and the document's
facts enter the result operand; the decrypted bytes stay in worker memory.
"""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass

from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.projection_pages import PROJECTION_DOCUMENT_MAX_BYTES

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.hashing import canonical_json_bytes, sha256_hex
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ...core.time.clock import now
from ...domain.attachments.enums import AttachmentSource
from ...domain.attachments.errors import AttachmentNotFoundError, AttachmentValidationError
from ...domain.attachments.models import Attachment
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES
from ..operations.host_path_name import host_path_file_name
from ..operations.models import OperationRequest, OperationTerminalReceipt, require_terminal_receipt_match
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .evidence import PurchaseInvoiceEvidenceService
from .evidence_errors import PurchaseInvoiceEvidenceNotFoundError
from .evidence_page_contracts import (
    EVIDENCE_PAGE_IMAGE_URL_PREFIX,
    EVIDENCE_PAGE_MAX_IMAGE_BYTES,
    LEDGER_EVIDENCE_PAGE_OPERATION_DEFINITION_ID,
    EvidencePageMediaType,
    LedgerEvidencePageExecutionResult,
    LedgerEvidencePagePorts,
    LedgerEvidencePageProjection,
    LedgerEvidencePageRequest,
)
from .evidence_page_errors import (
    LedgerEvidencePageDigestMismatchError,
    LedgerEvidencePageNotFoundError,
    LedgerEvidencePageTooLargeError,
    LedgerEvidencePageUnreadableError,
    LedgerEvidencePageUnsupportedMediaError,
)
from .read_access import resolve_ledger_request_read_access

_MAX_RESULT_BYTES = PROJECTION_DOCUMENT_MAX_BYTES - 4_096


@dataclass(frozen=True, slots=True)
class _StoredDocument:
    """Where a requested document's bytes are kept and the digest they must hash to."""

    attachment_id: str
    expected_sha256: str
    file_name: str | None


def _require_worker_identity(
    request: OperationRequest[LedgerEvidencePageRequest],
    context: OperationExecutorContext,
) -> str:
    """Refuse a foreign request or stale active bucket before opening a port."""
    bucket_id = str(request.payload.profile_id)
    subject = profile_operation_subject(bucket_id)
    if (
        request.definition_id != LEDGER_EVIDENCE_PAGE_OPERATION_DEFINITION_ID
        or context.identity.definition_id != LEDGER_EVIDENCE_PAGE_OPERATION_DEFINITION_ID
        or request.subject_ref != subject
        or context.identity.subject_ref != subject
        or require_active_bucket_id() != bucket_id
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return bucket_id


def _named_file(path_or_locator: str) -> str | None:
    """The file name of a recorded local path or file URI, never the folder it lay in."""
    name = host_path_file_name(path_or_locator.removeprefix("file:"))
    return name if name is not None and name not in {".", ".."} else None


def _evidence_document(ports: LedgerEvidencePagePorts, bucket_id: str, evidence_id: str) -> _StoredDocument:
    try:
        record = PurchaseInvoiceEvidenceService(ports=ports.evidence_ports_factory(bucket_id=bucket_id)).view(
            bucket_id=bucket_id, evidence_id=evidence_id
        )
    except PurchaseInvoiceEvidenceNotFoundError:
        raise LedgerEvidencePageNotFoundError() from None
    if record.bucket_id != bucket_id or record.evidence_id != evidence_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return _StoredDocument(
        attachment_id=record.attachment_id,
        expected_sha256=record.source_sha256,
        file_name=_named_file(record.source_path),
    )


def _load_manifest(ports: LedgerEvidencePagePorts, bucket_id: str, document: _StoredDocument) -> Attachment:
    store = ports.attachment_store_factory(bucket_id)
    try:
        manifest = store.load_manifest(document.attachment_id)
    except AttachmentNotFoundError:
        raise LedgerEvidencePageNotFoundError() from None
    except AttachmentValidationError:
        raise LedgerEvidencePageUnreadableError() from None
    if manifest.bucket_id is not None and manifest.bucket_id != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    if manifest.attachment_id != document.attachment_id or manifest.sha256 != document.expected_sha256:
        raise LedgerEvidencePageDigestMismatchError()
    return manifest


def _read_page(
    ports: LedgerEvidencePagePorts,
    bucket_id: str,
    payload: LedgerEvidencePageRequest,
) -> LedgerEvidencePageProjection:
    """Load, verify and draw the requested page in the worker thread."""
    if require_active_bucket_id() != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    if payload.evidence_id is not None:
        document = _evidence_document(ports, bucket_id, payload.evidence_id)
    elif payload.attachment_id is not None:
        document = _StoredDocument(
            attachment_id=payload.attachment_id, expected_sha256=payload.attachment_id, file_name=None
        )
    else:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    manifest = _load_manifest(ports, bucket_id, document)
    file_name = document.file_name
    if payload.attachment_id is not None and manifest.source is AttachmentSource.LOCAL_FILE:
        file_name = _named_file(manifest.source_reference)
    media_type = EvidencePageMediaType.of_declared(manifest.mime_type)
    if media_type is None:
        raise LedgerEvidencePageUnsupportedMediaError()
    renderer = ports.renderer
    if manifest.bytes_size > renderer.max_source_bytes:
        raise LedgerEvidencePageTooLargeError()
    try:
        source = ports.attachment_store_factory(bucket_id).read_bytes(manifest.sha256)
    except AttachmentNotFoundError:
        raise LedgerEvidencePageNotFoundError() from None
    if len(source) > renderer.max_source_bytes:
        raise LedgerEvidencePageTooLargeError()
    if sha256_hex(source) != document.expected_sha256:
        raise LedgerEvidencePageDigestMismatchError()
    rendered = renderer.render(
        source,
        media_type=media_type,
        page=payload.page,
        max_width=payload.max_width,
        max_image_bytes=EVIDENCE_PAGE_MAX_IMAGE_BYTES,
    )
    del source
    if rendered.width > payload.max_width or len(rendered.png) > EVIDENCE_PAGE_MAX_IMAGE_BYTES:
        raise LedgerEvidencePageTooLargeError()
    return LedgerEvidencePageProjection(
        profile_id=payload.profile_id,
        evidence_id=payload.evidence_id,
        attachment_id=manifest.attachment_id,
        media_type=media_type,
        page=payload.page,
        page_count=rendered.page_count,
        width=rendered.width,
        height=rendered.height,
        source_sha256=document.expected_sha256,
        file_name=file_name,
        image_data_url=EVIDENCE_PAGE_IMAGE_URL_PREFIX + base64.b64encode(rendered.png).decode("ascii"),
    )


class LedgerEvidencePageExecutor:
    """Draw one page of one stored document for the active profile."""

    def __init__(self, ports: LedgerEvidencePagePorts) -> None:
        """Bind the evidence catalogue, attachment custody and renderer capabilities."""
        self._ports = ports

    async def execute(
        self,
        request: OperationRequest[LedgerEvidencePageRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Read, verify and draw the page, sealing only the bounded result."""
        payload = request.payload
        bucket_id = _require_worker_identity(request, context)
        await context.events.phase(LEDGER_EVIDENCE_PAGE_OPERATION_DEFINITION_ID)
        await context.events.effect(OperationEffect.NONE)

        async def capture() -> str:
            result = await asyncio.to_thread(_read_page, self._ports, bucket_id, payload)
            wrapped = LedgerEvidencePageExecutionResult(profile_id=payload.profile_id, result=result)
            if len(canonical_json_bytes(result.model_dump(mode="json"))) > _MAX_RESULT_BYTES:
                raise LedgerEvidencePageTooLargeError()
            return await context.operands.put(wrapped, written_at=now())

        return await await_cancellation_complete(capture(), task_name="ledger-evidence-page")


def build_ledger_evidence_page_definition(ports: LedgerEvidencePagePorts) -> OperationDefinition:
    """Declare the exact-profile, no-effect page read."""
    return build_single_phase_definition(
        definition_id=LEDGER_EVIDENCE_PAGE_OPERATION_DEFINITION_ID,
        request_type=LedgerEvidencePageRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=LedgerEvidencePageExecutionResult,
        executor_type=LedgerEvidencePageExecutor,
        build=lambda: LedgerEvidencePageExecutor(ports),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_READ_CAPABILITIES,
    )


def project_evidence_page_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    """Release the drawn page only under its successful, no-effect receipt."""
    if type(result) is not LedgerEvidencePageExecutionResult:
        raise ValueError("invalid evidence page result")
    require_terminal_receipt_match(
        receipt,
        definition_id=LEDGER_EVIDENCE_PAGE_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(result.profile_id)),
        condition=OperationTerminalCondition.SUCCEEDED,
        effect=OperationEffect.NONE,
        message="evidence page read is not bound to its successful receipt",
    )
    return result.result


def build_ledger_evidence_page_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the page read's typed contracts and whole-profile disclosure."""
    if definition.definition_id != LEDGER_EVIDENCE_PAGE_OPERATION_DEFINITION_ID:
        raise ValueError("page registration requires the page definition")
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=LedgerEvidencePageProjection,
        result_projector=project_evidence_page_result,
        access_resolver=lambda request, context: resolve_ledger_request_read_access(
            request,
            context,
            definition_id=LEDGER_EVIDENCE_PAGE_OPERATION_DEFINITION_ID,
            request_type=LedgerEvidencePageRequest,
        ),
    )


__all__ = [
    "LedgerEvidencePageExecutor",
    "build_ledger_evidence_page_definition",
    "build_ledger_evidence_page_registration",
    "project_evidence_page_result",
]
