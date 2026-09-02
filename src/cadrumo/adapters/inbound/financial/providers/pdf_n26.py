"""N26 PDF statement provider backed by ``pdfplumber``.

Implements :class:`PdfN26Provider`, an
:class:`~adapters.inbound.financial.providers.FinancialProvider`
that parses German-language N26 monthly PDF statements. The parser
is anchored on the ``Beschreibung Verbuchungsdatum Betrag`` table
header and a regex matched against each line below it; continuation
lines (value-date stamps, IBAN annotations, free-form remittance
text) attach to the most recent header row.

The PDF provider emits
:class:`~adapters.inbound.financial.providers.ParsedLedgerRow` records
with PDF-backed :class:`~domain.transactions.RawProvenance`. Its current
fixture corpus is generated from sanitised, published N26 statement text; it
proves this line-structure family but does not claim exhaustive coverage of
every N26 current-account or FX statement variant.
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import TypedDict, override

from .....core.decimal.grammar import DecimalSeparator
from .....core.external_constants import DEFAULT_CURRENCY
from .....core.logging import get_logger
from .....domain.transactions.raw_transaction import SourceFormat
from ...pdf.redaction import INPUT_PDF_SOURCE_LABEL as _INPUT_PDF_SOURCE_LABEL
from ._constants import PDF_EXTENSION
from .base import (
    FinancialProvider,
    InvalidFinancialSourceError,
    ParsedLedgerRow,
    ProviderValidation,
    build_raw_transaction,
    parse_amount_value,
    parse_date_value,
    synthesize_transaction_id,
)

_HEADER_LINE = "Beschreibung Verbuchungsdatum Betrag"
_BANK_MARKERS = ("N26 Bank AG", "N26 Bank SE")
_SECTION_MARKERS = (
    "Zusammenfassung",
    "Uebersicht",
    "Übersicht",
    "Uebersicht zu Gebuehren und Zinsen",
    "Übersicht zu Gebühren und Zinsen",
    "Anmerkung",
    "Vierteljaehrlicher Rechnungsabschluss",
    "Vierteljährlicher Rechnungsabschluss",
)
_INTERNAL_NARRATIVES = frozenset(
    {
        "Zinsertrag",
        "Abgeltungssteuer",
        "Solidaritaetszuschlag",
        "Solidaritätszuschlag",
        "An Hauptkonto",
        "Von Hauptkonto",
    },
)
_ROW_RE = re.compile(
    r"^(?P<narrative>.+?) (?P<booked_date>\d{2}\.\d{2}\.\d{4}) (?P<amount>[+-][\d\.,]+)EUR$",
)
_VALUE_DATE_RE = re.compile(r"^Wertstellung (?P<value_date>\d{2}\.\d{2}\.\d{4})$")
_STATEMENT_NUMBER_RE = re.compile(r"(?:Kontoauszug )?Nr\. (?P<number>\d+/\d+)")
_PERIOD_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4} bis \d{2}\.\d{2}\.\d{4}$")

_logger = get_logger(__name__)


class _InProgressRow(TypedDict):
    """Mutable scratch row collected while iterating page lines."""

    base_line: str
    narrative: str
    booked_date: str
    amount: str
    continuations: list[str]


class _ParsedRow(TypedDict):
    """Frozen statement row produced by :func:`_finalize_row`."""

    base_line: str
    narrative: str
    booked_date: str
    amount: str
    value_date: str | None
    continuations: tuple[str, ...]
    page_number: int
    page_lines: tuple[str, ...]


class PdfN26Provider(FinancialProvider):
    """Ingest raw transactions from N26 monthly PDF statements.

    The provider rejects any PDF that does not carry the N26 bank
    marker, the ``Kontoauszug`` heading, and the canonical
    transaction-table header line, so an arbitrary PDF cannot be
    silently accepted as an N26 statement. Internal-flow narratives
    (interest credits, savings transfers, withholding tax) are
    flagged via :data:`_INTERNAL_NARRATIVES` so the
    :func:`_derive_counterparty_and_description` helper drops the
    counterparty for those rows.

    The provider declares ``verification_source =
    "synthetic_from_bank_published_text"`` and keeps the parser PDF-only; CSV,
    OFX, and XLSX exports are handled by their sibling providers.
    """

    name = "n26-pdf"
    supported_extensions = frozenset({PDF_EXTENSION})
    source_format = SourceFormat.PDF
    # Corpus PDFs are synthetic fixtures generated from sanitised text dumps
    # from the portfolio-performance open-source test corpus (Kontoauszug01.txt,
    # Kontoauszug06.txt, Kontoauszug07.txt). The line-structure family matches
    # real N26 PDF layouts; no raw operator statement PDFs are held.
    # Set provisional_pending_specimen = True when real operator PDFs are
    # acquired to trigger the corpus upgrade gate.
    verification_source = "synthetic_from_bank_published_text"
    provisional_pending_specimen = False

    @override
    def validate_source(self, path: Path) -> ProviderValidation:
        """Validate that ``path`` is an N26 PDF statement with at least one row.

        Returns:
            A :class:`ProviderValidation` with the validation outcome.
        """
        try:
            pages = self._extract_pages(path)
            self._require_n26_statement(pages)
            currency = _extract_statement_currency(pages)
            row_count = sum(1 for _ in _iter_statement_rows(pages))
        except InvalidFinancialSourceError as exc:
            return ProviderValidation(is_valid=False, warnings=(str(exc),))
        if row_count == 0:
            return ProviderValidation(
                is_valid=False,
                warnings=("N26 PDF statement contains no transaction rows",),
                detected_encoding="pdfplumber",
            )
        return ProviderValidation(
            is_valid=True,
            warnings=(),
            detected_encoding="pdfplumber",
            detected_dialect=f"pages={len(pages)};currency={currency};rows={row_count}",
        )

    @override
    def ingest(self, path: Path) -> Iterator[ParsedLedgerRow]:
        """Yield :class:`ParsedLedgerRow` records (magnitude + direction) from the N26 PDF statement."""
        source_bytes = self._read_source_bytes(path)
        source_sha256 = self._compute_sha256(source_bytes)
        pages = self._extract_pages(path)
        self._require_n26_statement(pages)
        currency = _extract_statement_currency(pages)
        for source_row_index, parsed_row in enumerate(_iter_statement_rows(pages), start=1):
            booked_date = parse_date_value(parsed_row["booked_date"])
            value_date_text = parsed_row.get("value_date")
            value_date = parse_date_value(value_date_text) if value_date_text else None
            amount = parse_amount_value(parsed_row["amount"], decimal_separator=DecimalSeparator.COMMA)
            counterparty, description = _derive_counterparty_and_description(
                parsed_row["narrative"],
                parsed_row["continuations"],
            )
            statement_number = _extract_statement_number(parsed_row["page_lines"])
            statement_period = _extract_statement_period(parsed_row["page_lines"])
            raw_fields: dict[str, str] = {
                "statement_number": statement_number or "",
                "statement_period": statement_period or "",
                "page_number": str(parsed_row["page_number"]),
                "description_line": parsed_row["base_line"],
                "booked_date_raw": parsed_row["booked_date"],
                "amount_raw": parsed_row["amount"],
                "value_date_raw": value_date_text or "",
                "narrative_raw": parsed_row["narrative"],
            }
            for index, continuation in enumerate(parsed_row["continuations"], start=1):
                raw_fields[f"continuation_{index}"] = continuation
            transaction_id = synthesize_transaction_id(
                provider_name=self.name,
                source_sha256=source_sha256,
                source_row_index=source_row_index,
            )
            yield build_raw_transaction(
                provider=self,
                path=path,
                source_sha256=source_sha256,
                source_row_index=source_row_index,
                provider_transaction_id=transaction_id,
                booked_date=booked_date,
                value_date=value_date,
                amount=amount,
                currency=currency,
                counterparty=counterparty,
                description=description,
                raw_fields=raw_fields,
            )

    def _extract_pages(self, path: Path) -> tuple[tuple[str, ...], ...]:
        """Return normalized text lines for every PDF page."""
        try:
            import pdfplumber
        except ImportError as exc:
            raise InvalidFinancialSourceError("pdfplumber is not installed") from exc
        try:
            with pdfplumber.open(str(path)) as pdf:
                pages: list[tuple[str, ...]] = []
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    lines = tuple(line.strip() for line in text.splitlines() if line.strip())
                    pages.append(lines)
        # BROAD-EXCEPT-RATIONALE-PDF-N26-TEARDOWN: pdfplumber raises
        # OSError (I/O failure), ValueError (malformed structure), and
        # struct.error (corrupt binary data) from its C-level PDF parser.
        # The upstream exception surface is not fully typed and grows
        # with library versions, so the broad catch is intentional to
        # guarantee conversion to InvalidFinancialSourceError.
        except Exception as exc:
            # Debug, not error: this is reached during the ``--provider auto``
            # detection probe loop for every non-PDF (or unreadable) input,
            # where a parse miss is the expected, non-fatal signal that this
            # provider does not match. The failure is converted to an
            # InvalidFinancialSourceError that detection treats as a miss; the
            # operator-facing refusal is raised once by the caller.
            _logger.debug(
                "pdf_n26_provider: failed to parse PDF file %s: %s",
                _INPUT_PDF_SOURCE_LABEL,
                type(exc).__name__,
            )
            raise InvalidFinancialSourceError(
                f"could not parse PDF file: {_INPUT_PDF_SOURCE_LABEL}",
                translated_message="adapters.inbound.financial.providers.pdf_n26.errors.parse_failed",
                context={"source": _INPUT_PDF_SOURCE_LABEL},
            ) from exc
        if not pages:
            raise InvalidFinancialSourceError("PDF file contains no pages")
        return tuple(pages)

    def _require_n26_statement(self, pages: tuple[tuple[str, ...], ...]) -> None:
        """Reject PDFs that do not look like N26 statements."""
        all_lines = tuple(line for page_lines in pages for line in page_lines)
        if not any("Kontoauszug" in line for line in all_lines):
            raise InvalidFinancialSourceError("PDF is missing the N26 statement heading")
        if not any(marker in line for line in all_lines for marker in _BANK_MARKERS):
            raise InvalidFinancialSourceError("PDF is not an N26 statement")
        if not any(_HEADER_LINE in page_lines for page_lines in pages):
            raise InvalidFinancialSourceError("PDF is missing the N26 transaction table header")


def _iter_statement_rows(
    pages: tuple[tuple[str, ...], ...],
) -> Iterator[_ParsedRow]:
    """Yield the raw transaction rows found in statement pages."""
    for page_number, page_lines in enumerate(pages, start=1):
        yield from _iter_page_rows(page_lines, page_number)


def _iter_page_rows(
    page_lines: tuple[str, ...],
    page_number: int,
) -> Iterator[_ParsedRow]:
    """Yield row records on one page; an unfinished row at end-of-page is finalised too."""
    if _HEADER_LINE not in page_lines:
        return
    header_index = page_lines.index(_HEADER_LINE)
    current: _InProgressRow | None = None
    for line in page_lines[header_index + 1 :]:
        if _is_footer_or_section_line(line):
            if current is not None:
                yield _finalize_row(current, page_number, page_lines)
            return
        next_row = _start_new_row(line) if _ROW_RE.match(line) else None
        if next_row is not None:
            if current is not None:
                yield _finalize_row(current, page_number, page_lines)
            current = next_row
            continue
        if current is not None:
            current["continuations"].append(line)
    if current is not None:
        yield _finalize_row(current, page_number, page_lines)


def _start_new_row(line: str) -> _InProgressRow | None:
    """Match ``line`` against ``_ROW_RE`` and return a fresh in-progress row, or ``None``."""
    match = _ROW_RE.match(line)
    if match is None:
        return None
    return {
        "base_line": line,
        "narrative": match.group("narrative"),
        "booked_date": match.group("booked_date"),
        "amount": match.group("amount"),
        "continuations": [],
    }


def _finalize_row(
    current: _InProgressRow,
    page_number: int,
    page_lines: Sequence[str],
) -> _ParsedRow:
    """Attach derived row metadata before yielding the parsed row."""
    continuations = tuple(str(value) for value in current["continuations"])
    value_date = None
    for continuation in continuations:
        match = _VALUE_DATE_RE.match(continuation)
        if match is not None:
            value_date = match.group("value_date")
            break
    return {
        "base_line": str(current["base_line"]),
        "narrative": str(current["narrative"]),
        "booked_date": str(current["booked_date"]),
        "amount": str(current["amount"]),
        "value_date": value_date,
        "continuations": continuations,
        "page_number": page_number,
        "page_lines": tuple(page_lines),
    }


def _extract_statement_currency(pages: tuple[tuple[str, ...], ...]) -> str:
    """Return the statement currency from the PDF text."""
    all_lines = tuple(line for page_lines in pages for line in page_lines)
    if any(DEFAULT_CURRENCY in line for line in all_lines):
        return DEFAULT_CURRENCY
    raise InvalidFinancialSourceError("could not determine statement currency from the PDF")


def _extract_statement_number(lines: Sequence[str]) -> str | None:
    """Return the statement number if it is present in the page header."""
    for line in lines:
        match = _STATEMENT_NUMBER_RE.search(line)
        if match is not None:
            number = match.group("number")
            if isinstance(number, str):
                return number
            raise InvalidFinancialSourceError("statement number match did not contain text")
    return None


def _extract_statement_period(lines: Sequence[str]) -> str | None:
    """Return the statement period if it is present in the page header."""
    for line in lines:
        if _PERIOD_RE.match(line):
            return line
    return None


def _derive_counterparty_and_description(
    narrative: str,
    continuations: Sequence[str],
) -> tuple[str | None, str]:
    """Split counterparty and description conservatively from N26 row text."""
    info_lines = [line for line in continuations if not _VALUE_DATE_RE.match(line) and not line.startswith("IBAN:")]
    cleaned_narrative = narrative.strip()
    if cleaned_narrative in _INTERNAL_NARRATIVES:
        description = " ".join([cleaned_narrative, *info_lines]).strip()
        return None, description
    if info_lines:
        return cleaned_narrative, " ".join(info_lines).strip()
    return None, cleaned_narrative


def _is_footer_or_section_line(line: str) -> bool:
    """Return whether `line` starts a non-transaction section."""
    return (
        "Kontotyp:" in line
        or line.startswith("N26 Bank ")
        or any(line.startswith(marker) for marker in _SECTION_MARKERS)
    )
