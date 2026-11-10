"""Registered-executor conformance scenario for attaching a document to a catalogue invoice."""

from __future__ import annotations

import hashlib

from ...application.invoices.document_attach_operation import (
    INVOICE_DOCUMENT_ATTACH_OPERATION_DEFINITION_ID,
    InvoiceDocumentAttachProjection,
    InvoiceDocumentAttachRequest,
)
from ...core.operations import OperationEffect, OperationTerminalCondition, profile_operation_subject
from ..adapter_composition_ports import build_attachment_store
from .conformance_family_contract import (
    ConformanceFamily,
    ConformanceFamilyContext,
    ConformanceOutcome,
    ConformancePreparation,
    RegisteredExecutorConformanceCase,
)
from .registered_executor_seeding_support import seed_conformance_invoice

_DOCUMENT_NAME = "factura.pdf"
_DOCUMENT = b"%PDF-1.4\n% synthetic conformance factura\n%%EOF\n"


def _prepare_attach(context: ConformanceFamilyContext) -> ConformancePreparation:
    bucket_id = str(context.profile_id)
    invoice = seed_conformance_invoice(context.profile_id)
    (context.input_root / _DOCUMENT_NAME).write_bytes(_DOCUMENT)
    attachments = build_attachment_store(bucket_id)
    assert tuple(attachments.iter_manifests()) == ()

    def verify(outcome: ConformanceOutcome) -> None:
        projection = outcome.resolve_result(InvoiceDocumentAttachProjection)
        assert projection.profile_id == context.profile_id
        assert projection.invoice_id == invoice.invoice_id
        assert projection.already_linked is False
        # The custody key is the document's own content digest.
        assert projection.attachment_id == hashlib.sha256(_DOCUMENT).hexdigest()
        (manifest,) = tuple(build_attachment_store(bucket_id).iter_manifests())
        assert manifest.linked_invoice_ids == (invoice.invoice_id,)

    return ConformancePreparation(
        subject_ref=profile_operation_subject(bucket_id),
        request=InvoiceDocumentAttachRequest(
            profile_id=context.profile_id,
            invoice_id=invoice.invoice_id,
            source_path=_DOCUMENT_NAME,
            source_directory=str(context.input_root),
        ),
        verify=verify,
    )


def _prepare(context: ConformanceFamilyContext) -> ConformancePreparation:
    if context.definition.definition_id != INVOICE_DOCUMENT_ATTACH_OPERATION_DEFINITION_ID:
        raise AssertionError(f"no invoice document conformance scenario for {context.definition.definition_id}")
    return _prepare_attach(context)


INVOICE_DOCUMENT_ATTACH_CONFORMANCE_FAMILY = ConformanceFamily(
    cases=(
        RegisteredExecutorConformanceCase(
            INVOICE_DOCUMENT_ATTACH_OPERATION_DEFINITION_ID,
            OperationTerminalCondition.SUCCEEDED,
            OperationEffect.UPDATED,
            (INVOICE_DOCUMENT_ATTACH_OPERATION_DEFINITION_ID,),
        ),
    ),
    prepare=_prepare,
)
