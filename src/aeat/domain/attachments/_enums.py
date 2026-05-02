"""Closed enumerations for attachment records.

Defines the closed taxonomy used by :class:`aeat.domain.attachments.Attachment`
to classify what an attachment is (:class:`AttachmentKind`) and where it came
from (:class:`AttachmentSource`).
"""

from __future__ import annotations

from enum import StrEnum


class AttachmentKind(StrEnum):
    """Closed taxonomy of supported attachment document kinds.

    Used by :attr:`aeat.domain.attachments.Attachment.kind` to disambiguate
    payload semantics for downstream renderers, validators, and reporting.

    Attributes:
        INVOICE_PDF: Vendor or customer invoice in PDF form.
        RECEIPT_IMAGE: Photographed or scanned receipt.
        EMAIL_MESSAGE: Captured email message body or eml export.
        DRIVE_DOCUMENT: Document captured from Google Drive.
        CONTRACT_PDF: Contract or agreement in PDF form.
        BANK_STATEMENT: Bank-issued statement document.
        METADATA_BLOB: Opaque metadata payload that supplements another record.
        OTHER: Catch-all for documents that do not fit the above categories.
    """

    INVOICE_PDF = "INVOICE_PDF"
    RECEIPT_IMAGE = "RECEIPT_IMAGE"
    EMAIL_MESSAGE = "EMAIL_MESSAGE"
    DRIVE_DOCUMENT = "DRIVE_DOCUMENT"
    CONTRACT_PDF = "CONTRACT_PDF"
    BANK_STATEMENT = "BANK_STATEMENT"
    METADATA_BLOB = "METADATA_BLOB"
    OTHER = "OTHER"


class AttachmentSource(StrEnum):
    """Closed taxonomy of channels an attachment can originate from.

    Used by :attr:`aeat.domain.attachments.Attachment.source` to record where
    bytes were captured from for provenance and re-fetch logic.

    Attributes:
        LOCAL_FILE: A file read from the local filesystem.
        GMAIL: A message body or attachment captured via the Gmail API.
        GOOGLE_DRIVE: A document fetched from Google Drive.
        URL: A document downloaded from an arbitrary URL.
        INLINE: Bytes provided inline rather than fetched from a channel.
    """

    LOCAL_FILE = "LOCAL_FILE"
    GMAIL = "GMAIL"
    GOOGLE_DRIVE = "GOOGLE_DRIVE"
    URL = "URL"
    INLINE = "INLINE"
