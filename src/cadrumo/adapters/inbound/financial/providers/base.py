"""Shared provider contracts and ingest helpers.

Defines the :class:`FinancialProvider` ABC together with the validation
record :class:`ProviderValidation`, the provider error hierarchy
(:class:`FinancialProviderError`, :class:`InvalidFinancialSourceError`,
:class:`UnsupportedFinancialSourceError`, :class:`BankStatementParseError`),
and the parsing / provenance helpers concrete providers reuse to emit
:class:`~domain.transactions.RawTransaction` records with consistent
:class:`~domain.transactions.RawProvenance`.

Providers emit :class:`ParsedLedgerRow` objects: the source sign is consumed at
the adapter boundary into a :class:`~domain.transactions.TransactionDirection`,
while the stored raw amount is an absolute magnitude.

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
import re
from abc import ABC, abstractmethod
from collections.abc import Iterator, Mapping, Sequence
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import ClassVar, Final, Literal

from pydantic import BaseModel

from .....core.config import load_settings
from .....core.decimal.coercion import coerce_decimal
from .....core.errors.hierarchy import CadrumoError, CoreValidationError
from .....core.hashing import sha256_hex as _sha256_hex
from .....core.logging import get_logger
from .....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.parsing import normalise_iso_4217_currency
from .....core.tabular import coerce_cell_text
from .....core.text_fold import fold_diacritics
from .....core.time.clock import now
from .....domain.transactions.enums import TransactionDirection
from .....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat

LOGGER = get_logger(__name__)

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


class FinancialProviderError(CadrumoError):
    """Base error raised by financial-ingest providers.

    Subclasses :class:`core.errors.CadrumoError` so the application
    layer can catch every provider failure with one ``except`` clause.
    """


class FinancialProviderConfigError(FinancialProviderError):
    """Raised when a :class:`FinancialProvider` subclass declaration is invalid.

    Fired by ``__init_subclass__`` when the concrete provider class is
    missing or carries an invalid ``verification_source`` or
    ``provisional_pending_specimen`` class variable.
    """


class UnsupportedFinancialSourceError(FinancialProviderError):
    """Raised when no provider can interpret a source document."""


class InvalidFinancialSourceError(FinancialProviderError):
    """Raised when a source document is unreadable or structurally invalid."""


class FinancialValidationError(FinancialProviderError):
    """Raised when a specific field (date, amount) fails domain validation."""


class BankStatementParseError(FinancialProviderError):
    """Raised when a bank statement PDF cannot be fully parsed.

    Carries structured attributes that allow callers to assert on the
    failure kind without parsing the message string — the same pattern
    as :class:`~adapters.inbound.declaracion.DeclaracionParseError`
    and :class:`~domain.justificante.JustificanteParseError`.

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
        """Initialise with an optional human-readable message and structured coverage fields.

        Args:
            message: Optional human-readable description of the failure.
            missing: Field or row identifiers that produced no match.
            malformed: Field identifiers whose captured value could not be coerced.
            ambiguous: Field identifiers that matched more than one region.
            coverage: Fraction of expected transaction rows successfully extracted.
        """
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
        unavailable_optional_extra: Machine identity of the optional extra whose
            absence made this provider unusable, carried as the canonical
            ``extra`` / ``import_name`` / ``importable`` fact triple rather than
            an installation instruction. Present only when a provider declined
            because its extra is not installed; the operator-facing recovery is
            resolved downstream from these facts, never rendered here.
    """

    model_config = _STRICT_FROZEN

    is_valid: bool
    warnings: tuple[str, ...] = ()
    detected_encoding: str | None = None
    detected_dialect: str | None = None
    unavailable_optional_extra: Mapping[str, str | bool] | None = None


class FinancialProvider(ABC):
    """Abstract base class for file-backed raw transaction providers.

    Concrete subclasses must declare :attr:`name`,
    :attr:`supported_extensions`, :attr:`source_format`,
    :attr:`verification_source`, and :attr:`provisional_pending_specimen`
    and implement :meth:`ingest` plus :meth:`validate_source`. The shared
    :meth:`build_provenance` helper centralises
    :class:`~domain.transactions.RawProvenance` construction so every
    emitted :class:`~domain.transactions.RawTransaction` carries
    consistent provenance metadata.

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

        Args:
            **kwargs: Forwarded to ``super().__init_subclass__``.

        Raises:
            FinancialProviderConfigError: When a concrete (non-abstract) subclass does not
                declare ``verification_source`` or ``provisional_pending_specimen``,
                or when ``verification_source`` carries an unknown literal.
        """
        super().__init_subclass__(**kwargs)
        # Skip enforcement for abstract subclasses (those that still have
        # abstract methods remaining — they are intermediary ABCs, not leaf
        # providers).
        if getattr(cls, "__abstractmethods__", None):
            return
        _VALID_SOURCES: frozenset[str] = frozenset(
            {"real_bank_corpus_pdf", "synthetic_from_bank_published_text", "no_corpus"},
        )
        if not hasattr(cls, "verification_source"):
            raise FinancialProviderConfigError(
                f"{cls.__qualname__} must declare a 'verification_source' class variable",
            )
        # Provider subclasses declare ``verification_source`` as a ClassVar;
        # the base reads it dynamically during registration.
        vs = cls.verification_source
        if vs not in _VALID_SOURCES:
            raise FinancialProviderConfigError(
                f"{cls.__qualname__}.verification_source={vs!r} is not one of {sorted(_VALID_SOURCES)}",
            )
        if not hasattr(cls, "provisional_pending_specimen"):
            raise FinancialProviderConfigError(
                f"{cls.__qualname__} must declare a 'provisional_pending_specimen' class variable",
            )
        # Same dynamic ClassVar probe as ``verification_source`` above.
        pps = cls.provisional_pending_specimen
        if not isinstance(pps, bool):
            raise FinancialProviderConfigError(
                f"{cls.__qualname__}.provisional_pending_specimen must be bool, got {type(pps)}",
            )
        if vs == "no_corpus" and pps is not True:
            raise FinancialProviderConfigError(
                f"{cls.__qualname__}: verification_source='no_corpus' requires provisional_pending_specimen=True",
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
    def ingest(self, path: Path) -> Iterator[ParsedLedgerRow]:
        """Yield parsed ledger rows from ``path``.

        Implementations must produce one :class:`ParsedLedgerRow` per source
        row (via :func:`build_raw_transaction`), each carrying a magnitude
        :class:`domain.transactions.RawTransaction` plus the
        :class:`domain.transactions.TransactionDirection` derived from the
        source sign at the parse boundary, with provenance built via
        :meth:`build_provenance`.

        Args:
            path: Source document to ingest.

        Returns:
            An iterator that yields one parsed ledger row per source row.

        Raises:
            InvalidFinancialSourceError: When the document cannot be parsed or a row is malformed.
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
        """Read raw source bytes after enforcing adapter input safety guards.

        The shared guard refuses symlinks, missing files, non-files, and sources
        over the configured size ceiling before format-specific parsers receive
        bytes. Concrete providers reuse the same bytes for validation,
        extraction, and SHA-256 provenance.
        """
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
        return _sha256_hex(source_bytes)

    def build_provenance(
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
            ingested_at=now(),
            provider_name=self.name,
        )


