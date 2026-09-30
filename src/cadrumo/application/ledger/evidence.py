"""Purchase invoice evidence records and the CRUD application service.

``aeat app ledger evidence {add|remove|update|view|list}`` operate over a
:class:`PurchaseInvoiceEvidence` pydantic record. Audit events are emitted
to a :class:`BucketEventHistoryRepository` on every mutating verb.

A :class:`PurchaseInvoiceEvidence` record is the MIDDLE tier of the three-rung
evidence progression, and owns no bytes of its own:

1. :class:`~cadrumo.domain.attachments.models.Attachment` owns byte custody. It is
   strictly content-addressed (``attachment_id == sha256`` of the stored bytes),
   immutable, and carries no fiscal figures. ``aeat app ledger attach`` and
   ``aeat app ledger evidence pull`` link one directly to a transaction.
2. :class:`PurchaseInvoiceEvidence` is an operator-registered CLAIM ABOUT one
   such byte payload: a mutable record whose supplier, invoice number, invoice
   date, and IVA figures are all OPTIONAL, because a scan whose text layer
   yields nothing is still valid evidence. Its ``evidence_id`` is a metadata
   digest, not a content digest, so several records may describe one byte
   payload; the bytes themselves are stored once, as the ``Attachment`` written
   at ``add`` time and read back through ``attachment_id``.
3. :class:`~cadrumo.domain.invoices.models.Invoice` is the CONFIRMED fiscal document,
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
catalogue is a :class:`PurchaseInvoiceEvidenceDocument` and the source bytes
are written through the required :class:`LedgerEvidencePorts` custody
capability. The resulting content-addressed ``attachment_id`` is recorded on
the evidence record; the bytes thereafter live only in secure storage.
``source_path`` is retained as a provenance breadcrumb and is never read for
bytes (``sensitive-financial-data-secure-storage-only``).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_serializer

from ...core.errors.hierarchy import InternalInvariantError
from ...core.external_constants import PDF_EXTENSION, PDF_MIME_TYPE, XML_MIME_TYPE
from ...core.hashing import content_hash_hex
from ...core.hex import Hex64Str
from ...core.identity.bucket import BucketId
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.percentage import Percentage
from ...core.text_bounds import NonNegativeDecimal
from ...core.time.clock import now as _utc_now
from ...domain.buckets.event import BucketEventObjectType, BucketEventType
from ...domain.buckets.event_repository import bucket_event_history_write, build_bucket_event, emit_bucket_event
from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.identifiers import canonical_decimal_string
from .evidence_errors import PurchaseInvoiceEvidenceInputError, PurchaseInvoiceEvidenceNotFoundError
from .evidence_ports import (
    EvidenceAttachmentIngestRequest,
    LedgerEvidencePorts,
    RevisionGuardedPurchaseInvoiceEvidenceRepositoryProtocol,
)
from .persistence_ports import LedgerPersistenceConflictError
from .preconditions import LedgerPreconditionCondition, ledger_no_recovery_verdict

_PDF_EXTENSIONS = frozenset({PDF_EXTENSION})
_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".heic", ".heif"})
# Structured e-invoice documents (EN16931 CII/UBL, Facturae 3.2.x). Admitted
# here because the deterministic document readers can
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


class MediaKind(StrEnum):
    """Canonical media-kind values for purchase invoice evidence."""

    PDF = "pdf"
    IMAGE = "image"


class PurchaseInvoiceEvidence(BaseModel):
    """One persisted purchase invoice evidence record."""

    model_config = STRICT_FROZEN_CONFIG

    evidence_id: str = Field(min_length=1, max_length=64)
    bucket_id: BucketId
    source_path: str = Field(min_length=1)
    source_sha256: ContentDigest
    # In-store byte home: the bytes live encrypted in secure custody under this
    # content-addressed id. Required, because a record whose bytes are not in secure
    # storage is not evidence -- `source_path` is a provenance breadcrumb only and is
    # never read for bytes (sensitive-financial-data-secure-storage-only), so a
    # byte-less record would be an unreadable claim about a file we do not hold.
    attachment_id: Hex64Str
    media_kind: MediaKind
    supplier: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    # Bounded, because these three are not display-only. The reconciliation
    # projection in application/aggregation/_renta_ledger.py copies
    # ``taxable_base`` and ``iva_amount`` off this record into a renta
    # deductible-expense observation, so a negative figure persisted here
    # reaches a deduction. Both this record and its patch took ANY Decimal:
    # -5 and 210 were accepted and echoed back to the operator as meaningful.
    taxable_base: NonNegativeDecimal | None = None
    iva_rate: Percentage | None = None
    iva_amount: NonNegativeDecimal | None = None
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

    Mirrors :func:`cadrumo.domain.transactions.models.derive_transaction_id`: the id is a
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
    raise InternalInvariantError(
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
    taxable_base: NonNegativeDecimal | None = None
    iva_rate: Percentage | None = None
    iva_amount: NonNegativeDecimal | None = None
    notes: str | None = None


def _resolve_media_kind(source_path: Path) -> MediaKind:
    """Admit a source file by extension, refusing with the accepted set named.

    The suffix decides ADMISSION only. What the document actually IS -- and
    therefore how exactly it can be read -- is derived from its bytes by
    document-shape probe at read time, because
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


