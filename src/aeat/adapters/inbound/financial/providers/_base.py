"""Shared provider contracts and ingest helpers.

Defines the :class:`FinancialProvider` ABC together with the validation
record :class:`ProviderValidation`, the provider error hierarchy
(:class:`FinancialProviderError`, :class:`InvalidFinancialSourceError`,
:class:`UnsupportedFinancialSourceError`, :class:`BankStatementParseError`),
and the parsing / provenance helpers concrete providers reuse to emit
:class:`aeat.domain.transactions.RawTransaction`
records with consistent provenance.

Provider corpus discipline
--------------------------
Every concrete :class:`FinancialProvider` subclass must declare two
class-level corpus attributes:

``verification_source``
    A string literal describing how the corpus fixtures were obtained:

    - ``"real_bank_corpus_pdf"`` — sanitised PDFs from real bank
      statements held by the operator.
    - ``"synthetic_from_bank_published_text"`` — PDFs generated from
      sanitised text dumps published in third-party open-source corpora
      (e.g., portfolio-performance); structure matches real layouts but
      origin is reconstructed.
    - ``"no_corpus"`` — no corpus is currently held.  The provider
      **must** also set ``provisional_pending_specimen = True``.

``provisional_pending_specimen``
    ``True`` when no real-corpus PDF has been parsed to confirm the
    provider produces correct output.  Providers with ``no_corpus`` must
    set this ``True``; providers with a confirmed corpus round-trip set
    it ``False``.

The test suite in ``test_pdf_n26.py`` and the detection-invariant test
enforce these attributes at collection time so a newly enrolled provider
cannot silently ship without the declaration.
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
from .....core.decimal import coerce_decimal
from .....core.errors import AeatError
from .....core.logging import get_logger
from .....domain.transactions import RawProvenance, RawTransaction, SourceFormat

LOGGER = get_logger(__name__)
_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")

# Defensive ceiling on financial-source ingest size. Real bank statements
# (PDF, XLSX, CSV) for a full fiscal year are well under 10 MiB; this 64 MiB
# cap rejects oversized inputs (including XLSX zip-bomb payloads) before
# they reach openpyxl / pdfplumber / the csv reader.
_MAX_SOURCE_BYTES = 64 * 1024 * 1024

#: Allowed values for :attr:`FinancialProvider.verification_source`.
CorpusVerificationSource = Literal[
    "real_bank_corpus_pdf",
    "synthetic_from_bank_published_text",
    "no_corpus",
]


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


class BankStatementParseError(FinancialProviderError):
    """Raised when a bank statement PDF cannot be fully parsed.

    Carries structured attributes that allow callers to assert on the
    failure kind without parsing the message string — the same pattern
    as :class:`aeat.adapters.inbound.declaracion._errors.DeclaracionParseError`
    and :class:`aeat.domain.justificante._errors.JustificanteParseError`.

    This error is appropriate for PDF-specific parse failures where the
    document was accepted by format detection but extraction produced
    incomplete or malformed results.  Low-level structural failures
    (file unreadable, wrong bank marker) continue to raise
    :class:`InvalidFinancialSourceError`.

    Attributes:
        missing: Tuple of field or row identifiers that produced no
            match in the PDF text (e.g. a required header field absent).
        malformed: Tuple of field identifiers whose captured value could
            not be coerced to the target type (date, amount, currency).
        ambiguous: Tuple of field identifiers that matched more than one
            region in the PDF.
        coverage: Fraction of expected transaction rows successfully
            extracted (``Decimal``).  ``None`` when the error is not a
            coverage failure.
    """

    def __init__(
        self,
        message: str | None = None,
        *,
        missing: tuple[str, ...] = (),
        malformed: tuple[str, ...] = (),
        ambiguous: tuple[str, ...] = (),
        coverage: Decimal | None = None,
    ) -> None:
        super().__init__(message)
        self.missing: tuple[str, ...] = missing
        self.malformed: tuple[str, ...] = malformed
        self.ambiguous: tuple[str, ...] = ambiguous
        self.coverage: Decimal | None = coverage


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
    :attr:`supported_extensions`, :attr:`source_format`,
    :attr:`verification_source`, and :attr:`provisional_pending_specimen`
    and implement :meth:`ingest` plus :meth:`validate_source`. The shared
    :meth:`_build_provenance` helper centralises
    :class:`aeat.domain.transactions.RawProvenance`
    construction so every emitted
    :class:`aeat.domain.transactions.RawTransaction`
    carries consistent provenance metadata.

    See the module docstring for the corpus discipline contract that
    :attr:`verification_source` and :attr:`provisional_pending_specimen`
    jointly enforce.

    Attributes:
        name: Stable provider identifier embedded in synthetic
            transaction ids and provenance records.
        supported_extensions: Lowercase file extensions
            (including the leading dot) the provider accepts.
        source_format: Source-format enum used for provenance.
        verification_source: Corpus provenance declaration; one of
            ``"real_bank_corpus_pdf"``,
            ``"synthetic_from_bank_published_text"``, or
            ``"no_corpus"``.
        provisional_pending_specimen: ``True`` when no confirmed corpus
            round-trip has been performed for this provider.  Providers
            with ``verification_source = "no_corpus"`` must set this
            ``True``.
    """

    name: ClassVar[str]
    supported_extensions: ClassVar[frozenset[str]]
    source_format: ClassVar[SourceFormat]
    verification_source: ClassVar[CorpusVerificationSource]
    provisional_pending_specimen: ClassVar[bool]

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Enforce corpus-discipline declarations at subclass definition time.

        ``verification_source`` and ``provisional_pending_specimen`` are
        declared as :class:`ClassVar` annotations on the ABC but Python does
        not enforce unset ``ClassVar`` attributes.  ``__init_subclass__`` runs
        once per concrete subclass at class-creation time (i.e. at import),
        giving the same guarantee as ``@abstractmethod`` without changing the
        class-variable declaration syntax that every concrete provider already
        uses.

        Raises:
            TypeError: When a concrete (non-abstract) subclass does not declare
                       ``verification_source`` or ``provisional_pending_specimen``,
                       or when ``verification_source`` carries an unknown literal.
        """
        super().__init_subclass__(**kwargs)
        # Skip enforcement for abstract subclasses (those that still have
        # abstract methods remaining — they are intermediary ABCs, not leaf
        # providers).
        if getattr(cls, "__abstractmethods__", None):
            return
        _VALID_SOURCES: frozenset[str] = frozenset(
            {"real_bank_corpus_pdf", "synthetic_from_bank_published_text", "no_corpus"}
        )
        if not hasattr(cls, "verification_source"):
            raise TypeError(
                f"{cls.__qualname__} must declare a 'verification_source' class variable"
            )
        vs = cls.verification_source  # type: ignore[attr-defined]
        if vs not in _VALID_SOURCES:
            raise TypeError(
                f"{cls.__qualname__}.verification_source={vs!r} is not one of "
                f"{sorted(_VALID_SOURCES)}"
            )
        if not hasattr(cls, "provisional_pending_specimen"):
            raise TypeError(
                f"{cls.__qualname__} must declare a 'provisional_pending_specimen' class variable"
            )
        pps = cls.provisional_pending_specimen  # type: ignore[attr-defined]
        if not isinstance(pps, bool):
            raise TypeError(
                f"{cls.__qualname__}.provisional_pending_specimen must be bool, got {type(pps)}"
            )
        if vs == "no_corpus" and pps is not True:
            raise TypeError(
                f"{cls.__qualname__}: verification_source='no_corpus' requires "
                "provisional_pending_specimen=True"
            )

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
        if path.is_symlink():
            raise InvalidFinancialSourceError(
                translated_message="errors.financial.source_file_is_symlink",
                context={"path": str(path)},
            )
        resolved = path.resolve()
        if not resolved.exists() or not resolved.is_file():
            raise InvalidFinancialSourceError(
                translated_message="errors.financial.source_file_not_found",
                context={"path": str(resolved)},
            )
        size = resolved.stat().st_size
        if size > _MAX_SOURCE_BYTES:
            raise InvalidFinancialSourceError(
                translated_message="errors.financial.source_file_too_large",
                context={
                    "path": str(resolved),
                    "size_bytes": size,
                    "max_bytes": _MAX_SOURCE_BYTES,
                },
            )
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
        coerced = coerce_decimal(value)
        if coerced is None:
            raise FinancialValidationError(f"unsupported float value: {value!r}")
        return coerced
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
    if not amount.is_finite():
        # Defence-in-depth: _sanitise_amount_text already strips letters,
        # so NaN / Infinity literals cannot reach Decimal() through normal
        # flow. This guard catches any future sanitiser regression that
        # would otherwise admit non-finite values into the ledger.
        raise FinancialValidationError(f"non-finite amount value: {raw!r}")
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
