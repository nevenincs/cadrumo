"""Payable and collectible invoice CRUD services.

Two noun-groups (``payable_invoice``, ``collectible_invoice``) each
expose the canonical five-verb CRUD spine
``add``/``remove``/``update``/``view``/``list``. Records are
bucket-scoped and persisted as encrypted secure-object documents per noun-kind.

The records are intentionally slim. Business-detail enrichment (line
items, IVA breakdown, reconciliation linkages) belongs to the
:mod:`aeat.domain.invoices` richer ``Invoice`` aggregate consumed by
modelo aggregation pipelines. The noun-group records here are the
canonical operator-edit surface for the two source-kind variants
covered.

Bucket events emitted per mutating verb via :class:`BucketEventHistoryRepository`:
    ``add``     -> ``payable_invoice.created`` / ``collectible_invoice.created``
    ``update``  -> ``payable_invoice.updated`` / ``collectible_invoice.updated``
    ``remove``  -> ``payable_invoice.removed`` / ``collectible_invoice.removed``

Read verbs (``view``, ``list``) emit no bucket event per the
MutatingNounGroupContract.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import override

from pydantic import BaseModel, Field, field_serializer, field_validator

from ...adapters.persistence.storage import LEDGER_BUSINESS_OPERATION_INVOICE_NAMESPACE
from ...adapters.persistence.storage.envelope import SecureBoundRepository
from ...adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ...core import STRICT_FROZEN_CONFIG
from ...core.aggregation import IntracomOperationType
from ...core.config import Settings
from ...core.errors import AeatError
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.identity import BucketId
from ...core.time import now as _utc_now
from ...domain.buckets import (
    BucketEventHistoryRepository,
    BucketEventObjectType,
    BucketEventType,
    append_bucket_event,
)
from ...domain.buckets._protocols import BucketEventHistoryRepositoryProtocol


class BusinessOperationInvoiceDirection(StrEnum):
    """The two invoice-direction variants this module covers.

    The member string values (``payable_invoice`` / ``collectible_invoice``)
    are the load-bearing internal source-kind taxonomy per
    ``aeat-spanish-stem-naming`` and are preserved; only the enum TYPE name
    is the direction axis.
    """

    PAYABLE_INVOICE = "payable_invoice"
    COLLECTIBLE_INVOICE = "collectible_invoice"


class BusinessOperationInvoiceInputError(AeatError):
    """Raised when a CLI-supplied input violates the typed contract."""


class BusinessOperationInvoiceNotFoundError(AeatError):
    """Raised when a CLI lookup targets a missing record."""


# EU IVA-ID format patterns keyed by ISO 3166-1 alpha-2 country code (uppercase).
# Sources: EU Commission VIES documentation + member-state tax authority publications.
_EU_IVA_PATTERNS: dict[str, re.Pattern[str]] = {
    "AT": re.compile(r"^ATU\d{8}$"),
    "BE": re.compile(r"^BE0\d{9}$"),
    "BG": re.compile(r"^BG\d{9,10}$"),
    "CY": re.compile(r"^CY\d{8}[A-Z]$"),
    "CZ": re.compile(r"^CZ\d{8,10}$"),
    "DE": re.compile(r"^DE\d{9}$"),
    "DK": re.compile(r"^DK\d{8}$"),
    "EE": re.compile(r"^EE\d{9}$"),
    "ES": re.compile(r"^ES[A-Z0-9]\d{7}[A-Z0-9]$"),
    "FI": re.compile(r"^FI\d{8}$"),
    "FR": re.compile(r"^FR[A-Z0-9]{2}\d{9}$"),
    "GR": re.compile(r"^EL\d{9}$"),
    "HR": re.compile(r"^HR\d{11}$"),
    "HU": re.compile(r"^HU\d{8}$"),
    "IE": re.compile(r"^IE\d{7}[A-Z]{1,2}$"),
    "IT": re.compile(r"^IT\d{11}$"),
    "LT": re.compile(r"^LT(\d{9}|\d{12})$"),
    "LU": re.compile(r"^LU\d{8}$"),
    "LV": re.compile(r"^LV\d{11}$"),
    "MT": re.compile(r"^MT\d{8}$"),
    "NL": re.compile(r"^NL\d{9}B\d{2}$"),
    "PL": re.compile(r"^PL\d{10}$"),
    "PT": re.compile(r"^PT\d{9}$"),
    "RO": re.compile(r"^RO\d{2,10}$"),
    "SE": re.compile(r"^SE\d{12}$"),
    "SI": re.compile(r"^SI\d{8}$"),
    "SK": re.compile(r"^SK\d{10}$"),
    "XI": re.compile(r"^XI[0-9A-Z]{5}$|^XI[0-9A-Z]{9}$|^XI[0-9A-Z]{12}$"),
}


def validate_eu_iva_id(raw: str) -> str:
    """Normalise and validate an EU IVA-ID.

    Strips whitespace and hyphens, uppercases, then checks the two-letter
    country prefix against the per-member-state pattern table.

    Returns the normalised value on success. Raises
    :class:`BusinessOperationInvoiceInputError` on format mismatch.
    """
    normalised = raw.strip().upper().replace(" ", "").replace("-", "")
    if len(normalised) < 4 or not normalised[:2].isalpha():
        raise BusinessOperationInvoiceInputError(
            f"EU IVA-ID {raw!r} must start with a 2-letter EU country code",
            suggestion="example: DE345678901, FR12345678901",
        )
    prefix = normalised[:2]
    # Greece uses EL prefix in IVA-IDs but GR in ISO 3166-1; map to its pattern.
    pattern_key = "GR" if prefix == "EL" else prefix
    pattern = _EU_IVA_PATTERNS.get(pattern_key)
    if pattern is None:
        raise BusinessOperationInvoiceInputError(
            f"EU IVA-ID prefix {prefix!r} does not correspond to an EU member state",
            suggestion="use one of: " + ", ".join(sorted(_EU_IVA_PATTERNS)),
        )
    if not pattern.match(normalised):
        raise BusinessOperationInvoiceInputError(
            f"EU IVA-ID {raw!r} does not match the expected format for {prefix}",
            suggestion=f"pattern: {pattern.pattern}",
        )
    return normalised


class BusinessOperationInvoice(BaseModel):
    """One persisted payable- or collectible-invoice record.

    The ``source_kind`` discriminator binds the record to one of the two
    locked source-kind taxonomy values. ``invoice_id`` is the noun-group's
    full_id; mutating verbs accept either ``invoice_id`` or any
    unambiguous prefix for partial-id matching.

    Intracom fields (``country_code``, ``eu_iva_id``, ``operation_type``)
    are ``None`` for domestic invoices and are set for EU intracomunitaria
    operations that feed M349 aggregation. Existing records without these
    fields grandfather in as ``None`` (schema migration per spec §5).
    """

    model_config = STRICT_FROZEN_CONFIG

    invoice_id: str = Field(min_length=1, max_length=64)
    source_kind: BusinessOperationInvoiceDirection
    bucket_id: BucketId
    counterparty_nif: str = Field(min_length=1)
    counterparty_name: str = Field(default="", max_length=200)
    invoice_number: str = Field(min_length=1, max_length=100)
    invoice_date: str = Field(min_length=10, max_length=10)
    currency: str = Field(default=DEFAULT_CURRENCY, min_length=3, max_length=3)
    taxable_base: Decimal = Field(default=Decimal("0"))
    iva_rate: Decimal | None = Field(default=None)
    iva_amount: Decimal = Field(default=Decimal("0"))
    total_amount: Decimal = Field(default=Decimal("0"))
    notes: str = Field(default="", max_length=2000)
    # Intracom EU fields — None for domestic invoices.
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    eu_iva_id: str | None = Field(default=None, max_length=20)
    operation_type: IntracomOperationType | None = Field(default=None)
    created_at: datetime
    updated_at: datetime

    @field_validator("country_code")
    @classmethod
    def _normalise_country_code(cls, v: str | None) -> str | None:
        return v.upper() if v is not None else None

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

    model_config = STRICT_FROZEN_CONFIG

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
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    eu_iva_id: str | None = Field(default=None, max_length=20)
    operation_type: IntracomOperationType | None = Field(default=None)


class BusinessOperationInvoiceResult(BaseModel):
    """Return record from a mutating invoice verb — record plus emitted event id."""

    model_config = STRICT_FROZEN_CONFIG

    record: BusinessOperationInvoice
    bucket_event_ids: tuple[str, ...] = ()


class BusinessOperationInvoiceDocument(BaseModel):
    """Encrypted bucket-local business-operation invoice catalogue."""

    model_config = STRICT_FROZEN_CONFIG

    bucket_id: BucketId
    source_kind: BusinessOperationInvoiceDirection
    records: tuple[BusinessOperationInvoice, ...] = ()


class BusinessOperationInvoiceRepository(SecureBoundRepository[BusinessOperationInvoiceDocument]):
    """Encrypted repository for one bucket/source-kind invoice catalogue."""

    namespace = LEDGER_BUSINESS_OPERATION_INVOICE_NAMESPACE.namespace
    sensitivity = LEDGER_BUSINESS_OPERATION_INVOICE_NAMESPACE.sensitivity
    schema_version = LEDGER_BUSINESS_OPERATION_INVOICE_NAMESPACE.schema_version
    payload_type = BusinessOperationInvoiceDocument

    @override
    def extract_identifier(self, payload: BusinessOperationInvoiceDocument) -> str:
        return _document_key(payload.bucket_id, payload.source_kind)


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
    event_repository: BucketEventHistoryRepositoryProtocol,
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


def _load(
    settings: Settings,
    kind: BusinessOperationInvoiceDirection,
    bucket_id: str,
) -> list[BusinessOperationInvoice]:
    document = _repository(settings, bucket_id).load(_document_key(bucket_id, kind))
    return list(document.records) if document is not None else []


def _save(
    settings: Settings,
    kind: BusinessOperationInvoiceDirection,
    bucket_id: str,
    records: list[BusinessOperationInvoice],
) -> None:
    _repository(settings, bucket_id).save(
        BusinessOperationInvoiceDocument(
            bucket_id=bucket_id,
            source_kind=kind,
            records=tuple(records),
        ),
    )


def _repository(settings: Settings, bucket_id: str) -> BusinessOperationInvoiceRepository:
    return BusinessOperationInvoiceRepository(objects=secure_object_repository_for_bucket(bucket_id, settings))


def _document_key(bucket_id: str, kind: BusinessOperationInvoiceDirection) -> str:
    return f"{bucket_id}:{kind.value}"


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

    source_kind: BusinessOperationInvoiceDirection

    def __init__(
        self,
        settings: Settings | None = None,
        bucket_event_repository: BucketEventHistoryRepositoryProtocol | None = None,
    ) -> None:
        # `Settings()` bypasses the `override_settings` context-var, so
        # route through `load_settings()` before resolving the runtime
        # secure-object repository.
        from ...core.config import load_settings as _load_settings

        self._settings = settings or _load_settings()
        self._event_repository = bucket_event_repository

    def add(
        self,
        *,
        bucket_id: str,
        counterparty_nif: str,
        invoice_number: str,
        invoice_date: str,
        counterparty_name: str = "",
        currency: str = DEFAULT_CURRENCY,
        taxable_base: Decimal = Decimal("0"),
        iva_rate: Decimal | None = None,
        iva_amount: Decimal = Decimal("0"),
        total_amount: Decimal = Decimal("0"),
        notes: str = "",
        country_code: str | None = None,
        eu_iva_id: str | None = None,
        operation_type: IntracomOperationType | None = None,
        actor: str = "cli",
    ) -> BusinessOperationInvoiceResult:
        now = _utc_now()
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
            country_code=country_code,
            eu_iva_id=eu_iva_id,
            operation_type=operation_type,
            created_at=now,
            updated_at=now,
        )
        records = _load(self._settings, self.source_kind, bucket_id)
        records.append(record)
        _save(self._settings, self.source_kind, bucket_id, records)
        created_type = _EVENT_MAP[self.source_kind.value][0]
        event_id = _emit_invoice_event(
            event_repository=self._event_repository_for_bucket(bucket_id),
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
        now = _utc_now()
        data["updated_at"] = now
        updated = BusinessOperationInvoice.model_validate(data)
        records[index] = updated
        _save(self._settings, self.source_kind, bucket_id, records)
        updated_type = _EVENT_MAP[self.source_kind.value][1]
        event_id = _emit_invoice_event(
            event_repository=self._event_repository_for_bucket(bucket_id),
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
        now = _utc_now()
        _save(self._settings, self.source_kind, bucket_id, records)
        removed_type = _EVENT_MAP[self.source_kind.value][2]
        event_id = _emit_invoice_event(
            event_repository=self._event_repository_for_bucket(bucket_id),
            record=target,
            event_type=removed_type,
            occurred_at=now,
            actor=actor,
        )
        return BusinessOperationInvoiceResult(record=target, bucket_event_ids=(event_id,))

    def _event_repository_for_bucket(self, bucket_id: str) -> BucketEventHistoryRepositoryProtocol:
        if self._event_repository is not None:
            return self._event_repository
        return BucketEventHistoryRepository(
            objects=secure_object_repository_for_bucket(bucket_id, self._settings),
        )


class PayableInvoiceService(_BusinessOperationInvoiceService):
    """CRUD service for ``payable_invoice`` records (we owe vendor)."""

    source_kind = BusinessOperationInvoiceDirection.PAYABLE_INVOICE


class CollectibleInvoiceService(_BusinessOperationInvoiceService):
    """CRUD service for ``collectible_invoice`` records (customer owes us)."""

    source_kind = BusinessOperationInvoiceDirection.COLLECTIBLE_INVOICE


__all__ = [
    "BusinessOperationInvoice",
    "BusinessOperationInvoiceDirection",
    "BusinessOperationInvoiceDocument",
    "BusinessOperationInvoiceInputError",
    "BusinessOperationInvoiceNotFoundError",
    "BusinessOperationInvoicePatch",
    "BusinessOperationInvoiceRepository",
    "BusinessOperationInvoiceResult",
    "CollectibleInvoiceService",
    "IntracomOperationType",
    "PayableInvoiceService",
    "validate_eu_iva_id",
]
