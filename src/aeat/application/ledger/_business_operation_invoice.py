"""Payable and collectible invoice CRUD services.

Two noun-groups (``payable_invoice``, ``collectible_invoice``) each
expose the canonical five-verb CRUD spine
``add``/``remove``/``update``/``view``/``list``. Records are
bucket-scoped and persisted as JSONL files per noun-kind.

The records are intentionally slim. Business-detail enrichment (line
items, IVA breakdown, reconciliation linkages) belongs to the
:mod:`aeat.domain.invoices` richer ``Invoice`` aggregate consumed by
modelo aggregation pipelines. The noun-group records here are the
canonical operator-edit surface for the two source-kind variants
covered.

Bucket events emitted per CRUD verb:
    ``add``     -> ``payable_invoice.created`` / ``collectible_invoice.created``
    ``update``  -> ``payable_invoice.updated`` / ``collectible_invoice.updated``
    ``remove``  -> ``payable_invoice.removed`` / ``collectible_invoice.removed``

Read verbs (``view``, ``list``) emit no bucket event per the
MutatingNounGroupContract.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from ...core.config import Settings
from ...core.errors import AeatError
from ...domain.buckets import (
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
    append_bucket_event,
)


class BusinessOperationInvoiceSourceKind(StrEnum):
    """The two source-kind variants this module covers."""

    PAYABLE_INVOICE = "payable_invoice"
    COLLECTIBLE_INVOICE = "collectible_invoice"


class BusinessOperationInvoiceInputError(AeatError):
    """Raised when a CLI-supplied input violates the typed contract."""


class BusinessOperationInvoiceNotFoundError(AeatError):
    """Raised when a CLI lookup targets a missing record."""


class BusinessOperationInvoice(BaseModel):
    """One persisted payable- or collectible-invoice record.

    The ``source_kind`` discriminator binds the record to one of the two
    locked source-kind taxonomy values. ``invoice_id`` is the noun-group's
    full_id; mutating verbs accept either ``invoice_id`` or any
    unambiguous prefix per the 2026-05-14 transaction-identity amendment.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    invoice_id: str = Field(min_length=1, max_length=64)
    source_kind: BusinessOperationInvoiceSourceKind
    bucket_id: str = Field(min_length=1)
    counterparty_nif: str = Field(min_length=1)
    counterparty_name: str = Field(default="", max_length=200)
    invoice_number: str = Field(min_length=1, max_length=100)
    invoice_date: str = Field(min_length=10, max_length=10)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    taxable_base: Decimal = Field(default=Decimal("0"))
    iva_rate: Decimal | None = Field(default=None)
    iva_amount: Decimal = Field(default=Decimal("0"))
    total_amount: Decimal = Field(default=Decimal("0"))
    notes: str = Field(default="", max_length=2000)
    created_at: datetime
    updated_at: datetime

    @field_serializer("taxable_base", "iva_amount", "total_amount", "iva_rate", when_used="json")
    def _serialize_decimal(self, value: Decimal | None) -> str | None:
        if value is None:
            return None
        return format(value, "f")


class BusinessOperationInvoicePatch(BaseModel):
    """Partial update payload for an existing record.

    Every field is optional; only provided fields overwrite the existing
    record. ``invoice_id``, ``source_kind``, and ``bucket_id`` are
    immutable and cannot be patched.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    counterparty_nif: str | None = Field(default=None, min_length=1)
    counterparty_name: str | None = Field(default=None, max_length=200)
    invoice_number: str | None = Field(default=None, min_length=1, max_length=100)
    invoice_date: str | None = Field(default=None, min_length=10, max_length=10)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    taxable_base: Decimal | None = Field(default=None)
    iva_rate: Decimal | None = Field(default=None)
    iva_amount: Decimal | None = Field(default=None)
    total_amount: Decimal | None = Field(default=None)
    notes: str | None = Field(default=None, max_length=2000)


class BusinessOperationInvoiceResult(BaseModel):
    """Return record from a mutating invoice verb — record plus emitted event id."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    record: BusinessOperationInvoice
    bucket_event_ids: tuple[str, ...] = ()


_INVOICE_EVENT_PAYLOAD_VERSION = 1

