"""In-memory evidence-input representation for on-host LLM reading.

A transient, in-process container for the decrypted bytes of a transaction's
attached evidence (a purchase invoice or a linked attachment), read from secure
storage so an on-host reader -- the in-tree text-layer or a local vision model --
can consume it.

CRITICAL (``sensitive-financial-data-secure-storage-only``): this object holds
decrypted ``FINANCIAL`` bytes in process memory ONLY. It MUST NEVER be persisted,
serialized to disk, written to a temp file, embedded in a persisted document, or
logged. It carries no JSON serializer; :meth:`EvidenceInput.model_dump` and
:meth:`EvidenceInput.model_dump_json` are overridden to raise so a stray
persistence call fails loudly rather than leaking bytes out of secure storage. The
raw ``data`` field is excluded from ``repr`` for the same reason.
"""

from __future__ import annotations

import hashlib
from typing import Never, Self, override

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ...adapters.persistence.storage.attachment import AttachmentStore
from ...core.config import Settings
from ._evidence import MediaKind, PurchaseInvoiceEvidence, PurchaseInvoiceEvidenceInputError

__all__ = [
    "EvidenceInput",
    "cloud_evidence_read_permitted",
    "resolve_attachment_evidence_input",
    "resolve_purchase_invoice_evidence_input",
]


def cloud_evidence_read_permitted(settings: Settings, *, acknowledged: bool) -> bool:
    """Whether an off-host cloud evidence read is permitted for THIS invocation.

    On-host reading is always allowed and is the default; this gate governs only
    the cloud exception. A cloud read is permitted only when the deployment has
    opted in (``aeat_evidence_cloud_upload_permitted``), the deployment is not a
    gestor/professional deployment (``aeat_evidence_gestor_mode`` is the absolute
    bar), AND the operator acknowledged the upload for this specific invocation.
    The acknowledgement is never sticky -- it must be re-affirmed each time
    (sensitive-financial-data-secure-storage-only).

    Args:
        settings: Resolved deployment settings carrying the consent posture.
        acknowledged: Whether the operator acknowledged the off-host upload for
            this invocation.

    Returns:
        ``True`` only when all three conditions hold; ``False`` otherwise.
    """
    if settings.aeat_evidence_gestor_mode:
        return False
    if not settings.aeat_evidence_cloud_upload_permitted:
        return False
    return acknowledged


class EvidenceInput(BaseModel):
    """Transient in-memory evidence bytes plus the provenance needed to cite them.

    Built by the resolver from evidence already held in secure storage. The bytes
    live only for the duration of a single on-host read; this model is never
    persisted (see the module docstring and the overridden dump methods).

    Attributes:
        media_kind: Whether the bytes are a PDF or an image.
        mime_type: Concrete MIME type of the bytes (e.g. ``application/pdf``).
        data: The decrypted evidence bytes, in memory only. Excluded from ``repr``.
        content_sha256: 64-character lowercase hex SHA-256 of :attr:`data`; the
            content address the bytes were read under. Enforced to match ``data``.
        evidence_id: Originating purchase-invoice ``evidence_id`` when the bytes
            came from a :class:`PurchaseInvoiceEvidence` record, else ``None``.
        attachment_id: Originating ``attachment_id`` when the bytes came from an
            :class:`Attachment`, else ``None``.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    media_kind: MediaKind
    mime_type: str = Field(min_length=1)
    data: bytes = Field(repr=False)
    content_sha256: str = Field(min_length=64, max_length=64)
    evidence_id: str | None = None
    attachment_id: str | None = None

    @model_validator(mode="after")
    def _verify_content_address(self) -> Self:
        """Reject bytes whose digest does not match the declared content address."""
        if not self.data:
            raise ValueError("EvidenceInput.data must not be empty")
        digest = hashlib.sha256(self.data).hexdigest()
        if digest != self.content_sha256:
            raise ValueError("EvidenceInput.content_sha256 must equal sha256(data)")
        if self.evidence_id is None and self.attachment_id is None:
            raise ValueError("EvidenceInput must carry an evidence_id or an attachment_id for provenance")
        return self

    @override
    def model_dump(self, *args: object, **kwargs: object) -> Never:  # pyright: ignore[reportIncompatibleMethodOverride]  # reason: deliberate persistence tripwire
        """Refuse serialization -- decrypted FINANCIAL bytes must never be persisted."""
        raise NotImplementedError(
            "EvidenceInput must never be serialized or persisted; it holds decrypted "
            "FINANCIAL bytes in memory only (sensitive-financial-data-secure-storage-only)."
        )

    @override
    def model_dump_json(self, *args: object, **kwargs: object) -> Never:  # pyright: ignore[reportIncompatibleMethodOverride]  # reason: deliberate persistence tripwire
        """Refuse JSON serialization -- decrypted FINANCIAL bytes must never be persisted."""
        raise NotImplementedError(
            "EvidenceInput must never be serialized or persisted; it holds decrypted "
            "FINANCIAL bytes in memory only (sensitive-financial-data-secure-storage-only)."
        )


def _media_kind_from_mime(mime_type: str) -> MediaKind:
    """Map a stored attachment MIME type to the reader's ``MediaKind``."""
    if mime_type == "application/pdf":
        return MediaKind.PDF
    if mime_type.startswith("image/"):
        return MediaKind.IMAGE
    raise PurchaseInvoiceEvidenceInputError(
        f"evidence media type {mime_type!r} cannot be read; only PDF and image evidence is supported",
        suggestion="aeat app ledger evidence list",
    )