def describe_dialect(dialect: type[csv.Dialect]) -> str:
    """Return a compact human-readable dialect description."""
    return f"delimiter={dialect.delimiter!r},quotechar={dialect.quotechar!r}"


def normalize_header(value: str) -> str:
    """Normalize a column header for alias matching."""
    without_diacritics = fold_diacritics(value.replace("\ufeff", "").strip().casefold())
    return " ".join(without_diacritics.split())


def archive_cell_text(value: object) -> str:
    """Coerce a source value to a stripped string for raw-field storage.

    Binds the raw-field archive's rendering policy — a booking stamp is
    stored ISO-8601 rather than however ``str()`` happens to print it — onto
    the shared cell coercer, so the twelve call sites in this package state
    the policy once instead of each carrying the keyword.
    """
    return coerce_cell_text(value, temporal_as_iso=True)


def _expected_date_format_hint(*, day_first: bool) -> str:
    if day_first:
        return "DD/MM/YYYY, DD-MM-YYYY, or YYYY-MM-DD"
    return "YYYY-MM-DD, MM/DD/YYYY, or DD/MM/YYYY"


def parse_date_value(value: object, *, day_first: bool = True, label: str = "date") -> date:
    """Parse a bank-statement date or date-time into a ``date``."""
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    original_raw = archive_cell_text(value)
    if not original_raw:
        raise FinancialValidationError("missing date value")
    raw = original_raw.replace(".", "/")
    if raw.isdigit() and len(raw) >= 8:
        try:
            return datetime.strptime(raw[:8], "%Y%m%d").date()
        except ValueError as fmt_exc:
            LOGGER.debug(
                "financial provider: compact date format %r did not match %r (%s); trying next",
                "%Y%m%d",
                raw,
                fmt_exc,
            )
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
    expected_format = _expected_date_format_hint(day_first=day_first)
    raise FinancialValidationError(
        f"unsupported date format: {original_raw!r}; expected {expected_format}",
        translated_message="errors.financial.unsupported_date_format",
        context={"label": label, "raw": original_raw, "expected_format": expected_format},
    )