# Map source_kind to the three event types (created, updated, removed).
_EVENT_MAP: dict[str, tuple[BucketEventType, BucketEventType, BucketEventType]] = {
    "payable_invoice": (
        BucketEventType.PAYABLE_INVOICE_CREATED,
        BucketEventType.PAYABLE_INVOICE_UPDATED,
        BucketEventType.PAYABLE_INVOICE_REMOVED,
    ),
    "collectible_invoice": (
        BucketEventType.COLLECTIBLE_INVOICE_CREATED,
        BucketEventType.COLLECTIBLE_INVOICE_UPDATED,
        BucketEventType.COLLECTIBLE_INVOICE_REMOVED,
    ),
}

_OBJECT_TYPE_MAP: dict[str, BucketEventObjectType] = {
    "payable_invoice": BucketEventObjectType.PAYABLE_INVOICE,
    "collectible_invoice": BucketEventObjectType.COLLECTIBLE_INVOICE,
}


def _emit_invoice_event(
    *,
    event_repository: BucketEventHistoryRepository,
    record: BusinessOperationInvoice,
    event_type: BucketEventType,
    occurred_at: datetime,
    actor: str,
) -> str:
    from ...domain.buckets._event import BucketEvent, derive_bucket_event_id

    object_type = _OBJECT_TYPE_MAP[record.source_kind.value]
    payload = {
        "invoice_number": record.invoice_number,
        "invoice_date": record.invoice_date,
        "counterparty_nif": record.counterparty_nif,
    }
    event = BucketEvent(
        event_id=derive_bucket_event_id(
            bucket_id=record.bucket_id,
            event_type=event_type,
            occurred_at=occurred_at,
            actor=actor,
            object_type=object_type,
            object_id=record.invoice_id,
            payload=payload,
        ),
        bucket_id=record.bucket_id,
        event_type=event_type,
        occurred_at=occurred_at,
        actor=actor,
        object_type=object_type,
        object_id=record.invoice_id,
        payload_version=_INVOICE_EVENT_PAYLOAD_VERSION,
        payload=payload,
    )
    event_repository.save(append_bucket_event(event_repository.load(), event))
    return event.event_id


def _now() -> datetime:
    return datetime.now(tz=UTC)


def _storage_path(settings: Settings, kind: BusinessOperationInvoiceSourceKind, bucket_id: str) -> Path:
    root = settings.aeat_invoices_dir / kind.value
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{bucket_id}.jsonl"


def _load(
    settings: Settings, kind: BusinessOperationInvoiceSourceKind, bucket_id: str
) -> list[BusinessOperationInvoice]:
    path = _storage_path(settings, kind, bucket_id)
    if not path.exists():
        return []
    records: list[BusinessOperationInvoice] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        records.append(BusinessOperationInvoice.model_validate_json(line))
    return records


def _save(
    settings: Settings,
    kind: BusinessOperationInvoiceSourceKind,
    bucket_id: str,
    records: list[BusinessOperationInvoice],
) -> None:
    path = _storage_path(settings, kind, bucket_id)
    payload = "\n".join(record.model_dump_json() for record in records)
    if payload:
        payload += "\n"
    path.write_text(payload, encoding="utf-8")


def _resolve_id(records: list[BusinessOperationInvoice], id_or_prefix: str) -> BusinessOperationInvoice:
    matches = [r for r in records if r.invoice_id == id_or_prefix or r.invoice_id.startswith(id_or_prefix)]
    if not matches:
        raise BusinessOperationInvoiceNotFoundError(
            f"no invoice record matches {id_or_prefix!r}",
            suggestion="list",
        )
    if len(matches) > 1:
        full_ids = sorted(r.invoice_id for r in matches)
        raise BusinessOperationInvoiceInputError(
            f"prefix {id_or_prefix!r} is ambiguous; matches {full_ids!r}",
            suggestion="provide a longer prefix or the full invoice_id",
        )
    return matches[0]