def _load(ports: LedgerEvidencePorts, bucket_id: str) -> list[PurchaseInvoiceEvidence]:
    return list(ports.evidence_repository.load(bucket_id=bucket_id))


_EVIDENCE_EVENT_PAYLOAD_VERSION = 1
_EVIDENCE_MUTATION_ATTEMPTS = 4


def prepare_purchase_invoice_evidence_update(
    record: PurchaseInvoiceEvidence,
    patch: PurchaseInvoiceEvidencePatch,
    *,
    updated_at: datetime,
) -> PurchaseInvoiceEvidence:
    """Return the canonical patched record without persisting it.

    The registered worker uses this same preparation path to prove its bounded
    result before it asks the service to commit. The service calls it again for
    each fresh snapshot after a revision conflict.
    """
    data = record.model_dump()
    for key, value in patch.model_dump(exclude_unset=True).items():
        if value is not None:
            data[key] = value
    data["updated_at"] = updated_at
    return PurchaseInvoiceEvidence.model_validate(data)


def _revisioned_mutation_repositories(
    ports: LedgerEvidencePorts,
) -> tuple[RevisionGuardedPurchaseInvoiceEvidenceRepositoryProtocol, BucketEventHistoryRepositoryProtocol]:
    """Require both revision-aware writers before a mutating evidence call."""
    evidence_repository = ports.evidence_repository
    event_repository = ports.bucket_event_repository
    if not isinstance(evidence_repository, RevisionGuardedPurchaseInvoiceEvidenceRepositoryProtocol):
        raise InternalInvariantError("evidence mutation requires a revision-guarded evidence repository")
    if not callable(getattr(event_repository, "load_revisioned", None)):
        raise InternalInvariantError("evidence mutation requires revisioned bucket-event history")
    return evidence_repository, event_repository


def _require_expected_record(
    record: PurchaseInvoiceEvidence,
    *,
    evidence_id: str,
    expected_current: PurchaseInvoiceEvidence | None,
) -> None:
    """Refuse a stale operation preflight before it can change persisted state."""
    if expected_current is not None and (expected_current.evidence_id != evidence_id or record != expected_current):
        raise PurchaseInvoiceEvidenceSnapshotConflictError("purchase invoice evidence changed after preflight")


class PurchaseInvoiceEvidenceSnapshotConflictError(Exception):
    """The target evidence row changed after a result-safety preflight."""


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


def _ingest_evidence_attachment(
    *,
    ports: LedgerEvidencePorts,
    bucket_id: str,
    resolved: Path,
    media_kind: MediaKind,
    now: datetime,
    actor: str,
) -> ContentDigest:
    """Write one admitted evidence file through the application custody port."""
    return ports.attachment_ingestor.ingest(
        EvidenceAttachmentIngestRequest(
            bucket_id=bucket_id,
            source_path=resolved,
            media_kind=media_kind.value,
            mime_type=_SUFFIX_MIME[resolved.suffix.lower()],
            captured_at=now,
            actor=actor,
        ),
    )


