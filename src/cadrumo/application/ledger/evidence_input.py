"""In-memory evidence-input representation for on-host LLM reading.

A transient, in-process container for the decrypted bytes of a transaction's
attached evidence (a purchase invoice or a linked attachment), read from secure
storage so an on-host reader -- the in-tree text-layer or a local vision model --
can consume it.

CRITICAL (``sensitive-financial-data-secure-storage-only``): this object holds
decrypted ``FINANCIAL`` bytes in process memory ONLY. It MUST NEVER be persisted,
serialized to disk, written to a temp file, embedded in a persisted document, or
logged. It carries no JSON serializer; ``EvidenceInput.model_dump`` and
``EvidenceInput.model_dump_json`` are overridden to raise so a stray
persistence call fails loudly rather than leaking bytes out of secure storage. The
raw ``data`` field is excluded from ``repr`` for the same reason.
"""

from __future__ import annotations

from typing import Never, Self, SupportsIndex, override

from pydantic import BaseModel, Field, model_serializer, model_validator

from ...core.document_shape import DocumentShape
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.hashing import sha256_hex
from ...core.identity import ContentDigest
from ...domain.attachments.protocols import AttachmentStoreProtocol
from .evidence import PurchaseInvoiceEvidence, PurchaseInvoiceEvidenceInputError
from .preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict

__all__ = [
    "EvidenceInput",
    "resolve_attachment_evidence_input",
    "resolve_purchase_invoice_evidence_input",
]


_REFUSAL_MESSAGE = (
    "EvidenceInput must never be serialized, iterated, or persisted; it holds decrypted "
    "FINANCIAL bytes in memory only (sensitive-financial-data-secure-storage-only)."
)


class EvidenceInput(BaseModel):
    """Transient in-memory evidence bytes plus the provenance needed to cite them.

    Built by the resolver from evidence already held in secure storage. The bytes
    live only for the duration of a single on-host read; this model is never
    persisted (see the module docstring and the overridden dump methods).

    Attributes:
        mime_type: Concrete MIME type as recorded on the storage manifest (e.g.
            ``application/pdf``). Carried as provenance and for the vision
            reader, which needs a concrete image MIME. It is the producer's
            LABEL and decides nothing about how the bytes are read; that is
            :attr:`document_shape`, which is probed from the bytes themselves.
        data: The decrypted evidence bytes, in memory only. Excluded from ``repr``.
        content_sha256: 64-character lowercase hex SHA-256 of :attr:`data`; the
            content address the bytes were read under. Enforced to match ``data``.
        evidence_id: Originating purchase-invoice ``evidence_id`` when the bytes
            came from a :class:`PurchaseInvoiceEvidence` record, else ``None``.
        attachment_id: Originating ``attachment_id`` when the bytes came from an
            :class:`~cadrumo.domain.attachments.Attachment`, else ``None``.
    """

    model_config = STRICT_FROZEN_CONFIG

    mime_type: str = Field(min_length=1)
    data: bytes = Field(repr=False)
    content_sha256: ContentDigest
    evidence_id: str | None = None
    attachment_id: str | None = None

    @model_validator(mode="after")
    def _verify_content_address(self) -> Self:
        """Reject bytes whose digest does not match the declared content address."""
        if not self.data:
            raise ValueError("EvidenceInput.data must not be empty")
        digest = sha256_hex(self.data)
        if digest != self.content_sha256:
            raise ValueError("EvidenceInput.content_sha256 must equal sha256(data)")
        if self.evidence_id is None and self.attachment_id is None:
            raise ValueError("EvidenceInput must carry an evidence_id or an attachment_id for provenance")
        return self

    @model_serializer
    def _refuse_model_serialization(self) -> dict[str, object]:
        """Refuse pydantic serialization on every route, including nested dumps.

        Registered as the model serializer so a parent model that embeds an
        ``EvidenceInput`` and calls ``model_dump`` / ``model_dump_json`` also raises
        here, rather than serializing the raw ``data`` bytes through the field schema.
        """
        raise NotImplementedError(_REFUSAL_MESSAGE)

    @override
    def model_dump(self, *args: object, **kwargs: object) -> Never:  # reason: deliberate persistence tripwire
        """Refuse serialization -- decrypted FINANCIAL bytes must never be persisted."""
        raise NotImplementedError(_REFUSAL_MESSAGE)

    @property
    def document_shape(self) -> DocumentShape:
        """What this evidence actually IS, derived from its own bytes.

        The sole reading decision. It replaced a ``media_kind`` field derived
        from the STORED MIME TYPE, which is a label the producer attached and
        which cannot see inside the document -- so a ZUGFeRD invoice, a PDF
        carrying a complete machine-readable EN16931 record, answered ``PDF``
        and was routed to prose extraction exactly like a photograph of a
        receipt. The most exactly readable document in the corpus took the
        least exact path, decided by a label.

        Derived rather than stored, so it costs no constructor change and
        cannot drift from the bytes it describes: there is no second field to
        forget to update. The probe reads magic bytes and, for a PDF, walks the
        embedded-file table -- it never consults ``mime_type``.
        """
        from ...adapters.inbound.einvoice import probe_document_shape

        return probe_document_shape(self.data)

    @override
    def model_dump_json(self, *args: object, **kwargs: object) -> Never:  # reason: deliberate persistence tripwire
        """Refuse JSON serialization -- decrypted FINANCIAL bytes must never be persisted."""
        raise NotImplementedError(_REFUSAL_MESSAGE)

    @override
    def __iter__(self) -> Never:  # reason: deliberate persistence tripwire
        """Refuse iteration / ``dict()`` -- it would expose the raw ``data`` bytes."""
        raise NotImplementedError(_REFUSAL_MESSAGE)

    @override
    def __reduce_ex__(self, protocol: SupportsIndex) -> Never:
        """Refuse pickling -- it would embed the raw ``data`` bytes."""
        raise NotImplementedError(_REFUSAL_MESSAGE)


