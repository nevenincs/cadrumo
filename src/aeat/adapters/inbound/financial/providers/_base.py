"""Shared provider contracts and ingest helpers.

Defines the :class:`FinancialProvider` ABC together with the validation
record :class:`ProviderValidation`, the provider error hierarchy
(:class:`FinancialProviderError`, :class:`InvalidFinancialSourceError`,
:class:`UnsupportedFinancialSourceError`), and the parsing /
provenance helpers concrete providers reuse to emit
:class:`aeat.domain.transactions.RawTransaction`
records with consistent provenance.
"""

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

from .....core.config import load_settings
from .....core.errors import AeatError
from .....core.logging import get_logger
from .....domain.transactions import RawProvenance, RawTransaction, SourceFormat

LOGGER = get_logger(__name__)
_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class FinancialProviderError(AeatError):
    """Base error raised by financial-ingest providers.

    Subclasses :class:`aeat.core.errors.AeatError` so the application
    layer can catch every provider failure with one ``except`` clause.
    """


class UnsupportedFinancialSourceError(FinancialProviderError):
    """Raised when no provider can interpret a source document."""


class InvalidFinancialSourceError(FinancialProviderError):
    """Raised when a source document is unreadable or structurally invalid."""


class FinancialValidationError(FinancialProviderError, ValueError):
    """Raised when a specific field (date, amount) fails domain validation.

    This error inherits from both :class:`FinancialProviderError` and
    :class:`ValueError` for compatibility with Pydantic and consistent
    adapter-layer error handling.
    """

    pass


class ProviderValidation(BaseModel):
    """Typed validation result returned before ingest.

    Attributes:
        is_valid: Whether the source document can be ingested.
        warnings: Human-readable warning strings; non-empty even when
            ``is_valid`` is True (e.g., a missing currency column).
        detected_encoding: Provider-specific encoding marker, when
            applicable (CSV byte decoding, OFX parser tag, etc.).
        detected_dialect: Compact provider-specific dialect / layout
            description used in operator diagnostics.
    """

    model_config = _STRICT_FROZEN

    is_valid: bool
    warnings: tuple[str, ...] = ()
    detected_encoding: str | None = None
    detected_dialect: str | None = None


class FinancialProvider(ABC):
    """Abstract base class for file-backed raw transaction providers.

    Concrete subclasses must declare :attr:`name`,
    :attr:`supported_extensions`, and :attr:`source_format` and
    implement :meth:`ingest` plus :meth:`validate_source`. The shared
    :meth:`_build_provenance` helper centralises
    :class:`aeat.domain.transactions.RawProvenance`
    construction so every emitted
    :class:`aeat.domain.transactions.RawTransaction`
    carries consistent provenance metadata.

    Attributes:
        name: Stable provider identifier embedded in synthetic
            transaction ids and provenance records.
        supported_extensions: Lowercase file extensions
            (including the leading dot) the provider accepts.
        source_format: Source-format enum used for provenance.
    """

    name: ClassVar[str]
    supported_extensions: ClassVar[frozenset[str]]
    source_format: ClassVar[SourceFormat]

    def can_handle(self, path: Path) -> bool:
        """Return whether the provider is a plausible match for ``path``.

        Args:
            path: Candidate source document.

        Returns:
            True if ``path`` exists and its extension is in
            :attr:`supported_extensions`. Content sniffing is left to
            :meth:`validate_source` and :func:`detect_provider`.
        """
        return path.is_file() and path.suffix.lower() in self.supported_extensions

    @abstractmethod
    def ingest(self, path: Path) -> Iterator[RawTransaction]:
        """Yield raw transactions from ``path``.

        Implementations must produce one
        :class:`aeat.domain.transactions.RawTransaction`
        per source row, with provenance built via
        :meth:`_build_provenance`.

        Args:
            path: Source document to ingest.

        Yields:
            One raw transaction per source row.

        Raises:
            :exc:`InvalidFinancialSourceError`: When the document
                cannot be parsed or a row is malformed.
        """

    @abstractmethod
    def validate_source(self, path: Path) -> ProviderValidation:
        """Validate ``path`` before ingesting it.

        Args:
            path: Candidate source document.

        Returns:
            A :class:`ProviderValidation` describing whether the
            document is ingestable and surfacing any warnings.
        """

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
        """Create the common provenance record for one source row.

        Args:
            path: Source document path; resolved to its absolute form
                before storage.
            source_sha256: Lowercase SHA-256 of the source bytes.
            source_row_index: 1-based row index within the source.

        Returns:
            A :class:`RawProvenance` record stamped with the current
            UTC ingestion timestamp and the provider's
            :attr:`name` / :attr:`source_format`.
        """
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
        raise FinancialValidationError("missing date value")
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
        except ValueError as fmt_exc:
            LOGGER.debug(
                "financial provider: date format %r did not match %r (%s); trying next",
                candidate,
                raw,
                fmt_exc,
            )
            continue
    raise FinancialValidationError(f"unsupported date format: {raw!r}")


