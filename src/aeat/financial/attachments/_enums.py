"""Closed enumerations for attachment records."""

from __future__ import annotations

from enum import StrEnum


class AttachmentKind(StrEnum):
    """Supported attachment document kinds."""

    INVOICE_PDF = "INVOICE_PDF"
    RECEIPT_IMAGE = "RECEIPT_IMAGE"
    EMAIL_MESSAGE = "EMAIL_MESSAGE"
    DRIVE_DOCUMENT = "DRIVE_DOCUMENT"
    CONTRACT_PDF = "CONTRACT_PDF"
    BANK_STATEMENT = "BANK_STATEMENT"
    METADATA_BLOB = "METADATA_BLOB"
    OTHER = "OTHER"


class AttachmentSource(StrEnum):
    """Supported attachment source channels."""

    LOCAL_FILE = "LOCAL_FILE"
    GMAIL = "GMAIL"
    GOOGLE_DRIVE = "GOOGLE_DRIVE"
    URL = "URL"
    INLINE = "INLINE"
