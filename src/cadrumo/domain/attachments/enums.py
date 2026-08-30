"""Closed enumerations for attachment records.

Defines the closed taxonomy used by :class:`domain.attachments.Attachment`
to classify what an attachment is (:class:`AttachmentKind`) and where it came
from (:class:`AttachmentSource`).
"""

from __future__ import annotations

from enum import StrEnum


class AttachmentKind(StrEnum):
    """Closed taxonomy of supported attachment document kinds.

    Used by :attr:`domain.attachments.Attachment.kind` to disambiguate
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
    OTHER = "OTHER"


class AttachmentSource(StrEnum):
    """Closed taxonomy of channels an attachment can originate from.

    Used by :attr:`domain.attachments.Attachment.source` to record where
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


class DocumentLinkSource(StrEnum):
    """Channels that can back an operator-recorded *document link*.

    A document link records a reference to a document held elsewhere (a Gmail
    message, a Drive document, an arbitrary URL); it never carries local bytes.
    The full :class:`AttachmentSource` taxonomy also includes ``LOCAL_FILE`` and
    ``INLINE``, which name byte-bearing captures that are not link sources. The
    ``aeat app ledger doclink --source`` option advertises exactly this narrowed
    set so the choices it shows match the sources its handler accepts. Each member's
    value equals the matching :class:`AttachmentSource` member's value, so
    :meth:`to_attachment_source` is a total mapping.

    Attributes:
        GMAIL: A message captured via the Gmail API.
        GOOGLE_DRIVE: A document fetched from Google Drive.
        URL: A document referenced by an arbitrary URL.
    """

    GMAIL = "GMAIL"
    GOOGLE_DRIVE = "GOOGLE_DRIVE"
    URL = "URL"

    def to_attachment_source(self) -> AttachmentSource:
        """Map a document-link source to its :class:`AttachmentSource` member."""
        return AttachmentSource(self.value)