class PurchaseInvoiceEvidenceService:
    """Application service for the ``aeat app ledger evidence`` verb group."""

    def __init__(self, *, ports: LedgerEvidencePorts) -> None:
        """Initialise the service with every required evidence capability."""
        self._ports = ports

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
        bytes through the required attachment-ingestion capability (active
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
        evidence_repository, event_repository = _revisioned_mutation_repositories(self._ports)
        keyed_id = (
            derive_keyed_purchase_invoice_evidence_id(bucket_id=bucket_id, idempotency_key=idempotency_key)
            if idempotency_key is not None
            else None
        )
        # Validate the complete domain row before the attachment custodian makes
        # its first durable write. The digest and additive id are the only facts
        # not known yet; valid placeholders have the same bounded wire shape.
        PurchaseInvoiceEvidence(
            evidence_id=keyed_id or "0" * 16,
            bucket_id=bucket_id,
            source_path=str(source_path),
            source_sha256="0" * 64,
            attachment_id="0" * 64,
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
        # The attachment service is the single manifest and encrypted-byte write
        # authority. Ledger retains its narrow PDF/image admission, stable source
        # provenance, and evidence-specific audit lifecycle around that custody write.
        digest = _ingest_evidence_attachment(
            ports=self._ports,
            bucket_id=bucket_id,
            resolved=resolved,
            media_kind=media_kind,
            now=now,
            actor=actor,
        )
        last_conflict: LedgerPersistenceConflictError | None = None
        for _attempt in range(_EVIDENCE_MUTATION_ATTEMPTS):
            snapshot, evidence_revision_id = evidence_repository.load_revisioned(bucket_id=bucket_id)
            records = list(snapshot)
            existing_ids = {existing.evidence_id for existing in records}
            if keyed_id is not None:
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
                    # A keyed replay keeps the original record and does not append
                    # a second event. Attachment ingestion remains a separate
                    # secure-custody write performed once above.
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
                # Argv-faithful breadcrumb: echo the path the operator supplied,
                # never the machine-absolutized form.
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
            event = build_bucket_event(
                bucket_id=bucket_id,
                event_type=BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED,
                occurred_at=now,
                actor=actor,
                object_type=BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE,
                object_id=record.evidence_id,
                # Identity-bearing payload: the content digest plus stable
                # declared metadata, never the source path.
                payload={"media_kind": record.media_kind.value, "source_sha256": record.source_sha256},
                payload_version=_EVIDENCE_EVENT_PAYLOAD_VERSION,
            )
            event_write = bucket_event_history_write(event_repository, (event,))
            try:
                evidence_repository.save_if_revision_with_secure_object_writes(
                    bucket_id=bucket_id,
                    records=(*records, record),
                    expected_revision_id=evidence_revision_id,
                    extra_writes=(event_write,),
                )
            except LedgerPersistenceConflictError as exc:
                last_conflict = exc
                continue
            return PurchaseInvoiceEvidenceResult(record=record, bucket_event_ids=(event.event_id,))
        if last_conflict is not None:
            raise last_conflict
        raise AssertionError("evidence add retries exhausted without a revision conflict")

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
        for record in _load(self._ports, bucket_id):
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
        return tuple(_load(self._ports, bucket_id))

    def update(
        self,
        *,
        bucket_id: str,
        evidence_id: str,
        patch: PurchaseInvoiceEvidencePatch,
        actor: str = "cli",
        expected_current: PurchaseInvoiceEvidence | None = None,
        occurred_at: datetime | None = None,
    ) -> PurchaseInvoiceEvidenceResult:
        """Apply a partial update to an existing evidence record.

        Loads a revisioned bucket snapshot, merges non-``None`` fields from
        ``patch``, stamps ``updated_at``, and commits the catalogue and its
        ``PURCHASE_INVOICE_EVIDENCE_REPLACED`` event in one guarded batch.
        Contention replays the pure patch against a fresh catalogue snapshot.

        Args:
            bucket_id: Ledger bucket containing the record.
            evidence_id: Id of the record to update.
            patch: ``PurchaseInvoiceEvidencePatch`` carrying the fields to
                change. Fields set to ``None`` are left unchanged.
            actor: Identifier stamped on the audit event.
            expected_current: Optional record opened by a bounded result
                preflight. When provided, refuse if that target row changed so
                the caller cannot commit a result it could not safely project.
            occurred_at: Optional fixed transition instant shared with a
                registered worker's result preflight and retry-stable event.

        Returns:
            :class:`PurchaseInvoiceEvidenceResult`: With the updated record and audit
            event id.

        Raises:
            ``PurchaseInvoiceEvidenceNotFoundError``: if no matching record
                exists.
        """
        evidence_repository, event_repository = _revisioned_mutation_repositories(self._ports)
        occurred_at = occurred_at or _utc_now()
        last_conflict: LedgerPersistenceConflictError | None = None
        for _attempt in range(_EVIDENCE_MUTATION_ATTEMPTS):
            snapshot, evidence_revision_id = evidence_repository.load_revisioned(bucket_id=bucket_id)
            records = list(snapshot)
            record_index = next(
                (index for index, record in enumerate(records) if record.evidence_id == evidence_id),
                None,
            )
            if record_index is None:
                raise PurchaseInvoiceEvidenceNotFoundError(
                    translated_message="errors.refused.refused_ledger_evidence_not_found",
                    precondition_verdict=ledger_no_recovery_verdict(
                        LedgerPreconditionCondition.EVIDENCE_REFERENCE_RESOLVES,
                        facts={"evidence_record_present": False},
                    ),
                )
            current = records[record_index]
            if current.bucket_id != bucket_id:
                raise InternalInvariantError("purchase invoice evidence row belongs to another bucket")
            _require_expected_record(current, evidence_id=evidence_id, expected_current=expected_current)
            updated = prepare_purchase_invoice_evidence_update(current, patch, updated_at=occurred_at)
            records[record_index] = updated
            event = build_bucket_event(
                bucket_id=bucket_id,
                event_type=BucketEventType.PURCHASE_INVOICE_EVIDENCE_REPLACED,
                occurred_at=occurred_at,
                actor=actor,
                object_type=BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE,
                object_id=evidence_id,
                payload={"media_kind": updated.media_kind.value},
                payload_version=_EVIDENCE_EVENT_PAYLOAD_VERSION,
            )
            event_write = bucket_event_history_write(event_repository, (event,))
            result = PurchaseInvoiceEvidenceResult(record=updated, bucket_event_ids=(event.event_id,))
            try:
                evidence_repository.save_if_revision_with_secure_object_writes(
                    bucket_id=bucket_id,
                    records=tuple(records),
                    expected_revision_id=evidence_revision_id,
                    extra_writes=(event_write,),
                )
            except LedgerPersistenceConflictError as exc:
                last_conflict = exc
                continue
            return result
        if last_conflict is not None:
            raise last_conflict
        raise AssertionError("evidence update retries exhausted without a revision conflict")

    def remove(
        self,
        *,
        bucket_id: str,
        evidence_id: str,
        actor: str = "cli",
        expected_current: PurchaseInvoiceEvidence | None = None,
    ) -> PurchaseInvoiceEvidenceResult:
        """Remove an evidence record from a bucket.

        Loads a revisioned bucket snapshot and commits the record removal with
        its ``PURCHASE_INVOICE_EVIDENCE_DETACHED`` event in one guarded batch.
        Contention replays the removal against a fresh catalogue snapshot.

        Args:
            bucket_id: Ledger bucket containing the record.
            evidence_id: Id of the record to remove.
            actor: Identifier stamped on the audit event.
            expected_current: Optional record opened by a bounded result
                preflight. When provided, refuse if that target row changed so
                the caller cannot commit a result it could not safely project.

        Returns:
            :class:`PurchaseInvoiceEvidenceResult`: Carrying the removed record and
            the audit event id.

        Raises:
            ``PurchaseInvoiceEvidenceNotFoundError``: if no matching record
                exists.
        """
        evidence_repository, event_repository = _revisioned_mutation_repositories(self._ports)
        occurred_at = _utc_now()
        last_conflict: LedgerPersistenceConflictError | None = None
        for _attempt in range(_EVIDENCE_MUTATION_ATTEMPTS):
            snapshot, evidence_revision_id = evidence_repository.load_revisioned(bucket_id=bucket_id)
            records = list(snapshot)
            record_index = next(
                (index for index, record in enumerate(records) if record.evidence_id == evidence_id),
                None,
            )
            if record_index is None:
                raise PurchaseInvoiceEvidenceNotFoundError(
                    translated_message="errors.refused.refused_ledger_evidence_not_found",
                    precondition_verdict=ledger_no_recovery_verdict(
                        LedgerPreconditionCondition.EVIDENCE_REFERENCE_RESOLVES,
                        facts={"evidence_record_present": False},
                    ),
                )
            removed = records[record_index]
            if removed.bucket_id != bucket_id:
                raise InternalInvariantError("purchase invoice evidence row belongs to another bucket")
            _require_expected_record(removed, evidence_id=evidence_id, expected_current=expected_current)
            records.pop(record_index)
            event = build_bucket_event(
                bucket_id=bucket_id,
                event_type=BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED,
                occurred_at=occurred_at,
                actor=actor,
                object_type=BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE,
                object_id=evidence_id,
                payload={"media_kind": removed.media_kind.value},
                payload_version=_EVIDENCE_EVENT_PAYLOAD_VERSION,
            )
            event_write = bucket_event_history_write(event_repository, (event,))
            result = PurchaseInvoiceEvidenceResult(record=removed, bucket_event_ids=(event.event_id,))
            try:
                evidence_repository.save_if_revision_with_secure_object_writes(
                    bucket_id=bucket_id,
                    records=tuple(records),
                    expected_revision_id=evidence_revision_id,
                    extra_writes=(event_write,),
                )
            except LedgerPersistenceConflictError as exc:
                last_conflict = exc
                continue
            return result
        if last_conflict is not None:
            raise last_conflict
        raise AssertionError("evidence remove retries exhausted without a revision conflict")


# Public supporting contract for sibling ledger action services, matching the
# shape `_actions_common` declares. The evidence event emitter is shared: this
# module raises it on the evidence paths, and the LLM review workflow raises the
# same event for a declined draft, which never becomes a transaction.
emit_evidence_event = _emit_evidence_event

__all__ = [
    "PurchaseInvoiceEvidence",
    "PurchaseInvoiceEvidenceDocument",
    "PurchaseInvoiceEvidencePatch",
    "PurchaseInvoiceEvidenceResult",
    "PurchaseInvoiceEvidenceService",
    "PurchaseInvoiceEvidenceSnapshotConflictError",
    "derive_keyed_purchase_invoice_evidence_id",
    "emit_evidence_event",
    "prepare_purchase_invoice_evidence_update",
]
