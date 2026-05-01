"""Strict raw transaction boundary models for T1 ingest."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class SourceFormat(StrEnum):
    """Supported source formats for raw-ingest provenance."""

    CSV = "csv"
    XLSX = "xlsx"
    OFX = "ofx"
    PDF = "pdf"
    MANUAL = "manual"


class RawProvenance(BaseModel):
    """Byte-level provenance pointer for a raw transaction."""

    model_config = _STRICT_FROZEN

    source_path: Path
    source_sha256: str = Field(min_length=64, max_length=64)
    source_row_index: int = Field(ge=1)
    source_format: SourceFormat
    ingested_at: datetime
    provider_name: str = Field(min_length=1)

    @field_validator("source_path")
    @classmethod
    def _resolve_source_path(cls, value: Path) -> Path:
        """Persist the absolute source path for later audit reads."""
        return value.resolve()

    @field_validator("source_sha256")
    @classmethod
    def _normalize_sha256(cls, value: str) -> str:
        """Normalize and validate the file hash."""
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(char not in "0123456789abcdef" for char in normalized):
            raise ValueError("source_sha256 must be a 64-character lowercase hex digest")
        return normalized

    @field_validator("ingested_at")
    @classmethod
    def _require_aware_timestamp(cls, value: datetime) -> datetime:
        """Reject naive datetimes in provenance records."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("ingested_at must be timezone-aware")
        return value

    @field_validator("provider_name")
    @classmethod
    def _trim_provider_name(cls, value: str) -> str:
        """Reject blank provider names."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("provider_name must not be blank")
        return trimmed


class RawTransaction(BaseModel):
    """Strict T1 ingest record emitted by every financial provider."""

    model_config = _STRICT_FROZEN

    transaction_id: str = Field(min_length=1)
    booked_date: date
    value_date: date | None = None
    amount: Decimal
    currency: str = Field(min_length=3, max_length=3)
    counterparty: str | None = None
    description: str = Field(min_length=1)
    provenance: RawProvenance
    raw_fields: Mapping[str, str]

    @field_validator("transaction_id", "description")
    @classmethod
    def _reject_blank_strings(cls, value: str) -> str:
        """Reject empty identifiers and descriptions."""
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("field must not be blank")
        return trimmed

    @field_validator("currency")
    @classmethod
    def _normalize_currency(cls, value: str) -> str:
        """Normalize currency to uppercase ISO-4217 style text."""
        normalized = value.strip().upper()
        if len(normalized) != 3 or not normalized.isalpha():
            raise ValueError("currency must be a three-letter ISO 4217 code")
        return normalized

    @field_validator("counterparty")
    @classmethod
    def _normalize_counterparty(cls, value: str | None) -> str | None:
        """Collapse blank counterparties to ``None``."""
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @field_validator("raw_fields")
    @classmethod
    def _freeze_raw_fields(cls, value: Mapping[str, str]) -> Mapping[str, str]:
        """Freeze the raw source row into an immutable string mapping."""
        return MappingProxyType({str(key): str(raw) for key, raw in value.items()})

    @field_serializer("raw_fields")
    def _serialize_raw_fields(self, value: Mapping[str, str]) -> dict[str, str]:
        """Serialize the immutable mapping back to a regular JSON object."""
        return dict(value)
