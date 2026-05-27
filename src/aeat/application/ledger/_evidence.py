"""Purchase invoice evidence records and the CRUD application service.

``aeat app ledger evidence {add|remove|update|view|list}`` operate over a
:class:`PurchaseInvoiceEvidence` pydantic record.

File-type scope is restricted to PDF and image inputs handled by the OCR
path. Plaintext, email body, and Drive-URL evidence sources are out of
scope. ``add`` refuses non-PDF/non-image
source paths with a typed :class:`PurchaseInvoiceEvidenceInputError`.

Persistence is a bucket-scoped JSON file under
``Settings.aeat_purchase_invoice_evidence_dir / <bucket_id>.jsonl``. Each
line is one evidence record encoded as JSON. The format is deliberately
append-only friendly so concurrent agents do not corrupt previous rows.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from ...core.config import Settings
from ...core.errors import AeatError
from ...domain.buckets import (
    BucketEvent,
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
    append_bucket_event,
    derive_bucket_event_id,
)

_PDF_EXTENSIONS = frozenset({".pdf"})
_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".heic", ".heif"})

_DEFERRED_ADR_REF = "evidence-source-expansion (deferred; only PDF and image inputs are accepted)"


class PurchaseInvoiceEvidenceInputError(AeatError):
    """Raised when a CLI-supplied evidence input violates the typed contract."""


class PurchaseInvoiceEvidenceNotFoundError(AeatError):
    """Raised when a CLI lookup targets a missing evidence record."""


class PurchaseInvoiceEvidence(BaseModel):
    """One persisted purchase invoice evidence record."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    evidence_id: str = Field(min_length=1, max_length=64)
    bucket_id: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    source_sha256: str = Field(min_length=64, max_length=64)
    media_kind: str = Field(pattern=r"^(pdf|image)$")
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


class PurchaseInvoiceEvidencePatch(BaseModel):
    """Mutable subset of fields accepted by ``update``."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    supplier: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    taxable_base: Decimal | None = None
    iva_rate: Decimal | None = None
    iva_amount: Decimal | None = None
    notes: str | None = None


def _resolve_media_kind(source_path: Path) -> str:
    suffix = source_path.suffix.lower()
    if suffix in _PDF_EXTENSIONS:
        return "pdf"
    if suffix in _IMAGE_EXTENSIONS:
        return "image"
    raise PurchaseInvoiceEvidenceInputError(
        f"source path {source_path!s} has unsupported extension {suffix!r}; "
        f"only PDF and image inputs are accepted. See {_DEFERRED_ADR_REF}.",
        suggestion="aeat app ledger evidence list",
    )


def _hash_file(source_path: Path) -> str:
    hasher = hashlib.sha256()
    with source_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


class PurchaseInvoiceEvidenceResult(BaseModel):
    """Return record from a mutating evidence verb — record plus emitted event id."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    record: PurchaseInvoiceEvidence
    bucket_event_ids: tuple[str, ...] = ()


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _storage_path(settings: Settings, bucket_id: str) -> Path:
    return settings.aeat_purchase_invoice_evidence_dir / f"{bucket_id}.jsonl"


def _load(settings: Settings, bucket_id: str) -> list[PurchaseInvoiceEvidence]:
    path = _storage_path(settings, bucket_id)
    if not path.is_file():
        return []
    records: list[PurchaseInvoiceEvidence] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        records.append(PurchaseInvoiceEvidence.model_validate_json(line))
    return records


