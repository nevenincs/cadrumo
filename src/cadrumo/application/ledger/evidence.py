"""Purchase invoice evidence records and the CRUD application service.

``aeat app ledger evidence {add|remove|update|view|list}`` operate over a
:class:`PurchaseInvoiceEvidence` pydantic record. Audit events are emitted
to a :class:`BucketEventHistoryRepository` on every mutating verb.

A :class:`PurchaseInvoiceEvidence` record is the MIDDLE tier of the three-rung
evidence progression, and owns no bytes of its own:

1. :class:`~cadrumo.domain.attachments.Attachment` owns byte custody. It is
   strictly content-addressed (``attachment_id == sha256`` of the stored bytes),
   immutable, and carries no fiscal figures. ``aeat app ledger attach`` and
   ``aeat app ledger doclink`` link one directly to a transaction.
2. :class:`PurchaseInvoiceEvidence` is an operator-registered CLAIM ABOUT one
   such byte payload: a mutable record whose supplier, invoice number, invoice
   date, and IVA figures are all OPTIONAL, because a scan whose text layer
   yields nothing is still valid evidence. Its ``evidence_id`` is a metadata
   digest, not a content digest, so several records may describe one byte
   payload; the bytes themselves are stored once, as the ``Attachment`` written
   at ``add`` time and read back through ``attachment_id``.
3. :class:`~cadrumo.domain.invoices.Invoice` is the CONFIRMED fiscal document,
   whose counterparty name, tax id, country, totals, currency, and lines are all
   REQUIRED. ``aeat app ledger evidence confirm`` promotes tier 2 to tier 3 once
   the operator supplies or accepts those figures.

The tiers are a permissiveness ladder, not three ways of saying one thing: each
rung requires strictly more than the one below it, so none can absorb another
without either dropping fiscal fields or refusing evidence the tier below
legitimately accepts.

File-type scope is restricted to PDF and image inputs. Plaintext, email
body, and Drive-URL evidence sources are out of scope. ``add`` refuses
non-PDF/non-image source paths with a typed
:class:`PurchaseInvoiceEvidenceInputError`.

Persistence is bucket-scoped encrypted secure-object storage. The evidence
catalogue is a :class:`PurchaseInvoiceEvidenceDocument` persisted through
:class:`~cadrumo.adapters.persistence.storage.SecureBoundRepository` under
:data:`cadrumo.adapters.persistence.storage.LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE`.
At ``add`` time the source file's bytes are copied into the encrypted
:class:`~cadrumo.adapters.persistence.storage.AttachmentStore` (active bucket) and
the resulting content-addressed ``attachment_id`` is recorded on the evidence
record; the bytes thereafter live only in secure storage. ``source_path`` is
retained as a provenance breadcrumb and is never read for bytes
(``sensitive-financial-data-secure-storage-only``).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from typing import override

from pydantic import BaseModel, Field, field_serializer

from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.storage import (
    LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE,
    AttachmentStore,
    SecureBoundRepository,
    secure_object_repository_for_bucket,
)
from ...core import STRICT_FROZEN_CONFIG, Hex64Str
from ...core.config import Settings
from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import PDF_EXTENSION, PDF_MIME_TYPE, XML_MIME_TYPE
from ...core.hashing import content_hash_hex
from ...core.identity import BucketId, ContentDigest
from ...core.time import now as _utc_now
from ...domain.attachments.enums import AttachmentKind, AttachmentSource
from ...domain.attachments.service import AttachmentFileContent, AttachmentIngestionRequest, add_attachment
from ...domain.buckets.event import BucketEventObjectType, BucketEventType
from ...domain.buckets.event_repository import emit_bucket_event
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.identifiers import canonical_decimal_string
from .preconditions import LedgerPreconditionCondition, LedgerPreconditionErrorMixin, ledger_no_recovery_verdict

_PDF_EXTENSIONS = frozenset({PDF_EXTENSION})
_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".heic", ".heif"})
# Structured e-invoice documents (EN16931 CII/UBL, Facturae 3.2.x). Admitted
# here because the deterministic readers in `adapters.inbound.einvoice` can
# now read them EXACTLY, on a default install, with no model involved. Before
# those readers existed this gate refused them, which was the right answer;
# leaving it refusing them afterwards would be the campaign's own named
# failure mode -- a deliverable that ships correct, tested and unreachable,
# readable only if the document happened to arrive through `doclink` or
# `pull-folder` instead of the front door.
_STRUCTURED_EXTENSIONS = frozenset({".xml"})

# Concrete MIME types by source extension. The on-host vision reader needs a
# concrete MIME (image/png vs image/jpeg), which `MediaKind` alone cannot supply.
_SUFFIX_MIME = {
    PDF_EXTENSION: PDF_MIME_TYPE,
    # Every extension `_resolve_media_kind` ADMITS must have an entry here, or
    # `evidence add` raises a bare KeyError the operator sees as an internal
    # error. Widening the accept-list for structured documents without this
    # entry is exactly what made Facturae, CII and UBL unreachable through the
    # front door while the readers for them worked perfectly.
    ".xml": XML_MIME_TYPE,
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
}


def _attachment_kind_for(media_kind: MediaKind) -> AttachmentKind:
    """Map a purchase-invoice ``MediaKind`` to the attachment manifest kind."""
    return AttachmentKind.INVOICE_PDF if media_kind is MediaKind.PDF else AttachmentKind.RECEIPT_IMAGE


class MediaKind(StrEnum):
    """Canonical media-kind values for purchase invoice evidence."""

    PDF = "pdf"
    IMAGE = "image"


class PurchaseInvoiceEvidenceInputError(LedgerPreconditionErrorMixin, CadrumoError):
    """Raised when a CLI-supplied evidence input violates the typed contract."""


class PurchaseInvoiceEvidenceNotFoundError(LedgerPreconditionErrorMixin, CadrumoError):
    """Raised when a CLI lookup targets a missing evidence record."""


class PurchaseInvoiceEvidence(BaseModel):
    """One persisted purchase invoice evidence record."""

    model_config = STRICT_FROZEN_CONFIG

    evidence_id: str = Field(min_length=1, max_length=64)
    bucket_id: BucketId
    source_path: str = Field(min_length=1)
    source_sha256: ContentDigest
    # In-store byte home: the bytes live encrypted in the AttachmentStore under this
    # content-addressed id. Required, because a record whose bytes are not in secure
    # storage is not evidence -- `source_path` is a provenance breadcrumb only and is
    # never read for bytes (sensitive-financial-data-secure-storage-only), so a
    # byte-less record would be an unreadable claim about a file we do not hold.
    attachment_id: Hex64Str
    media_kind: MediaKind
    supplier: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    taxable_base: Decimal | None = None
    iva_rate: Decimal | None = None
    iva_amount: Decimal | None = None
    notes: str = ""
    created_at: datetime
    updated_at: datetime

    @field_serializer("taxable_base", "iva_rate", "iva_amount", when_used="json")
    def _serialize_decimal(self, value: Decimal | None) -> str | None:
        return None if value is None else str(value)


#: Bound on the mint-time collision disambiguator. A genuine collision needs an
#: identical record (same file, fields, and coarse-clock instant) already stored,
#: so a handful of attempts is the realistic ceiling; the cap exists so a
#: derivation regression that drops the disambiguator from the digest fails loudly
#: instead of spinning forever.
_ID_DISAMBIGUATION_CAP = 1024


def derive_purchase_invoice_evidence_id(
    *,
    bucket_id: str,
    source_sha256: str,
    media_kind: MediaKind,
    supplier: str | None,
    invoice_number: str | None,
    invoice_date: str | None,
    taxable_base: Decimal | None,
    iva_rate: Decimal | None,
    iva_amount: Decimal | None,
    notes: str,
    created_at: datetime,
    disambiguator: int = 0,
) -> str:
    """Return the content-addressed id for a purchase-invoice evidence record.

    Mirrors :func:`cadrumo.domain.transactions.derive_transaction_id`: the id is a
    SHA-256 digest (truncated to 16 hex chars, the prior surrogate's width) over
    the record's identifying fields, so it is stable under a frozen-clock replay
    and directly referenceable as an ``aeat app ledger evidence`` argument,
    needing no output mask. ``created_at`` plus the ``disambiguator`` ordinal
    preserve the genuine-duplicate case the ledger already supports: two evidence
    records for the same file must keep distinct ids, so the mint site increments
    ``disambiguator`` on the rare digest collision (identical fields at an
    identical coarse-clock instant) rather than colliding.
    """
    return content_hash_hex(
        {
            "bucket_id": bucket_id,
            "source_sha256": source_sha256,
            "media_kind": media_kind.value,
            "supplier": supplier or "",
            "invoice_number": invoice_number or "",
            "invoice_date": invoice_date or "",
            "taxable_base": canonical_decimal_string(taxable_base) if taxable_base is not None else "",
            "iva_rate": canonical_decimal_string(iva_rate) if iva_rate is not None else "",
            "iva_amount": canonical_decimal_string(iva_amount) if iva_amount is not None else "",
            "notes": notes,
            "created_at": created_at.isoformat(),
            "disambiguator": disambiguator,
        },
    )[:16]


def derive_keyed_purchase_invoice_evidence_id(*, bucket_id: str, idempotency_key: str) -> str:
    """Return a CLOCK-FREE evidence id for a caller-supplied idempotency key.

    The keyless derivation above deliberately folds ``created_at`` plus a
    disambiguator, and that is not an oversight to correct: two evidence records
    for the same file are a legitimate case -- the same invoice PDF can be
    attached twice as two distinct pieces of evidence -- and simply dropping the
    clock would silently collapse them into one. The codified rule anticipates
    exactly this and supplies the shape: a deliberately-additive verb documents
    itself as such, while a caller-supplied key provides the guarded path for
    callers that need one.

    So this is not "drop the clock", it is "add the key". The id derives from
    the bucket and the key alone, which is what makes a retry at a different
    instant resolve to the same record.
    """
    return content_hash_hex({"bucket_id": bucket_id, "idempotency_key": idempotency_key})[:16]


def _derive_additive_evidence_id(
    *,
    bucket_id: str,
    digest: str,
    media_kind: MediaKind,
    supplier: str | None,
    invoice_number: str | None,
    invoice_date: str | None,
    taxable_base: Decimal | None,
    iva_rate: Decimal | None,
    iva_amount: Decimal | None,
    notes: str,
    now: datetime,
    existing_ids: set[str],
) -> str:
    """Derive the keyless, deliberately-additive evidence id.

    Extracted from the mint site when the keyed path landed beside it, so the
    two identity regimes read as two named alternatives rather than as one loop
    with a conditional range. The disambiguator preserves the genuine-duplicate
    case: two attachments of the same file are distinct evidence.
    """
    for disambiguator in range(_ID_DISAMBIGUATION_CAP):
        candidate = derive_purchase_invoice_evidence_id(
            bucket_id=bucket_id,
            source_sha256=digest,
            media_kind=media_kind,
            supplier=supplier,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            taxable_base=taxable_base,
            iva_rate=iva_rate,
            iva_amount=iva_amount,
            notes=notes,
            created_at=now,
            disambiguator=disambiguator,
        )
        if candidate not in existing_ids:
            return candidate
    # Unreachable unless the derivation stops incorporating the disambiguator:
    # then every attempt collides and the loop would spin forever. Fail loudly
    # on the bounded cap instead of hanging.
    raise RuntimeError(
        f"could not derive a unique purchase-invoice evidence id after "
        f"{_ID_DISAMBIGUATION_CAP} attempts; the content digest is not "
        "incorporating the disambiguator (a derivation regression)",
    )


def _divergent_evidence_fields(
    prior: PurchaseInvoiceEvidence,
    *,
    source_sha256: str,
    media_kind: MediaKind,
    supplier: str | None,
    invoice_number: str | None,
    invoice_date: str | None,
    taxable_base: Decimal | None,
    iva_rate: Decimal | None,
    iva_amount: Decimal | None,
    notes: str,
) -> tuple[str, ...]:
    """Name every persisted field on which a same-key re-add differs.

    Compares EVERY persisted field, not a subset, and that is the load-bearing
    part rather than a thoroughness flourish. A guarded no-op that matches on a
    subset silently DROPS whatever changed in the fields it did not look at --
    an under-declaration wearing an idempotency guard's clothes. The close
    review of this rule's origin campaign caught exactly that failure, on a
    recargo field a match had omitted.
    """
    candidate: dict[str, object] = {
        "source_sha256": source_sha256,
        "media_kind": media_kind,
        "supplier": supplier,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "taxable_base": taxable_base,
        "iva_rate": iva_rate,
        "iva_amount": iva_amount,
        "notes": notes,
    }
    return tuple(name for name, value in candidate.items() if getattr(prior, name) != value)


class PurchaseInvoiceEvidenceDocument(BaseModel):
    """Encrypted bucket-local purchase invoice evidence catalogue."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    records: tuple[PurchaseInvoiceEvidence, ...] = ()


class PurchaseInvoiceEvidencePatch(BaseModel):
    """Mutable subset of ``PurchaseInvoiceEvidence`` fields accepted by ``update``.

    Only the fields listed here may be changed after an evidence record is
    created. ``evidence_id``, ``bucket_id``, ``source_path``,
    ``source_sha256``, ``attachment_id``, ``media_kind``, and the timestamp
    fields are immutable.
    A ``None`` value for any optional field means "leave unchanged"; the
    service ignores ``None`` entries when applying the patch.
    """

    model_config = STRICT_FROZEN_CONFIG

    supplier: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    taxable_base: Decimal | None = None
    iva_rate: Decimal | None = None
    iva_amount: Decimal | None = None
    notes: str | None = None


def _resolve_media_kind(source_path: Path) -> MediaKind:
    """Admit a source file by extension, refusing with the accepted set named.

    The suffix decides ADMISSION only. What the document actually IS -- and
    therefore how exactly it can be read -- is derived from its bytes by
    :func:`~adapters.inbound.einvoice.probe_document_shape` at read time, because
    a suffix and a declared MIME both answered "PDF" for a ZUGFeRD invoice
    carrying a complete machine-readable record.
    """
    suffix = source_path.suffix.lower()
    if suffix in _PDF_EXTENSIONS or suffix in _STRUCTURED_EXTENSIONS:
        # A structured XML document and a PDF are both read through the
        # document-shape probe; the coarse media kind stays PDF-side because
        # neither is an image.
        return MediaKind.PDF
    if suffix in _IMAGE_EXTENSIONS:
        return MediaKind.IMAGE
    accepted = ", ".join(sorted(_PDF_EXTENSIONS | _STRUCTURED_EXTENSIONS | _IMAGE_EXTENSIONS))
    raise PurchaseInvoiceEvidenceInputError(
        translated_message="errors.refused.refused_ledger_evidence_input",
        context={"suffix": suffix, "accepted_extensions": accepted},
        precondition_verdict=ledger_no_recovery_verdict(
            LedgerPreconditionCondition.EVIDENCE_FILE_EXTENSION_SUPPORTED,
            facts={"extension_supported": False},
        ),
    )


class PurchaseInvoiceEvidenceResult(BaseModel):
    """Return record from a mutating evidence verb — record plus emitted event id."""

    model_config = STRICT_FROZEN_CONFIG

    record: PurchaseInvoiceEvidence
    bucket_event_ids: tuple[str, ...] = ()


class PurchaseInvoiceEvidenceRepository(SecureBoundRepository[PurchaseInvoiceEvidenceDocument]):
    """Encrypted store for one bucket's :class:`PurchaseInvoiceEvidenceDocument`.

    The namespace, sensitivity, schema version, and object-key contract come
    from
    :data:`cadrumo.adapters.persistence.storage.LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE`.
    The :class:`~cadrumo.adapters.persistence.storage.SecureBoundRepository` base
    wraps each :class:`PurchaseInvoiceEvidenceDocument` in a
    :class:`~cadrumo.adapters.persistence.storage.Envelope` before writing it.

    See Also:
        :class:`PurchaseInvoiceEvidenceService`
            CRUD service that mutates this repository and emits bucket events.
        :class:`~cadrumo.adapters.persistence.storage.AttachmentStore`
            Encrypted byte store that holds the referenced source files.
    """

    namespace = LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE.namespace
    sensitivity = LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE.sensitivity
    schema_version = LEDGER_PURCHASE_INVOICE_EVIDENCE_NAMESPACE.schema_version
    payload_type = PurchaseInvoiceEvidenceDocument

    @override
    def extract_identifier(self, payload: PurchaseInvoiceEvidenceDocument) -> str:
        return payload.bucket_id


def _repository(settings: Settings, bucket_id: str) -> PurchaseInvoiceEvidenceRepository:
    return PurchaseInvoiceEvidenceRepository(objects=secure_object_repository_for_bucket(bucket_id, settings))


def _load(settings: Settings, bucket_id: str) -> list[PurchaseInvoiceEvidence]:
    document = _repository(settings, bucket_id).load(bucket_id)
    return list(document.records) if document is not None else []


def _save(settings: Settings, bucket_id: str, records: list[PurchaseInvoiceEvidence]) -> None:
    _repository(settings, bucket_id).save(
        PurchaseInvoiceEvidenceDocument(bucket_id=bucket_id, records=tuple(records)),
    )


_EVIDENCE_EVENT_PAYLOAD_VERSION = 1


def _emit_evidence_event(
    *,
    event_repository: BucketEventHistoryRepositoryProtocol,
    bucket_id: str,
    event_type: BucketEventType,
    evidence_id: str,
    actor: str,
    occurred_at: datetime,
    payload: dict[str, str],
) -> str:
    """Record one evidence transition through the shared emission primitive.

    This used to derive the id, build the event, append it and save the
    catalogue itself -- the exact sequence :func:`emit_bucket_event` documents
    as the one every emitting domain must share. Re-deriving it cost more than
    duplication: the shared primitive appends through the catalogue's revision
    guard, and a bare load-append-save does not, so two evidence attachments
    landing together discarded one another's audit entry. Content-addressed
    events make that loss invisible after the fact -- every survivor is intact
    and the missing one leaves no gap -- so the trail still read as complete.

    The only things this surface fixes are the object kind and the payload
    version; everything else is the caller's.
    """
    event = emit_bucket_event(
        repository=event_repository,
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE,
        object_id=evidence_id,
        payload=payload,
        payload_version=_EVIDENCE_EVENT_PAYLOAD_VERSION,
    )
    return event.event_id


class PurchaseInvoiceEvidenceService:
    """Application service for the ``aeat app ledger evidence`` verb group."""

    def __init__(
        self,
        settings: Settings | None = None,
        bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    ) -> None:
        """Initialise the service with optional dependency injection.

        Args:
            settings: Resolved ``Settings`` object. When ``None``,
                ``load_settings()`` is called so that test overrides via
                ``override_settings()`` are honoured.
            bucket_event_repository: Audit-event sink. Defaults to
                ``BucketEventHistoryRepository`` backed by the requested
                operation bucket.
        """
        # `load_settings()` honours `override_settings`; bare `Settings()`
        # bypasses the context-var and lands writes in the project default.
        from ...core.config import load_settings as _load_settings

        self._settings = settings or _load_settings()
        self._event_repository = bucket_event_repository

    def add(
        self,
        *,
        bucket_id: str,
        source_path: str | Path,
        supplier: str | None = None,
        invoice_number: str | None = None,
        invoice_date: str | None = None,
        taxable_base: Decimal | None = None,
        iva_rate: Decimal | None = None,
        iva_amount: Decimal | None = None,
        notes: str = "",
        actor: str = "cli",
        idempotency_key: str | None = None,
    ) -> PurchaseInvoiceEvidenceResult:
        """Attach a new purchase invoice evidence file to a bucket (ledger).

        Resolves ``source_path`` for byte access only, verifies the file
        exists, infers the ``MediaKind`` from the extension, copies the file's
        bytes into the encrypted
        :class:`~cadrumo.adapters.persistence.storage.AttachmentStore` (active
        bucket) and records the resulting content-addressed ``attachment_id`` on
        the record (the bytes thereafter live only in secure storage). The
        persisted ``source_path`` is the argv-faithful path the operator
        supplied, never the machine-absolutized form, so it is a stable
        provenance breadcrumb rather than a machine-dependent one. Creates a
        ``PurchaseInvoiceEvidence`` record,
        appends it to the in-memory catalogue, persists the encrypted bucket-local catalogue
        in secure-object storage, and emits a
        ``PURCHASE_INVOICE_EVIDENCE_ATTACHED`` audit event whose content-addressed
        id derives from the source digest and stable metadata, never the path.

        Args:
            bucket_id: Ledger bucket the evidence belongs to.
            source_path: Local path to a PDF or image file. A ``str`` (the raw
                operator argv) is echoed onto the record verbatim — separators are
                preserved exactly, never OS-normalized — so the persisted path and
                envelope are identical across platforms (a forward-slash relative
                path stays forward-slash on Windows). A ``Path`` is accepted for
                programmatic callers and stringified for the echo. Byte access
                always resolves the path regardless.
            supplier: Optional vendor name extracted from the invoice.
            invoice_number: Optional invoice identifier from the document.
            invoice_date: Optional issue date string (free-form; typically
                ``YYYY-MM-DD``).
            taxable_base: Optional net taxable amount (``~decimal.Decimal``).
            iva_rate: Optional IVA percentage as a ``~decimal.Decimal``.
            iva_amount: Optional IVA amount as a ``~decimal.Decimal``.
            notes: Operator free-text annotation.
            actor: Identifier stamped on the audit event (defaults to
                ``"cli"``).
            idempotency_key: Caller-supplied retry key. When supplied the
                record id is derived CLOCK-FREE from it, so a retry at a
                different instant resolves to the same record: a matching
                re-add returns the existing record as a guarded no-op with no
                second bucket event and no re-stamped timestamp, and a same-key
                re-add whose content differs refuses naming the divergent
                fields. When omitted the verb stays deliberately ADDITIVE --
                two attachments of one file are two distinct pieces of
                evidence, and collapsing them would be its own defect.

        Returns:
            :class:`PurchaseInvoiceEvidenceResult`: Carrying the new record and the
            emitted audit event id.

        Raises:
            ``PurchaseInvoiceEvidenceInputError``: if ``source_path`` is not a
                readable file or has an unsupported extension.
        """
        resolved = Path(source_path).expanduser().resolve()
        if not resolved.is_file():
            raise PurchaseInvoiceEvidenceInputError(
                translated_message="errors.refused.refused_ledger_evidence_input",
                context={"source_path": str(source_path), "resolved_path": str(resolved)},
                precondition_verdict=ledger_no_recovery_verdict(
                    LedgerPreconditionCondition.EVIDENCE_FILE_READABLE,
                    facts={"source_file_readable": False},
                ),
            )
        media_kind = _resolve_media_kind(resolved)
        now = _utc_now()
        # The attachment service is the single manifest and encrypted-byte write
        # authority. Ledger retains its narrow PDF/image admission, stable source
        # provenance, and evidence-specific audit lifecycle around that custody write.
        store = AttachmentStore(objects=secure_object_repository_for_bucket(bucket_id, self._settings))
        attachment = add_attachment(
            store,
            content=AttachmentFileContent(path=resolved),
            request=AttachmentIngestionRequest(
                kind=_attachment_kind_for(media_kind),
                source=AttachmentSource.LOCAL_FILE,
                source_reference=str(resolved),
                mime_type=_SUFFIX_MIME[resolved.suffix.lower()],
                captured_at=now,
                bucket_id=bucket_id,
                captured_by=actor,
                source_command="aeat app ledger evidence add",
            ),
        )
        digest = attachment.attachment_id
        records = _load(self._settings, bucket_id)
        existing_ids = {existing.evidence_id for existing in records}
        if idempotency_key is not None:
            keyed_id = derive_keyed_purchase_invoice_evidence_id(
                bucket_id=bucket_id,
                idempotency_key=idempotency_key,
            )
            prior = next((row for row in records if row.evidence_id == keyed_id), None)
            if prior is not None:
                divergent = _divergent_evidence_fields(
                    prior,
                    source_sha256=digest,
                    media_kind=media_kind,
                    supplier=supplier,
                    invoice_number=invoice_number,
                    invoice_date=invoice_date,
                    taxable_base=taxable_base,
                    iva_rate=iva_rate,
                    iva_amount=iva_amount,
                    notes=notes,
                )
                if divergent:
                    raise PurchaseInvoiceEvidenceInputError(
                        translated_message="errors.refused.refused_ledger_evidence_input",
                        precondition_verdict=ledger_no_recovery_verdict(
                            LedgerPreconditionCondition.EVIDENCE_IDEMPOTENCY_KEY_UNIQUE,
                            facts={"idempotency_key_matches_existing_record": False},
                        ),
                    )
                # Guarded no-op: the existing record, no second bucket event, no
                # re-stamped timestamp. The empty event tuple is the signal that
                # nothing was written.
                return PurchaseInvoiceEvidenceResult(record=prior, bucket_event_ids=())
            evidence_id = keyed_id
        else:
            evidence_id = _derive_additive_evidence_id(
                bucket_id=bucket_id,
                digest=digest,
                media_kind=media_kind,
                supplier=supplier,
                invoice_number=invoice_number,
                invoice_date=invoice_date,
                taxable_base=taxable_base,
                iva_rate=iva_rate,
                iva_amount=iva_amount,
                notes=notes,
                now=now,
                existing_ids=existing_ids,
            )
        record = PurchaseInvoiceEvidence(
            evidence_id=evidence_id,
            bucket_id=bucket_id,
            # Argv-faithful breadcrumb: echo the path the operator supplied, never
            # the machine-absolutized form. `resolved` is used for byte access
            # only; folding the absolute path into the persisted record (and the
            # echoed envelope) made two invocations from different working dirs
            # non-deterministic for identical bytes.
            source_path=str(source_path),
            source_sha256=digest,
            attachment_id=digest,
            media_kind=media_kind,
            supplier=supplier,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            taxable_base=taxable_base,
            iva_rate=iva_rate,
            iva_amount=iva_amount,
            notes=notes,
            created_at=now,
            updated_at=now,
        )
        records.append(record)
        _save(self._settings, bucket_id, records)
        event_id = _emit_evidence_event(
            event_repository=self._event_repository_for_bucket(bucket_id),
            bucket_id=bucket_id,
            event_type=BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED,
            evidence_id=record.evidence_id,
            actor=actor,
            occurred_at=now,
            # Identity-bearing payload: the content digest plus stable declared
            # metadata, never the source path. The bucket-event id folds the
            # payload, so a path here would make the event id machine-path
            # dependent (the defect this fix closes).
            payload={"media_kind": record.media_kind, "source_sha256": record.source_sha256},
        )
        return PurchaseInvoiceEvidenceResult(record=record, bucket_event_ids=(event_id,))

    def view(self, *, bucket_id: str, evidence_id: str) -> PurchaseInvoiceEvidence:
        """Return the single evidence record identified by ``evidence_id``.

        Args:
            bucket_id: Ledger bucket to search.
            evidence_id: Unique evidence id assigned at ``add`` time.

        Returns:
            :class:`PurchaseInvoiceEvidence`: The matching record.

        Raises:
            ``PurchaseInvoiceEvidenceNotFoundError``: if no record with that id
                exists in the bucket.
        """
        for record in _load(self._settings, bucket_id):
            if record.evidence_id == evidence_id:
                return record
        raise PurchaseInvoiceEvidenceNotFoundError(
            translated_message="errors.refused.refused_ledger_evidence_not_found",
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.EVIDENCE_REFERENCE_RESOLVES,
                facts={"evidence_record_present": False},
            ),
        )

    def list_all(self, *, bucket_id: str) -> tuple[PurchaseInvoiceEvidence, ...]:
        """Return all evidence records for a bucket in append order.

        Args:
            bucket_id: Ledger bucket to read.

        Returns:
            tuple[:class:`PurchaseInvoiceEvidence`, ...]: Oldest first.
            Returns an empty tuple if the bucket has no evidence file yet.
        """
        return tuple(_load(self._settings, bucket_id))

    def update(
        self,
        *,
        bucket_id: str,
        evidence_id: str,
        patch: PurchaseInvoiceEvidencePatch,
        actor: str = "cli",
    ) -> PurchaseInvoiceEvidenceResult:
        """Apply a partial update to an existing evidence record.

        Loads the bucket's record list, finds the record matching
        ``evidence_id``, merges non-``None`` fields from ``patch``, stamps
        ``updated_at``, writes the updated list back, and emits a
        ``PURCHASE_INVOICE_EVIDENCE_REPLACED`` audit event.

        Args:
            bucket_id: Ledger bucket containing the record.
            evidence_id: Id of the record to update.
            patch: ``PurchaseInvoiceEvidencePatch`` carrying the fields to
                change. Fields set to ``None`` are left unchanged.
            actor: Identifier stamped on the audit event.

        Returns:
            :class:`PurchaseInvoiceEvidenceResult`: With the updated record and audit
            event id.

        Raises:
            ``PurchaseInvoiceEvidenceNotFoundError``: if no matching record
                exists.
        """
        records = _load(self._settings, bucket_id)
        for index, record in enumerate(records):
            if record.evidence_id != evidence_id:
                continue
            data = record.model_dump()
            for key, value in patch.model_dump(exclude_unset=True).items():
                if value is not None:
                    data[key] = value
            now = _utc_now()
            data["updated_at"] = now
            updated = PurchaseInvoiceEvidence.model_validate(data)
            records[index] = updated
            _save(self._settings, bucket_id, records)
            event_id = _emit_evidence_event(
                event_repository=self._event_repository_for_bucket(bucket_id),
                bucket_id=bucket_id,
                event_type=BucketEventType.PURCHASE_INVOICE_EVIDENCE_REPLACED,
                evidence_id=evidence_id,
                actor=actor,
                occurred_at=now,
                payload={"media_kind": updated.media_kind},
            )
            return PurchaseInvoiceEvidenceResult(record=updated, bucket_event_ids=(event_id,))
        raise PurchaseInvoiceEvidenceNotFoundError(
            translated_message="errors.refused.refused_ledger_evidence_not_found",
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.EVIDENCE_REFERENCE_RESOLVES,
                facts={"evidence_record_present": False},
            ),
        )

    def remove(
        self,
        *,
        bucket_id: str,
        evidence_id: str,
        actor: str = "cli",
    ) -> PurchaseInvoiceEvidenceResult:
        """Remove an evidence record from a bucket.

        Loads the bucket catalogue, finds the record, removes it from the
        in-memory list, persists the updated encrypted bucket-local catalogue
        in secure-object storage, and emits a
        ``PURCHASE_INVOICE_EVIDENCE_DETACHED`` audit event.

        Args:
            bucket_id: Ledger bucket containing the record.
            evidence_id: Id of the record to remove.
            actor: Identifier stamped on the audit event.

        Returns:
            :class:`PurchaseInvoiceEvidenceResult`: Carrying the removed record and
            the audit event id.

        Raises:
            ``PurchaseInvoiceEvidenceNotFoundError``: if no matching record
                exists.
        """
        records = _load(self._settings, bucket_id)
        for index, record in enumerate(records):
            if record.evidence_id == evidence_id:
                removed = records.pop(index)
                _save(self._settings, bucket_id, records)
                now = _utc_now()
                event_id = _emit_evidence_event(
                    event_repository=self._event_repository_for_bucket(bucket_id),
                    bucket_id=bucket_id,
                    event_type=BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED,
                    evidence_id=evidence_id,
                    actor=actor,
                    occurred_at=now,
                    payload={"media_kind": removed.media_kind},
                )
                return PurchaseInvoiceEvidenceResult(record=removed, bucket_event_ids=(event_id,))
        raise PurchaseInvoiceEvidenceNotFoundError(
            translated_message="errors.refused.refused_ledger_evidence_not_found",
            precondition_verdict=ledger_no_recovery_verdict(
                LedgerPreconditionCondition.EVIDENCE_REFERENCE_RESOLVES,
                facts={"evidence_record_present": False},
            ),
        )

    def _event_repository_for_bucket(self, bucket_id: str) -> BucketEventHistoryRepositoryProtocol:
        if self._event_repository is not None:
            return self._event_repository
        return BucketEventHistoryRepository(
            objects=secure_object_repository_for_bucket(bucket_id, self._settings),
        )


# Public supporting contract for sibling ledger action services, matching the
# shape `_actions_common` declares. The evidence event emitter is shared: this
# module raises it on the evidence paths, and the LLM review workflow raises the
# same event for a declined draft, which never becomes a transaction.
emit_evidence_event = _emit_evidence_event

__all__ = [
    "PurchaseInvoiceEvidence",
    "PurchaseInvoiceEvidenceDocument",
    "PurchaseInvoiceEvidenceInputError",
    "PurchaseInvoiceEvidenceNotFoundError",
    "PurchaseInvoiceEvidencePatch",
    "PurchaseInvoiceEvidenceRepository",
    "PurchaseInvoiceEvidenceResult",
    "PurchaseInvoiceEvidenceService",
    "emit_evidence_event",
]