def parse_amount_value(
    value: object,
    *,
    decimal_separator: Literal[",", "."] | None = None,
) -> Decimal:
    """Parse bank-export numeric text into ``Decimal`` without float coercion.

    Float coercion is forbidden because bank exports carry exact
    cents; intermediate floats would silently round (e.g.,
    ``1234.56`` → ``1234.5599999...``). The parser preserves the
    sign convention of the source — bracketed ``(123.45)`` and
    trailing-minus ``123.45-`` both decode to a negative
    :class:`decimal.Decimal`.

    Args:
        value: Raw cell value; accepted as :class:`Decimal`,
            :class:`int`, :class:`float` (re-parsed via :func:`str`),
            or text.
        decimal_separator: Optional explicit decimal separator. When
            omitted, the parser infers it from the rightmost
            occurrence of ``,`` or ``.`` in the text.

    Returns:
        A :class:`Decimal` preserving the printed precision and sign.

    Raises:
        ValueError: When the value is empty or cannot be parsed.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        return Decimal(str(value))
    raw = coerce_cell_text(value)
    if not raw:
        raise FinancialValidationError("missing amount value")
    sanitized, negative = _sanitise_amount_text(raw)
    if not sanitized:
        raise FinancialValidationError(f"unsupported amount value: {raw!r}")
    decimal_sep = _resolve_decimal_separator(sanitized, override=decimal_separator)
    normalized = _normalise_amount_digits(sanitized, decimal_sep=decimal_sep)
    try:
        amount = Decimal(normalized)
    except InvalidOperation as exc:
        raise FinancialValidationError(f"unsupported amount value: {raw!r}") from exc
    return -amount if negative else amount


def _sanitise_amount_text(raw: str) -> tuple[str, bool]:
    """Strip whitespace and sign markers from ``raw``; return ``(digits-and-separators, negative_flag)``.

    Three negativity conventions are recognised: leading minus
    (``-123.45``), trailing minus (``123.45-``), and accounting
    parentheses (``(123.45)``). After the sign markers are
    removed, only digits and ``,`` / ``.`` survive \u2014 anything else
    (currency symbols, stray operators) is dropped before
    separator inference.
    """
    sanitized = raw.replace(" ", "").replace("\u202f", "")
    negative = (
        sanitized.startswith("-") or sanitized.endswith("-") or (sanitized.startswith("(") and sanitized.endswith(")"))
    )
    sanitized = sanitized.strip("()-+")
    sanitized = "".join(char for char in sanitized if char.isdigit() or char in ",.")
    return sanitized, negative


def _resolve_decimal_separator(
    sanitized: str,
    *,
    override: Literal[",", "."] | None,
) -> str:
    """Resolve the decimal separator: explicit override, then inference from the sanitised text.

    Inference uses the rightmost separator when both ``,`` and ``.``
    appear (e.g. ``1.234,56`` -> comma is decimal); falls back to
    whichever single separator is present, or ``.`` when neither is
    present (a bare integer literal).
    """
    if override is not None:
        if override not in {",", "."}:
            raise FinancialValidationError(f"unsupported decimal separator: {override!r}")
        return override
    if "," in sanitized and "." in sanitized:
        return "," if sanitized.rfind(",") > sanitized.rfind(".") else "."
    if "," in sanitized:
        return ","
    return "."


def _normalise_amount_digits(sanitized: str, *, decimal_sep: str) -> str:
    """Drop the thousands separator and rewrite the decimal separator as ``.``."""
    thousands_sep = "." if decimal_sep == "," else ","
    normalized = sanitized.replace(thousands_sep, "")
    if decimal_sep != ".":
        normalized = normalized.replace(decimal_sep, ".")
    return normalized


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
