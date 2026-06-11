"""Content-addressed attachment domain for the transaction evidence layer.

This subpackage owns the attachment evidence model: supporting documents
(invoice PDFs, Gmail messages, Drive documents, receipts, contracts,
metadata blobs) wrapped as immutable manifests linked to transactions
and/or invoices. The link makes every casilla value the project justifies
traceable back to physical evidence.

Domain models, errors, and the on-disk repository live here, alongside
the orchestration helpers :func:`add_attachment`, :func:`list_attachments`,
and :func:`load_attachment` exported from :mod:`._service`.

The exported surface comprises :class:`Attachment`, :class:`AttachmentCatalogue`,
:class:`AttachmentStoreProtocol`, the :class:`AttachmentKind` and
:class:`AttachmentSource` enums, and the :exc:`AttachmentError` family.
"""

from __future__ import annotations

from ._enums import AttachmentKind, AttachmentSource, DocumentLinkSource
from ._errors import (
    AttachmentError,
    AttachmentNotFoundError,
    AttachmentPersistenceError,
    AttachmentValidationError,
)
from ._models import Attachment, AttachmentCatalogue
from ._protocols import AttachmentStoreProtocol
from ._service import add_attachment, add_attachment_bytes, list_attachments, load_attachment

__all__ = [
    "Attachment",
    "AttachmentCatalogue",
    "AttachmentError",
    "AttachmentKind",
    "AttachmentNotFoundError",
    "AttachmentPersistenceError",
    "AttachmentSource",
    "AttachmentStoreProtocol",
    "AttachmentValidationError",
    "DocumentLinkSource",
    "add_attachment",
    "add_attachment_bytes",
    "list_attachments",
    "load_attachment",
]
