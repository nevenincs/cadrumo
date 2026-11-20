"""The single refusal for evidence bytes that match no readable document shape.

Evidence is admitted by what its bytes are, never by its file name or declared
MIME label. Both the add path (before any custody write) and the read path (after
custody) ask the same question of the same injected probe and refuse with the
same typed verdict, so a document the reader would refuse can never be stored as
evidence in the first place.

This module imports no persistence and none of the evidence record types, so the
add service and the read-path resolver can both depend on it without a cycle.
"""

from __future__ import annotations

from ...core.document_shape import DocumentShape
from .evidence_errors import PurchaseInvoiceEvidenceInputError
from .evidence_input_ports import EvidenceDocumentShapeProbe
from .preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict

__all__ = ["require_readable_document_shape"]


def require_readable_document_shape(
    data: bytes,
    *,
    mime_type: str,
    probe: EvidenceDocumentShapeProbe,
) -> DocumentShape:
    """Return the shape of ``data``, refusing bytes that match no readable document shape.

    :attr:`DocumentShape.UNKNOWN` is the probe's own "never guessed at, always
    refused" verdict, so refusing on it moves the authority to the bytes. An
    empty payload, a PDF header followed by garbage and an unrecognised
    container are all ``UNKNOWN``.

    ``mime_type`` appears in the message only as the operator-visible breadcrumb
    for the document being judged (the label the producer or the file's extension
    gave it); it decides nothing.
    """
    document_shape = probe(data)
    if document_shape is DocumentShape.UNKNOWN:
        raise PurchaseInvoiceEvidenceInputError(
            f"evidence bytes (labelled {mime_type!r}) match no readable document shape; "
            "only PDF, structured XML and image evidence can be read",
            translated_message="errors.refused.refused_ledger_evidence_input",
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.EVIDENCE_BYTES_READABLE,
                facts={"document_shape_recognized": False},
            ),
        )
    return document_shape