#: A thousands group is exactly three digits wide in both conventions this
#: parser accepts, so a group of any other width is malformed rather than
#: ambiguous.
_THOUSANDS_GROUP_WIDTH: Final[int] = 3


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
            :class:`int`, :class:`float` (re-parsed via ``str``),
            or text.
        decimal_separator: Optional explicit decimal separator. When
            omitted, the parser infers it from the rightmost
            occurrence of ``,`` or ``.`` in the text.

    Returns:
        A :class:`Decimal` preserving the printed precision and sign.

    Raises:
        FinancialValidationError: When the value is empty, carries scientific
            notation (which sanitisation would silently rewrite into a
            plausible wrong magnitude rather than fail), or cannot be parsed.
    """
    numeric = _already_numeric_amount(value)
    if numeric is not None:
        return numeric
    raw = archive_cell_text(value)
    if not raw:
        raise FinancialValidationError("missing amount value")
    if _EXPONENT_RE.search(raw):
        # Sanitisation drops non-numeric characters so a currency symbol or
        # code (``€1.234,56``, ``100 EUR``) is tolerated. For an exponent
        # marker that same drop silently rewrites the magnitude instead of
        # failing: ``1.23E+05`` would survive as ``1.2305`` — a five-orders-of
        # -magnitude understatement of 123.000,00 that then feeds the ledger
        # and every modelo aggregation built on it. A spreadsheet re-export of
        # a large amount is a real source of this shape, so it must refuse
        # rather than be normalised into a plausible wrong number.
        raise FinancialValidationError(f"scientific-notation amount value: {raw!r}")
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


def _already_numeric_amount(value: object) -> Decimal | None:
    """Return the value as a Decimal when it arrives already numeric.

    ``None`` means the cell is text and must go through the full parse. A
    float is re-parsed via its ``str`` rather than fed to ``Decimal``
    directly, so the printed precision survives instead of the binary
    expansion.
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if not isinstance(value, float):
        return None
    coerced = coerce_decimal(value)
    if coerced is None:
        raise FinancialValidationError(f"unsupported float value: {value!r}")
    return coerced


# A digit, an ``e``/``E``, then an optional sign and a digit: unambiguously an
# exponent. A currency code adjacent to digits (``100 EUR``) does not match,
# because no digit follows the ``E``.
_EXPONENT_RE = re.compile(r"\d\s*[eE]\s*[+-]?\s*\d")


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
    """Drop the thousands separator and rewrite the decimal separator as ``.``.

    A group being dropped as thousands separation MUST be exactly three digits
    wide, and a malformed one refuses rather than being normalised away. This is
    the same stance the scientific-notation guard above takes, for the same
    reason: the drop is silent, so a wrong separator does not fail, it rewrites
    the magnitude into a plausible wrong number that then feeds the ledger and
    every modelo aggregation built on it.

    Measured, and how this was found: a dot-decimal file read under a
    comma-decimal dialect had every ``.`` stripped as grouping, so ``7.77``
    became ``777`` and ``1210.00`` became ``121000`` -- a hundredfold
    overstatement that imported clean and surfaced only much later, when an
    unrelated reconciliation could not make base + IVA meet the gross. Neither
    convention can produce a two-digit final group, so the shape is decidable
    here without guessing which separator the file really meant.
    """
    thousands_sep = "." if decimal_sep == "," else ","
    _reject_malformed_thousands_groups(sanitized, thousands_sep=thousands_sep)
    normalized = sanitized.replace(thousands_sep, "")
    if decimal_sep != ".":
        normalized = normalized.replace(decimal_sep, ".")
    return normalized


def _reject_malformed_thousands_groups(sanitized: str, *, thousands_sep: str) -> None:
    """Refuse text whose ``thousands_sep`` groups are not three digits wide.

    Only the digit runs BETWEEN separators are judged. The leading run is free
    (``1.234`` is one thousand two hundred thirty-four), and a run followed by
    the decimal separator is the integer part rather than a group.
    """
    if thousands_sep not in sanitized:
        return
    segments = sanitized.split(thousands_sep)
    for segment in segments[1:]:
        digits = segment.split(",")[0] if thousands_sep == "." else segment.split(".")[0]
        if len(digits) != _THOUSANDS_GROUP_WIDTH or not digits.isdigit():
            raise FinancialValidationError(
                f"amount value {sanitized!r} groups digits as {digits!r} after the "
                f"{thousands_sep!r} thousands separator, which is not a three-digit "
                f"group: the separator is being read as grouping when the file may "
                f"mean it as the decimal mark, and dropping it would silently change "
                f"the magnitude",
            )