def _reject_unreadable_bytes(data: bytes, *, mime_type: str) -> None:
    """Refuse evidence whose BYTES match no readable document shape.

    The read path's admission question used to be asked of the stored MIME type
    through a two-member media kind, and a label cannot see inside a document.
    It got both directions wrong: a PNG announced as ``application/pdf`` was
    admitted and called a PDF, while a genuine PDF announced as
    ``application/octet-stream`` was refused outright. Neither answer was about
    the document.

    :attr:`DocumentShape.UNKNOWN` is the probe's own "never guessed at, always
    refused" verdict, so refusing on it moves the authority to the bytes while
    leaving every case where the label told the truth decided exactly as before.
    ``mime_type`` appears in the message only as the operator-visible breadcrumb
    identifying the record they are looking at; it decides nothing.
    """
    from ...adapters.inbound.einvoice import probe_document_shape

    if probe_document_shape(data) is DocumentShape.UNKNOWN:
        raise PurchaseInvoiceEvidenceInputError(
            f"evidence bytes (stored as {mime_type!r}) match no readable document shape; "
            "only PDF, structured XML and image evidence can be read",
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.EVIDENCE_BYTES_READABLE,
                facts={"document_shape_recognized": False},
            ),
        )


def resolve_attachment_evidence_input(
    attachment_id: str,
    *,
    store: AttachmentStoreProtocol,
    evidence_id: str | None = None,
) -> EvidenceInput:
    """Read stored evidence bytes from secure storage into an ``EvidenceInput``.

    The single read path for every evidence byte payload: bytes live in exactly
    one place (the content-addressed
    :class:`~cadrumo.domain.attachments.AttachmentStoreProtocol` blob for the
    active bucket), so both evidence tiers reach them through this one function.
    Loads the attachment manifest and its encrypted blob into memory. No file is
    written.

    Args:
        attachment_id: Content-addressed id of the stored bytes.
        store: Attachment store bound to the operation's secure-storage bucket.
        evidence_id: Originating :class:`PurchaseInvoiceEvidence` record id when
            the caller reached these bytes through an evidence record, else
            ``None`` for a bare linked attachment. Recorded on the result purely
            as provenance; it never selects the bytes.

    Returns:
        :class:`EvidenceInput`: In-memory bytes plus provenance, for an on-host read.

    Raises:
        PurchaseInvoiceEvidenceInputError: If the bytes match no readable
            document shape. Judged on the bytes, so the stored MIME type can be
            wrong in either direction without changing the verdict.
    """
    manifest = store.load_manifest(attachment_id)
    data = store.read_bytes(manifest.sha256)
    _reject_unreadable_bytes(data, mime_type=manifest.mime_type)
    return EvidenceInput(
        mime_type=manifest.mime_type,
        data=data,
        content_sha256=manifest.sha256,
        evidence_id=evidence_id,
        attachment_id=manifest.attachment_id,
    )


def resolve_purchase_invoice_evidence_input(
    evidence: PurchaseInvoiceEvidence,
    *,
    store: AttachmentStoreProtocol,
) -> EvidenceInput:
    """Read a purchase-invoice evidence record's bytes from secure storage.

    The provenance-binding adapter over :func:`resolve_attachment_evidence_input`:
    a :class:`PurchaseInvoiceEvidence` record holds no bytes of its own, only the
    ``attachment_id`` naming their in-store home written at ``add`` time, so the
    read delegates to the one attachment read path. Reading through this function
    rather than calling the attachment resolver directly is what guarantees the
    originating ``evidence_id`` is stamped on the result, so a record read can
    never lose its provenance.

    No byte-custody guard is needed or possible: ``attachment_id`` is a required
    field, so a record that reached secure storage has an in-store byte home by
    construction, and a byte-less record is refused at model validation rather
    than here. The cleartext ``source_path`` is never a fallback byte source
    (sensitive-financial-data-secure-storage-only).

    Args:
        evidence: The purchase-invoice evidence record.
        store: Attachment store bound to the operation's secure-storage bucket.

    Returns:
        :class:`EvidenceInput`: In-memory bytes plus provenance, for an on-host read.
    """
    return resolve_attachment_evidence_input(
        evidence.attachment_id,
        store=store,
        evidence_id=evidence.evidence_id,
    )
