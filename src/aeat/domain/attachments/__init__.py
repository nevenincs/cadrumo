"""Content-addressed attachment domain for the transaction evidence layer.

This subpackage owns the attachment evidence model: supporting documents
(invoice PDFs, Gmail messages, Drive documents, receipts, contracts,
metadata blobs) wrapped as immutable manifests linked to transactions
and/or invoices. The link makes every casilla value the project justifies
traceable back to physical evidence.

Domain models, errors, and the on-disk repository live here. Orchestration
helpers — :func:`aeat.application.attachments.add_attachment`,
:func:`aeat.application.attachments.list_attachments`,
:func:`aeat.application.attachments.load_attachment` — live in
:mod:`aeat.application.attachments`.

The exported surface comprises :class:`Attachment`, :class:`AttachmentCatalogue`,
:class:`AttachmentStore`, the :class:`AttachmentKind` and :class:`AttachmentSource`
enums, and the :exc:`AttachmentError` family.
"""

from __future__ import annotations

from ._enums import AttachmentKind, AttachmentSource
from ._errors import (
    AttachmentError,
    AttachmentNotFoundError,
    AttachmentPersistenceError,
    AttachmentValidationError,
)
from ._models import Attachment, AttachmentCatalogue
from ._repository import AttachmentStore

__all__ = [
    "Attachment",
    "AttachmentCatalogue",
    "AttachmentError",
    "AttachmentKind",
    "AttachmentNotFoundError",
    "AttachmentPersistenceError",
    "AttachmentSource",
    "AttachmentStore",
    "AttachmentValidationError",
]