def synthesize_transaction_id(
    *,
    provider_name: str,
    source_sha256: str,
    source_row_index: int,
) -> str:
    """Build a deterministic synthetic transaction identifier."""
    prefix = provider_name.lower().replace(" ", "-")
    return f"{prefix}-{source_sha256[:12]}-{source_row_index}"


class ParsedLedgerRow(BaseModel):
    """One parsed source row: a magnitude :class:`RawTransaction` + its flow.

    The provider observes the bank export's sign (or native debit/credit
    signal) once, at the parse boundary, to choose a
    :class:`~domain.transactions.TransactionDirection`; it then stores the
    **absolute magnitude** on ``raw`` and discards the sign. Downstream the
    import action carries ``direction`` straight onto the
    :class:`~domain.transactions.Transaction`, never re-deriving flow from
    a sign that no longer exists.

    Attributes:
        raw: The verbatim per-row
            :class:`~domain.transactions.RawTransaction` carrying the
            non-negative magnitude amount.
        direction: The authoritative flow direction derived from the source
            sign at the parse boundary.
    """

    model_config = _STRICT_FROZEN

    raw: RawTransaction
    direction: TransactionDirection


def direction_from_signed_amount(signed_amount: Decimal) -> TransactionDirection:
    """Map a source-signed amount to the authoritative :class:`TransactionDirection`.

    A negative source amount is an OUTGOING flow (money out); a positive
    source amount is INCOMING (money in). The sign is consumed exactly once
    here, at the adapter boundary, and discarded; the stored amount is the
    absolute magnitude. A zero amount carries no flow and is rejected by
    :func:`build_raw_transaction` before this is called.
    """
    return TransactionDirection.OUTGOING if signed_amount < Decimal("0") else TransactionDirection.INCOMING


def build_raw_transaction(
    *,
    provider: FinancialProvider,
    path: Path,
    source_sha256: str,
    source_row_index: int,
    provider_transaction_id: str,
    booked_date: date,
    value_date: date | None,
    amount: Decimal,
    currency: str,
    counterparty: str | None,
    description: str,
    raw_fields: Mapping[str, str],
) -> ParsedLedgerRow:
    """Create one :class:`ParsedLedgerRow` from a source-signed amount.

    ``amount`` is the source-signed value as the parser read it. Its sign is
    consumed here to choose the
    :class:`~domain.transactions.TransactionDirection`, then the stored
    :class:`~domain.transactions.RawTransaction` carries the
    absolute magnitude (flow lives in ``direction``, never in the sign). A
    **zero-amount** row carries no flow and is refused at the parse boundary,
    consistent with the manual ledger path.

    Raises:
        InvalidFinancialSourceError: When ``amount`` is zero.
    """
    if amount == Decimal("0"):
        raise InvalidFinancialSourceError(
            f"{provider.name} row {source_row_index} has a zero amount; a ledger movement must be non-zero",
        )
    direction = direction_from_signed_amount(amount)
    raw = RawTransaction(
        provider_transaction_id=provider_transaction_id,
        booked_date=booked_date,
        value_date=value_date,
        amount=abs(amount),
        currency=currency,
        counterparty=counterparty,
        description=description,
        provenance=provider.build_provenance(
            path=path,
            source_sha256=source_sha256,
            source_row_index=source_row_index,
        ),
        raw_fields=raw_fields,
    )
    return ParsedLedgerRow(raw=raw, direction=direction)


def default_currency() -> str:
    """Return the configured project-default financial currency.

    Every provider falls back to this value when a source omits a per-row
    currency, so it reaches the persisted
    :class:`~domain.transactions.RawTransaction` on the fallback branch
    without passing through any column-level check. The
    ``financial_base_currency`` setting itself declares no shape, so it is
    validated here — at the single owner of the fallback — against the same
    :func:`~core.parsing.normalise_iso_4217_currency` policy the per-column
    and per-statement paths use.

    Raises:
        FinancialValidationError: ``financial_base_currency`` is not a
            three-letter ISO 4217 code. Failing here names the misconfigured
            setting, instead of surfacing an opaque record-validation error
            once the value has already been copied onto a parsed row.
    """
    configured = load_settings().financial_base_currency
    try:
        return normalise_iso_4217_currency(configured)
    except CoreValidationError as exc:
        raise FinancialValidationError(
            f"financial_base_currency setting must be a three-letter ISO 4217 code; got {configured!r}",
        ) from exc
