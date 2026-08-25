"""Public facade for content-addressed attachment evidence.

This package owns the immutable :class:`Attachment` manifest and in-memory
:class:`AttachmentCatalogue` records used by ledger and filing evidence flows.
Each manifest is keyed by the stored bytes' SHA-256
(``attachment_id == sha256``) and records :class:`AttachmentKind`,
:class:`AttachmentSource`, the source reference, MIME type, byte size, capture
timestamp, owning bucket, linked transaction/invoice ids, metadata, and notes.
Link-only URI-list manifests are rejected: an attachment evidence record must
represent document bytes, not an external pointer.

This package owns BYTE CUSTODY and nothing else. An :class:`Attachment` records
what the bytes are and where they came from; it never carries a fiscal figure
(no supplier, invoice number, taxable base, IVA rate, or IVA amount) and is
immutable once written, because its identity IS the byte digest. A record that
asserts fiscal figures about a document is the separate middle evidence tier
:class:`application.ledger.evidence.PurchaseInvoiceEvidence`, which stores its bytes here
and references them by ``attachment_id``; a confirmed fiscal document is
:class:`domain.invoices.Invoice`. Read those two before adding a field here: a
figure belongs on one of them, never on the byte manifest.

Persistence is a protocol boundary. Domain helpers accept an
:class:`AttachmentStoreProtocol`; the concrete
:class:`adapters.persistence.storage.AttachmentStore` lives in the
adapter layer and stores encrypted blob rows plus manifest
:class:`adapters.persistence.storage.Envelope` rows through
:class:`adapters.persistence.storage.SecureObjectRepository` at ``FINANCIAL``
:class:`adapters.persistence.storage.SensitivityClass`.
This package does not own a plaintext or on-disk repository implementation.

The service helper :func:`add_attachment` accepts one typed
:class:`AttachmentIngestionRequest` plus either :class:`AttachmentFileContent`
or :class:`AttachmentBytesContent`, hashes the supplied content, writes it
through the supplied store, builds the manifest, and persists it;
:func:`load_attachment` and :func:`list_attachments` read manifests back
through the same protocol.
:func:`link_attachment_invoice` and :func:`link_attachment_transaction`
re-persist an already-stored manifest with an
invoice id appended to :attr:`Attachment.linked_invoice_ids`, for the case
where the invoice is minted only after the evidence is already captured
(e.g. confirming an extracted invoice draft).
:class:`DocumentLinkSource` narrows operator doclink channels, but a document
link must be resolved to :class:`AttachmentBytesContent` before
:func:`add_attachment`; there is no link-only attachment path.

Callers must import public models, errors, enums, protocols, and service
helpers from ``cadrumo.domain.attachments`` and must not reach into private
underscore modules inside this package.

See Also:
    :mod:`application.ledger`
        Ledger lifecycle that verifies attachment existence, byte custody, and
        bucket ownership before a transaction claims attachment evidence.
    :mod:`domain.invoices`
        The confirmed fiscal document tier, whose counterparty, totals, currency,
        and lines are required — the rung above the optional-metadata
        purchase-invoice evidence record, which itself lives in
        :mod:`application.ledger`. Neither models byte custody; both delegate it
        here.
    :mod:`application.aggregation`
        Calculation-source and evidence-advisory surfaces that consume
        transaction evidence links without reading plaintext files from disk.
    :mod:`adapters.persistence.storage`
        Secure-object and encrypted blob storage that implements
        :class:`AttachmentStoreProtocol`.
"""

from __future__ import annotations

from ._enums import AttachmentKind, AttachmentSource, DocumentLinkSource
from ._errors import (
    AttachmentError,
    AttachmentNotFoundError,
    AttachmentPersistenceError,
    AttachmentValidationError,
)
from ._models import Attachment, AttachmentCatalogue, is_link_only_mime_type, normalize_media_type
from ._protocols import AttachmentStoreProtocol
from ._service import (
    AttachmentBytesContent,
    AttachmentFileContent,
    AttachmentIngestionRequest,
    add_attachment,
    link_attachment_invoice,
    link_attachment_transaction,
    list_attachments,
    load_attachment,
)

__all__ = [
    "Attachment",
    "AttachmentBytesContent",
    "AttachmentCatalogue",
    "AttachmentError",
    "AttachmentFileContent",
    "AttachmentIngestionRequest",
    "AttachmentKind",
    "AttachmentNotFoundError",
    "AttachmentPersistenceError",
    "AttachmentSource",
    "AttachmentStoreProtocol",
    "AttachmentValidationError",
    "DocumentLinkSource",
    "add_attachment",
    "is_link_only_mime_type",
    "link_attachment_invoice",
    "link_attachment_transaction",
    "list_attachments",
    "load_attachment",
    "normalize_media_type",
]