def _save(settings: Settings, bucket_id: str, records: list[PurchaseInvoiceEvidence]) -> None:
    path = _storage_path(settings, bucket_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(record.model_dump_json() for record in records)
    if body:
        body += "\n"
    path.write_text(body, encoding="utf-8")


_EVIDENCE_EVENT_PAYLOAD_VERSION = 1


def _build_evidence_event(
    *,
    bucket_id: str,
    event_type: BucketEventType,
    evidence_id: str,
    actor: str,
    occurred_at: datetime,
    payload: dict[str, str],
) -> BucketEvent:
    return BucketEvent(
        event_id=derive_bucket_event_id(
            bucket_id=bucket_id,
            event_type=event_type,
            occurred_at=occurred_at,
            actor=actor,
            object_type=BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE,
            object_id=evidence_id,
            payload=payload,
        ),
        bucket_id=bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=BucketEventObjectType.PURCHASE_INVOICE_EVIDENCE,
        object_id=evidence_id,
        payload_version=_EVIDENCE_EVENT_PAYLOAD_VERSION,
        payload=payload,
    )


def _emit_evidence_event(
    *,
    event_repository: BucketEventHistoryRepository,
    bucket_id: str,
    event_type: BucketEventType,
    evidence_id: str,
    actor: str,
    occurred_at: datetime,
    payload: dict[str, str],
) -> str:
    event = _build_evidence_event(
        bucket_id=bucket_id,
        event_type=event_type,
        evidence_id=evidence_id,
        actor=actor,
        occurred_at=occurred_at,
        payload=payload,
    )
    event_repository.save(append_bucket_event(event_repository.load(), event))
    return event.event_id


class PurchaseInvoiceEvidenceService:
    """Application service for the ``aeat app ledger evidence`` verb group."""

    def __init__(
        self,
        settings: Settings | None = None,
        bucket_event_repository: BucketEventHistoryRepository | None = None,
    ) -> None:
        # `load_settings()` honours `override_settings`; bare `Settings()`
        # bypasses the context-var and lands writes in the project default.
        from ...core.config import load_settings as _load_settings
        self._settings = settings or _load_settings()
        self._event_repository = bucket_event_repository or BucketEventHistoryRepository()

    def add(
        self,
        *,
        bucket_id: str,
        source_path: Path,
        supplier: str | None = None,
        invoice_number: str | None = None,
        invoice_date: str | None = None,
        taxable_base: Decimal | None = None,
        iva_rate: Decimal | None = None,
        iva_amount: Decimal | None = None,
        notes: str = "",
        actor: str = "cli",
    ) -> PurchaseInvoiceEvidenceResult:
        resolved = Path(source_path).expanduser().resolve()
        if not resolved.is_file():
            raise PurchaseInvoiceEvidenceInputError(
                f"source path {source_path!s} is not a readable file",
                suggestion="aeat app ledger evidence list",
            )
        media_kind = _resolve_media_kind(resolved)
        digest = _hash_file(resolved)
        now = _now()
        record = PurchaseInvoiceEvidence(
            evidence_id=uuid.uuid4().hex[:16],
            bucket_id=bucket_id,
            source_path=str(resolved),
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
            updated_at=now,
        )
        records = _load(self._settings, bucket_id)
        records.append(record)
        _save(self._settings, bucket_id, records)
        event_id = _emit_evidence_event(
            event_repository=self._event_repository,
            bucket_id=bucket_id,
            event_type=BucketEventType.PURCHASE_INVOICE_EVIDENCE_ATTACHED,
            evidence_id=record.evidence_id,
            actor=actor,
            occurred_at=now,
            payload={"media_kind": record.media_kind, "source_path": record.source_path},
        )
        return PurchaseInvoiceEvidenceResult(record=record, bucket_event_ids=(event_id,))

    def view(self, *, bucket_id: str, evidence_id: str) -> PurchaseInvoiceEvidence:
        for record in _load(self._settings, bucket_id):
            if record.evidence_id == evidence_id:
                return record
        raise PurchaseInvoiceEvidenceNotFoundError(
            f"no purchase invoice evidence record with id {evidence_id!r} in bucket {bucket_id!r}",
            suggestion="aeat app ledger evidence list",
        )

    def list_all(self, *, bucket_id: str) -> tuple[PurchaseInvoiceEvidence, ...]:
        return tuple(_load(self._settings, bucket_id))

    def update(
        self,
        *,
        bucket_id: str,
        evidence_id: str,
        patch: PurchaseInvoiceEvidencePatch,
        actor: str = "cli",
    ) -> PurchaseInvoiceEvidenceResult:
        records = _load(self._settings, bucket_id)
        for index, record in enumerate(records):
            if record.evidence_id != evidence_id:
                continue
            data = record.model_dump()
            for key, value in patch.model_dump(exclude_unset=True).items():
                if value is not None:
                    data[key] = value
            now = _now()
            data["updated_at"] = now
            updated = PurchaseInvoiceEvidence.model_validate(data)
            records[index] = updated
            _save(self._settings, bucket_id, records)
            event_id = _emit_evidence_event(
                event_repository=self._event_repository,
                bucket_id=bucket_id,
                event_type=BucketEventType.PURCHASE_INVOICE_EVIDENCE_REPLACED,
                evidence_id=evidence_id,
                actor=actor,
                occurred_at=now,
                payload={"media_kind": updated.media_kind},
            )
            return PurchaseInvoiceEvidenceResult(record=updated, bucket_event_ids=(event_id,))
        raise PurchaseInvoiceEvidenceNotFoundError(
            f"no purchase invoice evidence record with id {evidence_id!r} in bucket {bucket_id!r}",
            suggestion="aeat app ledger evidence list",
        )

    def remove(
        self,
        *,
        bucket_id: str,
        evidence_id: str,
        actor: str = "cli",
    ) -> PurchaseInvoiceEvidenceResult:
        records = _load(self._settings, bucket_id)
        for index, record in enumerate(records):
            if record.evidence_id == evidence_id:
                removed = records.pop(index)
                _save(self._settings, bucket_id, records)
                now = _now()
                event_id = _emit_evidence_event(
                    event_repository=self._event_repository,
                    bucket_id=bucket_id,
                    event_type=BucketEventType.PURCHASE_INVOICE_EVIDENCE_DETACHED,
                    evidence_id=evidence_id,
                    actor=actor,
                    occurred_at=now,
                    payload={"media_kind": removed.media_kind},
                )
                return PurchaseInvoiceEvidenceResult(record=removed, bucket_event_ids=(event_id,))
        raise PurchaseInvoiceEvidenceNotFoundError(
            f"no purchase invoice evidence record with id {evidence_id!r} in bucket {bucket_id!r}",
            suggestion="aeat app ledger evidence list",
        )


__all__ = [
    "PurchaseInvoiceEvidence",
    "PurchaseInvoiceEvidenceInputError",
    "PurchaseInvoiceEvidenceNotFoundError",
    "PurchaseInvoiceEvidencePatch",
    "PurchaseInvoiceEvidenceResult",
    "PurchaseInvoiceEvidenceService",
]
