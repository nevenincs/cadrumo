"""Public surface for the content-addressed attachment domain.

This subpackage implements the attachment evidence layer for Track B's
Transaction Data Pipeline (TDP step T3 — see issue #76 and the EPIC at
issue #104). Attachments wrap supporting documents — invoice PDFs, Gmail
messages, Drive documents, receipts, contracts, metadata blobs — and link
them to transactions and/or invoices so every casilla value the project
eventually justifies can be traced to physical evidence.

Domain models, errors, and the store live here. Orchestration helpers
(``add_attachment``, ``list_attachments``, ``load_attachment``) are in
``aeat.application.attachments``.
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
from ._service import add_attachment, list_attachments, load_attachment
from ._store import AttachmentStore

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
    "add_attachment",
    "list_attachments",
    "load_attachment",
]
