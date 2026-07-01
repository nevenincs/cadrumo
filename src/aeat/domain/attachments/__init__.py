"""Public facade for content-addressed attachment evidence.

This package owns the immutable :class:`Attachment` manifest and in-memory
:class:`AttachmentCatalogue` records used by ledger and filing evidence flows.
Each manifest is keyed by the stored bytes' SHA-256
(``attachment_id == sha256``) and records :class:`AttachmentKind`,
:class:`AttachmentSource`, the source reference, MIME type, byte size, capture
timestamp, owning bucket, linked transaction/invoice ids, metadata, and notes.
Link-only URI-list manifests are rejected: an attachment evidence record must
represent document bytes, not an external pointer.

Persistence is a protocol boundary. Domain helpers accept an
:class:`AttachmentStoreProtocol`; the concrete
:class:`~aeat.adapters.persistence.storage.AttachmentStore` lives in the
adapter layer and stores encrypted blob rows plus manifest
:class:`~aeat.adapters.persistence.storage.Envelope` rows through
:class:`~aeat.adapters.persistence.storage.SecureObjectRepository` at
``FINANCIAL`` :class:`~aeat.adapters.persistence.storage.SensitivityClass`.
This package does not own a plaintext or on-disk repository implementation.

Service helpers :func:`add_attachment` and :func:`add_attachment_bytes` hash
file or in-memory bytes, write them through the supplied store, build the
manifest, and persist it; :func:`load_attachment` and
:func:`list_attachments` read manifests back through the same protocol.
:class:`DocumentLinkSource` narrows operator doclink channels, but a document
link must be resolved to bytes before :func:`add_attachment_bytes`; there is no
link-only attachment path.

Callers must import public models, errors, enums, protocols, and service
helpers from ``aeat.domain.attachments`` and must not reach into private
underscore modules inside this package.
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
