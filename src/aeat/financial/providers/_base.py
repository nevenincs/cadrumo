"""Shared provider contracts and ingest helpers."""

from __future__ import annotations

import csv
import hashlib
import unicodedata
from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict

from ...config import load_settings
from ...errors import AeatError
from ...logging import get_logger
from .._raw_transaction import RawProvenance, RawTransaction, SourceFormat

LOGGER = get_logger(__name__)
_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class FinancialProviderError(AeatError):
    """Base error raised by financial-ingest providers."""


class UnsupportedFinancialSourceError(FinancialProviderError):
    """Raised when no provider can interpret a source document."""


class InvalidFinancialSourceError(FinancialProviderError):
    """Raised when a source document is unreadable or structurally invalid."""


class ProviderValidation(BaseModel):
    """Typed validation result returned before ingest."""

    model_config = _STRICT_FROZEN

    is_valid: bool
    warnings: tuple[str, ...] = ()
    detected_encoding: str | None = None
    detected_dialect: str | None = None


class FinancialProvider(ABC):
    """Abstract base class for file-backed raw transaction providers."""

    name: ClassVar[str]
    supported_extensions: ClassVar[frozenset[str]]
    source_format: ClassVar[SourceFormat]

    def can_handle(self, path: Path) -> bool:
        """Return whether the provider is a plausible match for ``path``."""
        return path.is_file() and path.suffix.lower() in self.supported_extensions

    @abstractmethod
    def ingest(self, path: Path) -> Iterator[RawTransaction]:
        """Yield raw transactions from ``path``."""

    @abstractmethod
    def validate_source(self, path: Path) -> ProviderValidation:
        """Validate ``path`` before ingesting it."""

    def _read_source_bytes(self, path: Path) -> bytes:
        """Read the raw source bytes once for validation and provenance."""
        resolved = path.resolve()
        if not resolved.exists() or not resolved.is_file():
            raise InvalidFinancialSourceError(f"source file does not exist: {resolved}")
        return resolved.read_bytes()

    @staticmethod
    def _compute_sha256(source_bytes: bytes) -> str:
        """Return the lowercase SHA-256 digest of the source bytes."""
        return hashlib.sha256(source_bytes).hexdigest()

    def _build_provenance(
        self,
        *,
        path: Path,
        source_sha256: str,
        source_row_index: int,
    ) -> RawProvenance:
        """Create the common provenance record for one source row."""
        return RawProvenance(
            source_path=path.resolve(),
            source_sha256=source_sha256,
            source_row_index=source_row_index,
            source_format=self.source_format,
            ingested_at=datetime.now(UTC),
            provider_name=self.name,
        )


def describe_dialect(dialect: type[csv.Dialect]) -> str:
    """Return a compact human-readable dialect description."""
    return f"delimiter={dialect.delimiter!r},quotechar={dialect.quotechar!r}"


def normalize_header(value: str) -> str:
    """Normalize a column header for alias matching."""
    normalized = unicodedata.normalize("NFKD", value.replace("\ufeff", "").strip().lower())
    without_diacritics = "".join(char for char in normalized if not unicodedata.combining(char))
    return " ".join(without_diacritics.split())


def coerce_cell_text(value: object) -> str:
    """Coerce a source value to a stripped string for raw-field storage."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def parse_date_value(value: object, *, day_first: bool = True) -> date:
    """Parse a bank-statement date or date-time into a ``date``."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = coerce_cell_text(value)
    if not raw:
        raise ValueError("missing date value")
    raw = raw.replace(".", "/")
    if raw.isdigit() and len(raw) >= 8:
        return datetime.strptime(raw[:8], "%Y%m%d").date()
    formats: Sequence[str]
    if day_first:
        formats = (
            "%d/%m/%Y",
            "%d/%m/%y",
            "%d-%m-%Y",
            "%d-%m-%y",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%y %H:%M:%S",
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
        )
    else:
        formats = (
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%m/%d/%Y",
            "%m/%d/%Y %H:%M:%S",
            "%d/%m/%Y",
            "%d/%m/%Y %H:%M:%S",
        )
    for candidate in formats:
        try:
            return datetime.strptime(raw, candidate).date()
        except ValueError:
            continue
    raise ValueError(f"unsupported date format: {raw!r}")


def parse_amount_value(
    value: object,
    *,
    decimal_separator: Literal[",", "."] | None = None,
) -> Decimal:
    """Parse bank-export numeric text into ``Decimal`` without float coercion."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    raw = coerce_cell_text(value)
    if not raw:
        raise ValueError("missing amount value")
    sanitized = raw.replace(" ", "").replace("\u202f", "")
    negative = (
        sanitized.startswith("-") or sanitized.endswith("-") or (sanitized.startswith("(") and sanitized.endswith(")"))
    )
    sanitized = sanitized.strip("()-+")
    sanitized = "".join(char for char in sanitized if char.isdigit() or char in ",.")
    if not sanitized:
        raise ValueError(f"unsupported amount value: {raw!r}")
    if decimal_separator is not None and decimal_separator not in {",", "."}:
        raise ValueError(f"unsupported decimal separator: {decimal_separator!r}")
    if decimal_separator is not None:
        decimal_sep = decimal_separator
    elif "," in sanitized and "." in sanitized:
        decimal_sep = "," if sanitized.rfind(",") > sanitized.rfind(".") else "."
    elif "," in sanitized:
        decimal_sep = ","
    else:
        decimal_sep = "."
    thousands_sep = "." if decimal_sep == "," else ","
    normalized = sanitized.replace(thousands_sep, "")
    if decimal_sep != ".":
        normalized = normalized.replace(decimal_sep, ".")
    try:
        amount = Decimal(normalized)
    except InvalidOperation as exc:
        raise ValueError(f"unsupported amount value: {raw!r}") from exc
    return -amount if negative else amount


def synthesize_transaction_id(
    *,
    provider_name: str,
    source_sha256: str,
    source_row_index: int,
) -> str:
    """Build a deterministic synthetic transaction identifier."""
    prefix = provider_name.lower().replace(" ", "-")
    return f"{prefix}-{source_sha256[:12]}-{source_row_index}"


def build_raw_transaction(
    *,
    provider: FinancialProvider,
    path: Path,
    source_sha256: str,
    source_row_index: int,
    transaction_id: str,
    booked_date: date,
    value_date: date | None,
    amount: Decimal,
    currency: str,
    counterparty: str | None,
    description: str,
    raw_fields: Mapping[str, str],
) -> RawTransaction:
    """Create one strict raw transaction with shared provenance semantics."""
    return RawTransaction(
        transaction_id=transaction_id,
        booked_date=booked_date,
        value_date=value_date,
        amount=amount,
        currency=currency,
        counterparty=counterparty,
        description=description,
        provenance=provider._build_provenance(
            path=path,
            source_sha256=source_sha256,
            source_row_index=source_row_index,
        ),
        raw_fields=raw_fields,
    )


def default_currency() -> str:
    """Return the configured project-default financial currency."""
    return load_settings().financial_base_currency.strip().upper()
