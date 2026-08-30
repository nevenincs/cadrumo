"""Strict raw transaction boundary models for ingest.

Defines the upstream-immutable records every transaction parser must
emit, before they are wrapped in
:class:`domain.transactions.Transaction`:

- :class:`RawTransaction` -- the verbatim per-row record.
- :class:`RawProvenance` -- the source-file metadata pinned to each row.
- :class:`SourceFormat` -- closed taxonomy of supported input formats.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType

from pydantic import BaseModel, Field, field_serializer, field_validator

from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.errors.hierarchy import CoreValidationError
from ...core.identity import ContentDigest
from ...core.parsing import normalise_iso_4217_currency
from ...core.time import UtcInstant, validate_utc_aware
from .errors import TransactionValidationError


class SourceFormat(StrEnum):
    """Closed taxonomy of supported raw-transaction input formats.

    Attributes:
        CSV: Bank statement CSV export.
        XLSX: Bank statement Excel workbook.
        OFX: Open Financial Exchange feed.
        PDF: PDF statement (parsed text layer).
        MANUAL: Hand-entered transaction.
    """

    CSV = "csv"
    XLSX = "xlsx"
    OFX = "ofx"
    PDF = "pdf"
    MANUAL = "manual"


class RawProvenance(BaseModel):
    """Per-row provenance pinned to one :class:`RawTransaction`.

    Attributes:
        source_path: Basename of the source file (the filename only, never a
            resolved absolute path). The file's content identity is carried by
            ``source_sha256``; storing only the basename keeps provenance
            human-readable without baking a host-specific absolute path into the
            persisted and exported record (which would leak the operator's
            directory layout and mutate across operating systems on rehydration).
        source_sha256: 64-character lowercase hex SHA-256 digest of the
            source file.
        source_row_index: One-based row index within the source file.
        source_format: Closed :class:`SourceFormat` discriminator.
        ingested_at: Timezone-aware UTC timestamp of the ingest run.
        provider_name: Non-blank logical name of the upstream
            financial provider.
    """

    model_config = _STRICT_FROZEN

    source_path: Path
    source_sha256: ContentDigest
    source_row_index: int = Field(ge=1)
    source_format: SourceFormat
    ingested_at: UtcInstant
    provider_name: str = Field(min_length=1)

    @field_validator("source_path")
    @classmethod
    def _basename_source_path(cls, value: Path) -> Path:
        """Reduce ``source_path`` to its basename.

        The persisted/exported record must not carry a resolved absolute path:
        it would leak the operator's directory layout and, because the prior
        ``.resolve()`` re-ran on rehydration, mutate a POSIX-authored path into
        a malformed Windows path (and vice versa), breaking strict cross-OS
        roundtrip equality. The basename is OS-neutral and idempotent: extracting
        it at ingest runs on the authoring host where the separator matches, and
        re-validating a stored bare filename is a no-op on every platform.
        """
        name = value.name
        # A path with no filename component (e.g. a bare directory) keeps its
        # string form rather than collapsing to an empty name.
        return Path(name) if name else value

    @field_validator("source_sha256", mode="before")
    @classmethod
    def _normalize_sha256(cls, value: object) -> object:
        """Fold an uppercase digest to the canonical form BEFORE the shape check.

        This is normalisation only; the shape is enforced by
        :data:`~core.identity.ContentDigest`, which the field is typed as, and
        restating it here would be a second register of one contract.

        The ordering is the whole point. ``ContentDigest`` requires lowercase,
        so an uppercase digest that this boundary has always accepted would be
        refused by the annotation if the fold ran after it — an input contract
        narrowed silently by a retype that was meant to widen enforcement, not
        change what the boundary admits.
        """
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("ingested_at")
    @classmethod
    def _require_aware_timestamp(cls, value: datetime) -> datetime:
        """Reject naive timestamps; ingest must record UTC offsets."""
        try:
            return validate_utc_aware(value)
        except CoreValidationError as exc:
            raise TransactionValidationError(str(exc)) from exc

    @field_validator("provider_name")
    @classmethod
    def _trim_provider_name(cls, value: str) -> str:
        """Trim ``provider_name``; reject the empty string."""
        trimmed = value.strip()
        if not trimmed:
            raise TransactionValidationError("provider_name must not be blank")
        return trimmed


class RawTransaction(BaseModel):
    """Verbatim per-row transaction record emitted by an ingest parser.

    Attributes:
        provider_transaction_id: Provider-assigned native identifier; never
            normalised beyond a strip + non-blank check. This is the bank/feed's
            own id for the row, distinct from the content-addressed
            :attr:`domain.transactions.Transaction.transaction_id` hash the
            domain derives from it.
        booked_date: Date the transaction posted to the account.
        value_date: Optional value date; falls back to ``booked_date``
            when ``None``.
        amount: Non-negative magnitude :class:`decimal.Decimal` in
            :attr:`currency`. Flow direction is carried solely by
            :attr:`domain.transactions.Transaction.direction`; the
            sign is never stored on the amount.
        currency: Three-letter ISO 4217 currency code, uppercase. Trimmed and
            uppercased before validation, so a padded source cell is accepted.
        counterparty: Optional counterparty descriptor; trimmed and
            collapsed to ``None`` when blank.
        description: Non-blank narrative.
        provenance: Per-row :class:`RawProvenance` metadata.
        raw_fields: Frozen mapping of original source columns to
            stringified values, preserved verbatim for audit.
    """

    model_config = _STRICT_FROZEN

    provider_transaction_id: str = Field(min_length=1)
    booked_date: date
    value_date: date | None = None
    amount: Decimal
    currency: str = Field(min_length=3, max_length=3)
    counterparty: str | None = None
    description: str = Field(min_length=1)
    provenance: RawProvenance
    raw_fields: Mapping[str, str]

    @field_validator("provider_transaction_id", "description")
    @classmethod
    def _reject_blank_strings(cls, value: str) -> str:
        """Trim and reject blank strings on identifier / narrative fields."""
        trimmed = value.strip()
        if not trimmed:
            raise TransactionValidationError("field must not be blank")
        return trimmed

    @field_validator("amount")
    @classmethod
    def _reject_negative_amount(cls, value: Decimal) -> Decimal:
        """Reject a negative ``amount``; the stored magnitude is non-negative.

        Flow direction is carried solely by
        :attr:`domain.transactions.Transaction.direction`; the sign is
        never stored on the amount. This gate fires on both the import and the
        manual construction paths because every transaction wraps one
        :class:`RawTransaction`.
        """
        if value < Decimal("0"):
            raise TransactionValidationError(
                "amount must be a non-negative magnitude; flow is carried by direction, not by sign",
            )
        return value

    @field_validator("currency", mode="before")
    @classmethod
    def _normalize_currency(cls, value: object) -> str:
        """Trim, uppercase, and assert ``currency`` is a three-letter ISO 4217 code.

        Runs in ``mode="before"`` so normalisation precedes the
        ``min_length`` / ``max_length`` field constraint: a padded source cell
        (``" usd "``) normalises to ``"USD"`` here rather than being refused
        for its padding, which is what the CSV and OFX ingest boundaries have
        always done. Delegates the shape policy to
        :func:`~core.parsing.normalise_iso_4217_currency` so every inbound
        surface and this persisted record share one definition.
        """
        try:
            return normalise_iso_4217_currency(value)
        except CoreValidationError as exc:
            raise TransactionValidationError(str(exc)) from exc

    @field_validator("counterparty")
    @classmethod
    def _normalize_counterparty(cls, value: str | None) -> str | None:
        """Trim ``counterparty`` and collapse blank strings to ``None``."""
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @field_validator("raw_fields")
    @classmethod
    def _freeze_raw_fields(cls, value: Mapping[str, str]) -> Mapping[str, str]:
        """Freeze ``raw_fields`` into an immutable mapping with stringified entries."""
        return MappingProxyType({str(key): str(raw) for key, raw in value.items()})

    @field_serializer("raw_fields")
    def _serialize_raw_fields(self, value: Mapping[str, str]) -> dict[str, str]:
        """Serialise the immutable mapping back to a JSON-friendly dict."""
        return dict(value)

    @property
    def display_counterparty(self) -> str:
        """Return :attr:`counterparty` coerced to an empty string when absent.

        CSV importers may produce :class:`RawTransaction` rows whose
        counterparty column is blank; :func:`_normalize_counterparty`
        collapses those to ``None`` so the domain model carries the
        true absent signal. The CLI ledger surface (list / view / payable
        / collectible) renders the field through a typed payload that
        expects ``str`` rather than ``str | None`` so the display layer
        can keep its column contract uniform. Routing the coercion
        through this property removes three identical
        ``raw.counterparty or ""`` call-site repeats and centralises the
        decision so future display tweaks (placeholder strings, ellipses)
        land in one place.
        """
        return self.counterparty or ""
