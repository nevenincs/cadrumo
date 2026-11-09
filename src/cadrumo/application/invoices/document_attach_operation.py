"""Registered exact-profile custody of an invoice's source document.

A received or issued invoice recorded through the Libro de facturas carries no
document until one is attached. The worker reads the file the person chose,
stores its bytes in the profile's encrypted attachment custody and records the
invoice on that attachment's manifest, which is how a confirmed PDF or
structured e-invoice already belongs to its invoice. No frontend computes the
digest, and no path stands in for the document.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from cadrumo_client.contracts.access_refusals import AccessDenialCode

from ...core.async_cleanup import await_cancellation_complete
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect, profile_operation_subject
from ...core.time.clock import now
from ...domain.attachments.errors import AttachmentNotFoundError
from ...domain.attachments.service import link_attachment_invoice
from ..ledger.evidence import MediaKind, admit_evidence_file, ingest_evidence_file
from ..ledger.evidence_port_identity import require_exact_evidence_ports
from ..ledger.read_access import resolve_ledger_request_commit_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES
from ..operations.execution_actor import OperationExecutionCallerReader, execution_actor_label
from ..operations.models import OperationRequest, OperationTerminalReceipt, require_succeeded_terminal_receipt
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..operations.subject_reference import OperationSubjectReferenceV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .catalogue_lifecycle import resolve_catalogue_invoice

if TYPE_CHECKING:
    from ...domain.attachments.protocols import AttachmentStoreProtocol
    from ..ledger.evidence_ports import LedgerEvidencePorts
    from .catalogue_reads_ports import InvoiceCatalogueReader

INVOICE_DOCUMENT_ATTACH_OPERATION_DEFINITION_ID = "ledger.invoice.attach_document"

_PERSON_FRONTEND_ACTOR = "cli"
"""The custody label of a document a person's frontend attaches; an automation's is derived from its session."""
_EvidencePath = Annotated[str, Field(min_length=1, max_length=4_096)]


@dataclass(frozen=True, slots=True)
class InvoiceDocumentAttachPorts:
    """Attachment custody, the invoice catalogue and the manifest store of one bucket."""

    evidence: LedgerEvidencePorts
    invoice_reader: InvoiceCatalogueReader
    attachment_store: AttachmentStoreProtocol


class InvoiceDocumentAttachPortsFactory(Protocol):
    """Construct the complete document-attach bundle for one profile bucket."""

    def __call__(self, *, bucket_id: str) -> InvoiceDocumentAttachPorts:
        """Return every capability bound to ``bucket_id``."""
        ...


class InvoiceDocumentAttachRequest(BaseModel):
    """One invoice and the document the person chose for it, named only so the worker can read it."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    invoice_id: str = Field(min_length=1, max_length=64)
    source_path: _EvidencePath
    source_directory: _EvidencePath


class InvoiceDocumentAttachProjection(BaseModel):
    """The invoice and the document now recorded as its source."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    profile_id: UUID
    invoice_id: str = Field(min_length=1, max_length=64)
    attachment_id: ContentDigest
    already_linked: bool


class InvoiceDocumentAttachExecutionResult(BaseModel):
    """Private result kept in the worker's encrypted operation record."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    result: InvoiceDocumentAttachProjection

    @model_validator(mode="after")
    def _names_a_whole_invoice(self) -> InvoiceDocumentAttachExecutionResult:
        if not self.result.invoice_id.strip():
            raise ValueError("an attached document names its invoice")
        return self


