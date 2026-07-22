"""Payable and collectible invoice CRUD services.

Two noun-groups (``payable_invoice``, ``collectible_invoice``) each
expose the canonical five-verb CRUD spine
``add``/``remove``/``update``/``view``/``list``. Records are
bucket-scoped and persisted as encrypted :class:`BusinessOperationInvoiceDocument`
payloads through
:class:`~cadrumo.adapters.persistence.storage.SecureBoundRepository` per
noun-kind, under the
:data:`cadrumo.adapters.persistence.storage.LEDGER_BUSINESS_OPERATION_INVOICE_NAMESPACE`
namespace contract.

The records are intentionally slim. Business-detail enrichment (line
items, IVA breakdown, reconciliation linkages) belongs to the
:mod:`cadrumo.domain.invoices` richer ``Invoice`` aggregate consumed by
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
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import override

from pydantic import BaseModel, Field, field_serializer, field_validator

from ...adapters.outbound.fx import default_ecb_rate_provider
from ...adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ...adapters.persistence.storage import (
    LEDGER_BUSINESS_OPERATION_INVOICE_NAMESPACE,
    SecureBoundRepository,
    secure_object_repository_for_bucket,
)
from ...core import STRICT_FROZEN_CONFIG, IntracomOperationType
from ...core.config import Settings
from ...core.errors import CadrumoError
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.hashing import content_hash_hex
from ...core.identity import BucketId
from ...core.money import round_to_cents
from ...core.parsing import parse_iso8601_date
from ...core.time import now as _utc_now
from ...domain import canonical_decimal_string
from ...domain.buckets import (
    BucketEventHistoryRepositoryProtocol,
    BucketEventObjectType,
    BucketEventType,
    append_bucket_event,
)
from ...domain.currency import ExchangeRateProvider


class BusinessOperationInvoiceDirection(StrEnum):
    """The two invoice-direction variants this module covers.

    The member string values (``payable_invoice`` / ``collectible_invoice``)
    are the load-bearing internal source-kind taxonomy per
    ``aeat-spanish-stem-naming`` and are preserved; only the enum TYPE name
    is the direction axis.
    """

    PAYABLE_INVOICE = "payable_invoice"
    COLLECTIBLE_INVOICE = "collectible_invoice"


class BusinessOperationInvoiceInputError(CadrumoError):
    """Raised when a CLI-supplied input violates the typed contract."""


class BusinessOperationInvoiceNotFoundError(CadrumoError):
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
    operations that feed M349 aggregation. The current persisted shape always
    carries the three keys; domestic invoices record them explicitly as
    ``None``.
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
    # Euro-conversion stamp for a foreign-currency invoice, resolved at entry
    # from the ECB reference rate. Both are absent for a EUR invoice (already
    # euro) and for a foreign invoice whose rate could not be resolved -- which
    # is then withheld from modelo projection rather than declared at face
    # value. See `Invoice.fx_rate` for the rich-catalogue counterpart.
    fx_rate: Decimal | None = Field(default=None)
    fx_rate_date: str | None = Field(default=None, min_length=10, max_length=10)
    notes: str = Field(default="", max_length=2000)
    # Intracom EU fields — None for domestic invoices.
    country_code: str | None = Field(min_length=2, max_length=2)
    eu_iva_id: str | None = Field(max_length=20)
    operation_type: IntracomOperationType | None
    created_at: datetime
    updated_at: datetime

    @field_validator("country_code")
    @classmethod
    def _normalise_country_code(cls, v: str | None) -> str | None:
        return v.upper() if v is not None else None

    @property
    def taxable_base_eur(self) -> Decimal | None:
        """``taxable_base`` in euro, or ``None`` when unconverted."""
        return self._in_eur(self.taxable_base)

    @property
    def total_amount_eur(self) -> Decimal | None:
        """``total_amount`` in euro, or ``None`` when unconverted."""
        return self._in_eur(self.total_amount)

    def _in_eur(self, amount: Decimal) -> Decimal | None:
        """Convert *amount* to euro using the stored rate, or report it unknown."""
        if self.currency == DEFAULT_CURRENCY:
            return amount
        if self.fx_rate is None:
            return None
        return round_to_cents(amount * self.fx_rate)

    @field_serializer("taxable_base", "iva_amount", "total_amount", "iva_rate", "fx_rate", when_used="json")
    def _serialize_decimal(self, value: Decimal | None) -> str | None:
        if value is None:
            return None
        return format(value, "f")


#: Bound on the mint-time collision disambiguator. A genuine collision needs an
#: identical invoice (same fields and coarse-clock instant) already stored, so a
#: handful of attempts is the realistic ceiling; the cap exists so a derivation
#: regression that drops the disambiguator from the digest fails loudly instead of
#: spinning forever.
_ID_DISAMBIGUATION_CAP = 1024


def derive_business_operation_invoice_id(
    *,
    bucket_id: str,
    source_kind: BusinessOperationInvoiceDirection,
    counterparty_nif: str,
    counterparty_name: str,
    invoice_number: str,
    invoice_date: str,
    currency: str,
    taxable_base: Decimal,
    iva_rate: Decimal | None,
    iva_amount: Decimal,
    total_amount: Decimal,
    notes: str,
    country_code: str | None,
    eu_iva_id: str | None,
    operation_type: IntracomOperationType | None,
    created_at: datetime,
    disambiguator: int = 0,
) -> str:
    """Return the content-addressed id for a business-operation invoice record.

    Mirrors :func:`cadrumo.domain.transactions.derive_transaction_id`: a SHA-256
    digest (truncated to 16 hex chars, the prior surrogate's width) over the
    record's identifying fields, so the id is stable under a frozen-clock replay
    and directly referenceable as an ``aeat app ledger invoice`` argument,
    needing no output mask. ``created_at`` plus the ``disambiguator`` ordinal
    preserve the genuine-duplicate case: two legitimately distinct invoices must
    keep distinct ids, so the mint site increments ``disambiguator`` on the rare
    digest collision rather than colliding.
    """
    return content_hash_hex(
        {
            "bucket_id": bucket_id,
            "source_kind": source_kind.value,
            "counterparty_nif": counterparty_nif,
            "counterparty_name": counterparty_name,
            "invoice_number": invoice_number,
            "invoice_date": invoice_date,
            "currency": currency,
            "taxable_base": canonical_decimal_string(taxable_base),
            "iva_rate": canonical_decimal_string(iva_rate) if iva_rate is not None else "",
            "iva_amount": canonical_decimal_string(iva_amount),
            "total_amount": canonical_decimal_string(total_amount),
            "notes": notes,
            "country_code": country_code or "",
            "eu_iva_id": eu_iva_id or "",
            "operation_type": operation_type.value if operation_type is not None else "",
            "created_at": created_at.isoformat(),
            "disambiguator": disambiguator,
        },
    )[:16]


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
    """Encrypted store for one bucket/source-kind invoice catalogue.

    The namespace, sensitivity, schema version, and object-key contract come
    from
    :data:`cadrumo.adapters.persistence.storage.LEDGER_BUSINESS_OPERATION_INVOICE_NAMESPACE`.
    The :class:`~cadrumo.adapters.persistence.storage.SecureBoundRepository` base
    wraps each :class:`BusinessOperationInvoiceDocument` in a
    :class:`~cadrumo.adapters.persistence.storage.Envelope` before writing it.

    See Also:
        :class:`BusinessOperationInvoiceDocument`
            Bucket-local payload grouped by invoice direction.
        :class:`PayableInvoiceService`
            CRUD service for vendor invoices.
        :class:`CollectibleInvoiceService`
            CRUD service for customer invoices.
    """

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
    from ...domain.buckets import (
        BucketEvent,
        derive_bucket_event_id,
    )

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


def _resolve_fx_stamp(
    *,
    currency: str,
    invoice_date: str,
    rate_provider: ExchangeRateProvider | None,
) -> tuple[Decimal | None, str | None]:
    """Return the euro-conversion stamp for a foreign-currency invoice.

    Converts at the invoice date, the operation date Spanish law binds the
    official rate to (Ley 46/1998 art. 36), through the same shared ECB
    provider the ledger import and rich-catalogue paths use.

    A euro invoice is unstamped. A foreign invoice whose rate or date cannot be
    resolved is also left unstamped rather than defaulted: the record then
    reports no euro value and is withheld from projection, which an operator can
    correct, where a fabricated rate could not be.
    """
    if currency.strip().upper() == DEFAULT_CURRENCY:
        return (None, None)
    parsed = parse_iso8601_date(invoice_date)
    if parsed is None:
        return (None, None)
    provider = rate_provider or default_ecb_rate_provider()
    rate = provider.get_eur_rate(currency, parsed)
    if rate is None:
        return (None, None)
    return (rate, parsed.isoformat())


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
        rate_provider: ExchangeRateProvider | None = None,
    ) -> BusinessOperationInvoiceResult:
        now = _utc_now()
        fx_rate, fx_rate_date = _resolve_fx_stamp(
            currency=currency,
            invoice_date=invoice_date,
            rate_provider=rate_provider,
        )
        # Normalise country_code to the stored (upper) form so the id derives
        # from the same value the record persists (the model upper-cases it).
        normalised_country_code = country_code.upper() if country_code is not None else None
        records = _load(self._settings, self.source_kind, bucket_id)
        existing_ids = {existing.invoice_id for existing in records}
        for disambiguator in range(_ID_DISAMBIGUATION_CAP):
            invoice_id = derive_business_operation_invoice_id(
                bucket_id=bucket_id,
                source_kind=self.source_kind,
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
                country_code=normalised_country_code,
                eu_iva_id=eu_iva_id,
                operation_type=operation_type,
                created_at=now,
                disambiguator=disambiguator,
            )
            if invoice_id not in existing_ids:
                break
        else:
            # Unreachable unless the derivation stops incorporating the
            # disambiguator: then every attempt collides and the loop would spin
            # forever. Fail loudly on the bounded cap instead of hanging.
            raise RuntimeError(
                f"could not derive a unique business-operation invoice id after "
                f"{_ID_DISAMBIGUATION_CAP} attempts; the content digest is not "
                "incorporating the disambiguator (a derivation regression)",
            )
        record = BusinessOperationInvoice(
            invoice_id=invoice_id,
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
            fx_rate=fx_rate,
            fx_rate_date=fx_rate_date,
            created_at=now,
            updated_at=now,
        )
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
    "PayableInvoiceService",
    "validate_eu_iva_id",
]