def resolve_attachment_evidence_input(attachment_id: str, *, store: AttachmentStore) -> EvidenceInput:
    """Read a linked attachment's bytes from secure storage into an ``EvidenceInput``.

    Loads the attachment manifest and its encrypted blob from the
    :class:`AttachmentStore` (active bucket) into memory. No file is written.

    Args:
        attachment_id: Content-addressed id of the linked attachment.
        store: Attachment store bound to the operation's secure-storage bucket.

    Returns:
        :class:`EvidenceInput`: In-memory bytes plus provenance, for an on-host read.
    """
    manifest = store.load_manifest(attachment_id)
    data = store.read_bytes(manifest.sha256)
    return EvidenceInput(
        media_kind=_media_kind_from_mime(manifest.mime_type),
        mime_type=manifest.mime_type,
        data=data,
        content_sha256=manifest.sha256,
        attachment_id=manifest.attachment_id,
    )


def resolve_purchase_invoice_evidence_input(
    evidence: PurchaseInvoiceEvidence, *, store: AttachmentStore
) -> EvidenceInput:
    """Read a purchase-invoice evidence record's bytes from secure storage.

    Reads via the record's ``attachment_id`` -- the in-store byte home written at
    ``add`` time. A record without an ``attachment_id`` predates that contract and
    has no in-store bytes to read; this raises rather than falling back to the
    cleartext ``source_path`` (sensitive-financial-data-secure-storage-only).

    Args:
        evidence: The purchase-invoice evidence record.
        store: Attachment store bound to the operation's secure-storage bucket.

    Returns:
        :class:`EvidenceInput`: In-memory bytes plus provenance, for an on-host read.

    Raises:
        PurchaseInvoiceEvidenceInputError: When the record carries no ``attachment_id``.
    """
    if evidence.attachment_id is None:
        raise PurchaseInvoiceEvidenceInputError(
            f"evidence {evidence.evidence_id!r} has no in-store attachment; its bytes are not in secure storage",
            suggestion="re-add the evidence so its bytes are stored in the encrypted attachment store",
        )
    manifest = store.load_manifest(evidence.attachment_id)
    data = store.read_bytes(manifest.sha256)
    return EvidenceInput(
        media_kind=_media_kind_from_mime(manifest.mime_type),
        mime_type=manifest.mime_type,
        data=data,
        content_sha256=manifest.sha256,
        evidence_id=evidence.evidence_id,
        attachment_id=manifest.attachment_id,
    )