class InvoiceDocumentAttachExecutor:
    """Place one document in exact-profile custody and record it as an invoice's source."""

    def __init__(
        self,
        ports_factory: InvoiceDocumentAttachPortsFactory,
        *,
        execution_caller_reader: OperationExecutionCallerReader | None = None,
    ) -> None:
        """Bind the exact-profile capability factory and the session host's caller reader."""
        self._ports_factory = ports_factory
        self._execution_caller_reader = execution_caller_reader

    async def execute(
        self,
        request: OperationRequest[InvoiceDocumentAttachRequest],
        context: OperationExecutorContext,
    ) -> str:
        """Refuse an unknown invoice or unkept file before any write, then store and link."""
        payload = request.payload
        bucket_id = str(payload.profile_id)
        if request.definition_id != INVOICE_DOCUMENT_ATTACH_OPERATION_DEFINITION_ID:
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        require_operation_profile(request, context, payload.profile_id)
        await context.events.phase(INVOICE_DOCUMENT_ATTACH_OPERATION_DEFINITION_ID)
        actor = execution_actor_label(self._execution_caller_reader, context, supplied=_PERSON_FRONTEND_ACTOR)

        def preflight() -> tuple[InvoiceDocumentAttachPorts, str, tuple[Path, MediaKind]]:
            ports = self._ports_factory(bucket_id=bucket_id)
            require_exact_evidence_ports(ports.evidence, bucket_id=bucket_id)
            # Both refusals land before custody is touched, so a refused attach changed nothing.
            invoice = resolve_catalogue_invoice(ports.invoice_reader.load(), payload.invoice_id)
            admitted = admit_evidence_file(payload.source_path, Path(payload.source_directory))
            return ports, invoice.invoice_id, admitted

        def store_and_link(
            ports: InvoiceDocumentAttachPorts, invoice_id: str, admitted: tuple[Path, MediaKind]
        ) -> tuple[ContentDigest, bool]:
            digest = ingest_evidence_file(
                ports=ports.evidence,
                bucket_id=bucket_id,
                admitted=admitted,
                now=now(),
                actor=actor,
            )
            try:
                already = invoice_id in ports.attachment_store.load_manifest(digest).linked_invoice_ids
            except AttachmentNotFoundError:
                already = False
            link_attachment_invoice(ports.attachment_store, attachment_id=digest, invoice_id=invoice_id)
            return digest, already

        async def capture() -> str:
            ports, invoice_id, admitted = await asyncio.to_thread(preflight)
            async with context.cancellation.irreversible_section():
                # The bytes and their manifest are durable once ingestion starts.
                await context.events.effect(OperationEffect.UNKNOWN)
                digest, already = await asyncio.to_thread(store_and_link, ports, invoice_id, admitted)
                await context.events.effect(OperationEffect.UPDATED)
                return await context.operands.put(
                    InvoiceDocumentAttachExecutionResult(
                        result=InvoiceDocumentAttachProjection(
                            profile_id=payload.profile_id,
                            invoice_id=invoice_id,
                            attachment_id=digest,
                            already_linked=already,
                        )
                    ),
                    written_at=now(),
                )

        return await await_cancellation_complete(capture(), task_name="ledger-invoice-attach-document")


def _project_result(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    if type(result) is not InvoiceDocumentAttachExecutionResult:
        raise ValueError("invalid invoice document attach result")
    require_succeeded_terminal_receipt(
        receipt,
        definition_id=INVOICE_DOCUMENT_ATTACH_OPERATION_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(result.result.profile_id)),
        effect=OperationEffect.UPDATED,
        message="invoice document attach has an incompatible terminal receipt",
    )
    return result.result


def build_invoice_document_attach_definition(
    ports_factory: InvoiceDocumentAttachPortsFactory,
    *,
    execution_caller_reader: OperationExecutionCallerReader | None = None,
) -> OperationDefinition:
    """Declare one bounded exact-profile custody operation for an invoice's document.

    The attachment is addressed by its content and the invoice link is a set
    member, so repeating the same document is a no-op without an idempotency key.
    """
    return build_single_phase_definition(
        definition_id=INVOICE_DOCUMENT_ATTACH_OPERATION_DEFINITION_ID,
        request_type=InvoiceDocumentAttachRequest,
        subject_reference=OperationSubjectReferenceV1.profile(),
        result_type=InvoiceDocumentAttachExecutionResult,
        executor_type=InvoiceDocumentAttachExecutor,
        build=lambda: InvoiceDocumentAttachExecutor(ports_factory, execution_caller_reader=execution_caller_reader),
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_UPDATE_CAPABILITIES,
        public_error_detail=True,
    )


def resolve_invoice_document_attach_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile tax-value disclosure and COMMIT, as adding any ledger document does."""
    return resolve_ledger_request_commit_access(
        request,
        context,
        definition_id=INVOICE_DOCUMENT_ATTACH_OPERATION_DEFINITION_ID,
        request_type=InvoiceDocumentAttachRequest,
    )


def build_invoice_document_attach_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Bind bounded schemas, whole-profile access and exact receipt projection."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=InvoiceDocumentAttachProjection,
        result_projector=_project_result,
        access_resolver=resolve_invoice_document_attach_access,
    )


__all__ = [
    "INVOICE_DOCUMENT_ATTACH_OPERATION_DEFINITION_ID",
    "InvoiceDocumentAttachExecutionResult",
    "InvoiceDocumentAttachExecutor",
    "InvoiceDocumentAttachPorts",
    "InvoiceDocumentAttachPortsFactory",
    "InvoiceDocumentAttachProjection",
    "InvoiceDocumentAttachRequest",
    "build_invoice_document_attach_definition",
    "build_invoice_document_attach_registration",
    "resolve_invoice_document_attach_access",
]
