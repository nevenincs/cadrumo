"""Closed enumerations for attachment records.

Defines the closed taxonomy used by :class:`domain.attachments.models.Attachment`
to classify what an attachment is (:class:`AttachmentKind`) and where it came
from (:class:`AttachmentSource`).
"""

from __future__ import annotations

from enum import StrEnum


class AttachmentKind(StrEnum):
    """Closed taxonomy of supported attachment document kinds.

    Used by :attr:`domain.attachments.models.Attachment.kind` to disambiguate
    payload semantics for downstream renderers, validators, and reporting.

    Attributes:
        INVOICE_PDF: Vendor or customer invoice in PDF form.
        RECEIPT_IMAGE: Photographed or scanned receipt.
        EMAIL_MESSAGE: Captured email message body or eml export.
        DRIVE_DOCUMENT: Document captured from Google Drive.
        CONTRACT_PDF: Contract or agreement in PDF form.
        BANK_STATEMENT: Bank-issued statement document.
        AEAT_NOTIFICATION_PDF: The document AEAT served behind a notification's
            comparecencia — a sanción, liquidación or requerimiento act. It is
            named rather than folded into ``OTHER`` because it is the only kind
            here the taxpayer did not supply: it is an act of the tax authority
            against them, and its custody record is what later evidences what
            was served and when.
        METADATA_BLOB: Opaque metadata payload that supplements another record.
        M303_EXONERADO_390_APPLICABILITY_ATTESTATION: Canonical operator
            attestation of one Modelo 390 applicability coordinate.
        OTHER: Catch-all for documents that do not fit the above categories.
    """

    INVOICE_PDF = "INVOICE_PDF"
    RECEIPT_IMAGE = "RECEIPT_IMAGE"
    EMAIL_MESSAGE = "EMAIL_MESSAGE"
    DRIVE_DOCUMENT = "DRIVE_DOCUMENT"
    CONTRACT_PDF = "CONTRACT_PDF"
    BANK_STATEMENT = "BANK_STATEMENT"
    AEAT_NOTIFICATION_PDF = "AEAT_NOTIFICATION_PDF"
    METADATA_BLOB = "METADATA_BLOB"
    M303_EXONERADO_390_APPLICABILITY_ATTESTATION = "M303_EXONERADO_390_APPLICABILITY_ATTESTATION"
    OTHER = "OTHER"


class AttachmentSource(StrEnum):
    """Closed taxonomy of channels an attachment can originate from.

    Used by :attr:`domain.attachments.models.Attachment.source` to record where
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