class _BusinessOperationInvoiceService:
    """Shared CRUD implementation for payable and collectible noun-groups.

    Concrete services (:class:`PayableInvoiceService`,
    :class:`CollectibleInvoiceService`) bind the source-kind discriminator.
    """

    source_kind: BusinessOperationInvoiceSourceKind

    def __init__(
        self,
        settings: Settings | None = None,
        bucket_event_repository: BucketEventHistoryRepository | None = None,
    ) -> None:
        self._settings = settings or Settings()
        self._event_repository = bucket_event_repository or BucketEventHistoryRepository()

    def add(
        self,
        *,
        bucket_id: str,
        counterparty_nif: str,
        invoice_number: str,
        invoice_date: str,
        counterparty_name: str = "",
        currency: str = "EUR",
        taxable_base: Decimal = Decimal("0"),
        iva_rate: Decimal | None = None,
        iva_amount: Decimal = Decimal("0"),
        total_amount: Decimal = Decimal("0"),
        notes: str = "",
        actor: str = "cli",
    ) -> BusinessOperationInvoiceResult:
        now = _now()
        record = BusinessOperationInvoice(
            invoice_id=uuid.uuid4().hex[:16],
            source_kind=self.source_kind,
            bucket_id=bucket_id,
            counterparty_nif=counterparty_nif,
            counterparty_name=counterparty_name,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            currency=currency,
            taxable_base=taxable_base,
            iva_rate=iva_rate,
            iva_amount=iva_amount,
            total_amount=total_amount,
            notes=notes,
            created_at=now,
            updated_at=now,
        )
        records = _load(self._settings, self.source_kind, bucket_id)
        records.append(record)
        _save(self._settings, self.source_kind, bucket_id, records)
        created_type = _EVENT_MAP[self.source_kind.value][0]
        event_id = _emit_invoice_event(
            event_repository=self._event_repository,
            record=record,
            event_type=created_type,
            occurred_at=now,
            actor=actor,
        )
        return BusinessOperationInvoiceResult(record=record, bucket_event_ids=(event_id,))

    def view(self, *, bucket_id: str, invoice_id: str) -> BusinessOperationInvoice:
        records = _load(self._settings, self.source_kind, bucket_id)
        return _resolve_id(records, invoice_id)

    def list_all(self, *, bucket_id: str) -> tuple[BusinessOperationInvoice, ...]:
        return tuple(_load(self._settings, self.source_kind, bucket_id))

    def update(
        self,
        *,
        bucket_id: str,
        invoice_id: str,
        patch: BusinessOperationInvoicePatch,
        actor: str = "cli",
    ) -> BusinessOperationInvoiceResult:
        records = _load(self._settings, self.source_kind, bucket_id)
        target = _resolve_id(records, invoice_id)
        index = records.index(target)
        data = target.model_dump()
        for key, value in patch.model_dump(exclude_unset=True).items():
            if value is not None:
                data[key] = value
        now = _now()
        data["updated_at"] = now
        updated = BusinessOperationInvoice.model_validate(data)
        records[index] = updated
        _save(self._settings, self.source_kind, bucket_id, records)
        updated_type = _EVENT_MAP[self.source_kind.value][1]
        event_id = _emit_invoice_event(
            event_repository=self._event_repository,
            record=updated,
            event_type=updated_type,
            occurred_at=now,
            actor=actor,
        )
        return BusinessOperationInvoiceResult(record=updated, bucket_event_ids=(event_id,))

    def remove(
        self,
        *,
        bucket_id: str,
        invoice_id: str,
        actor: str = "cli",
    ) -> BusinessOperationInvoiceResult:
        records = _load(self._settings, self.source_kind, bucket_id)
        target = _resolve_id(records, invoice_id)
        records.remove(target)
        now = _now()
        _save(self._settings, self.source_kind, bucket_id, records)
        removed_type = _EVENT_MAP[self.source_kind.value][2]
        event_id = _emit_invoice_event(
            event_repository=self._event_repository,
            record=target,
            event_type=removed_type,
            occurred_at=now,
            actor=actor,
        )
        return BusinessOperationInvoiceResult(record=target, bucket_event_ids=(event_id,))


class PayableInvoiceService(_BusinessOperationInvoiceService):
    """CRUD service for ``payable_invoice`` records (we owe vendor)."""

    source_kind = BusinessOperationInvoiceSourceKind.PAYABLE_INVOICE


class CollectibleInvoiceService(_BusinessOperationInvoiceService):
    """CRUD service for ``collectible_invoice`` records (customer owes us)."""

    source_kind = BusinessOperationInvoiceSourceKind.COLLECTIBLE_INVOICE


__all__ = [
    "BusinessOperationInvoice",
    "BusinessOperationInvoiceInputError",
    "BusinessOperationInvoiceNotFoundError",
    "BusinessOperationInvoicePatch",
    "BusinessOperationInvoiceResult",
    "BusinessOperationInvoiceSourceKind",
    "CollectibleInvoiceService",
    "PayableInvoiceService",
]
