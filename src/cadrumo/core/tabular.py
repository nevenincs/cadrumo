"""Deterministic dialect normalization for arbitrary tabular exports.

Turns a CSV, TSV or delimited-text export of unknown dialect into one typed
:class:`NormalizedTable`: a header row, verbatim data cells, the preamble and
summary rows separated out, and the detected dialect recorded. It answers
"what shape is this file", never "what does this column mean" — role mapping is
a separate step consuming this output, and no cell value is interpreted here.

The contract lives in :mod:`cadrumo.core` because every layer meets a
delimited export and none of them owns it: the inbound financial adapter
normalizes a bank statement through it, and the application's bulk invoice
import normalizes an invoice book through the same call. A per-layer copy would
mean two delimiter sniffers disagreeing about the same operator file.

Six axes vary across real operator exports and are each detected rather than
assumed: the delimiter (``;``, ``,``, tab, ``|``), the decimal convention
(Spanish comma or English dot), the byte encoding (including a UTF-8 BOM),
metadata preamble rows before the header, appended summary rows after the data,
and newlines embedded inside quoted fields.

Cell text is stored **verbatim**. A Spanish ``1.234,56`` stays
``1.234,56`` in :attr:`NormalizedRow.cells`; the detected
:attr:`TabularDialect.decimal_separator` records how to read it, so the
interpretation is carried alongside the printed form rather than replacing it.
That is what lets a later step copy a cell without a lossy round trip.

Normalization never refuses a file whole. A row whose field count differs from
the table's is carried with a notice rather than dropped, an unreadable
decimal convention is reported and defaulted, and only a source that cannot be
decoded at all, or that yields no usable header, raises
:class:`TabularSourceError`. Each consuming layer translates that refusal into
its own operator-facing error taxonomy.

See Also:
    :class:`~core.FieldRole`
        The closed vocabulary a normalized column's meaning is mapped onto.
    :class:`~domain.transactions.RawTransaction`
        The record a projected tabular row eventually becomes.
"""

from __future__ import annotations

import csv
import io
import re
from collections import Counter
from datetime import date, datetime
from itertools import islice
from typing import Literal

from pydantic import BaseModel, Field

from .config import load_settings
from .decimal._grammar import european_thousands_reading_is_ambiguous
from .errors.hierarchy import CoreValidationError
from .external_constants import CSV_ENCODING_FALLBACK_CHAIN
from .logging import get_logger
from .models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .text_bounds import PositiveCount
from .text_fold import fold_printed_phrase

__all__ = [
    "CANDIDATE_DELIMITERS",
    "NormalizedRow",
    "NormalizedTable",
    "TabularDialect",
    "TabularNotice",
    "TabularNoticeCode",
    "TabularSourceError",
    "coerce_cell_text",
    "decode_tabular_bytes",
    "detect_tabular_delimiter",
    "normalize_tabular_bytes",
    "normalize_tabular_text",
]

_logger = get_logger(__name__)


class TabularSourceError(CoreValidationError):
    """Raised when tabular bytes cannot be decoded or carry no usable table.

    The three structural refusals normalization makes: no candidate codec
    decoded the bytes, no candidate delimiter produced a rectangle, or no row
    in the rectangle reads as a header. Consumers translate it into their own
    layer's refusal — the financial providers into
    ``InvalidFinancialSourceError``, the invoice bulk import into
    ``InvoiceValidationError``.
    """


#: Delimiters a delimited-text export realistically uses. Each is scored
#: against the whole file; the one producing the most consistent rectangle
#: wins, which is what survives a metadata preamble that a sample-window
#: sniffer reads as the table.
CANDIDATE_DELIMITERS: tuple[str, ...] = (";", ",", "\t", "|")

#: How many leading rows may be searched for the header. Real preambles run to
#: about seven lines; twenty leaves margin without letting a header be found in
#: the middle of the data.
_HEADER_SEARCH_LIMIT = 20

#: Leading tokens marking an appended aggregate row rather than a movement.
#: Diacritics are folded before comparison, so ``TOTALES`` and ``Totales``
#: both match.
_SUMMARY_ROW_TOKENS: frozenset[str] = frozenset(
    {"total", "totales", "suma", "sumas", "subtotal", "saldo final", "resumen", "grand total"},
)

_DIGIT_RUN_RE = re.compile(r"\d")
_NUMERIC_EVIDENCE_RE = re.compile(r"^[(+-]?[\d.,]+[)-]?$")
_DATE_LIKE_RE = re.compile(r"^\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}|^\d{8}$")

#: Noise a printed amount carries around its digits: a currency symbol, or an
#: ISO code set off from them. Removed only for the *decision* about whether a
#: cell is numeric; the cell itself is never rewritten.
_CURRENCY_NOISE_RE = re.compile(r"[€$£¥]|(?<![A-Za-z])[A-Za-z]{3}(?![A-Za-z])")

TabularNoticeCode = Literal[
    "encoding_fallback",
    "preamble_skipped",
    "summary_row_excluded",
    "ragged_row",
    "decimal_convention_defaulted",
    "decimal_convention_mixed",
    "blank_row_skipped",
]
"""Closed set of structural observations normalization can report."""


class TabularNotice(BaseModel):
    """One structural observation made while normalizing a source.

    Attributes:
        code: Which observation was made.
        detail: Operator-readable specifics, already carrying the values that
            justify the observation.
        source_line_number: Physical 1-based line the observation is about,
            or ``None`` for a whole-file observation.
    """

    model_config = _STRICT_FROZEN

    code: TabularNoticeCode
    detail: str
    source_line_number: int | None = None


class TabularDialect(BaseModel):
    """The detected shape of one tabular source.

    Attributes:
        delimiter: Field separator the rectangle was parsed with.
        quotechar: Quoting character honoured while parsing.
        encoding: Codec the bytes decoded under.
        decimal_separator: How a numeric cell in this file reads. Recorded,
            never applied — cells keep their printed form.
        header_line_number: Physical 1-based line the header was found on.
        column_count: Field count of the table's rectangle.
    """

    model_config = _STRICT_FROZEN

    delimiter: str = Field(min_length=1, max_length=1)
    quotechar: str = Field(min_length=1, max_length=1)
    encoding: str = Field(min_length=1)
    decimal_separator: Literal[",", "."]
    header_line_number: int = Field(ge=1)
    column_count: PositiveCount


class NormalizedRow(BaseModel):
    """One source row, cells verbatim.

    Attributes:
        source_line_number: Physical 1-based line the row started on. A row
            carrying a newline inside a quoted field spans several physical
            lines; this is the first.
        cells: The parsed fields exactly as printed, with no stripping,
            separator rewriting or type coercion applied.
    """

    model_config = _STRICT_FROZEN

    source_line_number: int = Field(ge=1)
    cells: tuple[str, ...]


class NormalizedTable(BaseModel):
    """One tabular source resolved into a rectangle plus what surrounds it.

    Attributes:
        dialect: The detected dialect.
        headers: Header cells verbatim, one per column of the rectangle.
        rows: Movement rows, in source order.
        preamble: Rows above the header, kept rather than discarded so an
            operator can see the account and period metadata they carry.
        summary_rows: Rows below the data recognised as aggregates. Excluded
            from :attr:`rows` so a ``TOTAL`` line is never read as a movement.
        notices: Every structural observation made while normalizing.
    """

    model_config = _STRICT_FROZEN

    dialect: TabularDialect
    headers: tuple[str, ...]
    rows: tuple[NormalizedRow, ...]
    preamble: tuple[NormalizedRow, ...] = ()
    summary_rows: tuple[NormalizedRow, ...] = ()
    notices: tuple[TabularNotice, ...] = ()


def coerce_cell_text(
    value: object,
    *,
    integral_floats_as_int: bool = False,
    temporal_as_iso: bool = False,
) -> str:
    """Render one source cell as the text a reader stores or matches on.

    A workbook cell arrives as a typed Python object rather than as text —
    openpyxl hands back ``float``, ``datetime`` and ``None`` — so every reader
    of a spreadsheet needs the same value-to-text step. The base rendering is
    ``str(value).strip()``, with ``None`` becoming the empty string.

    Two renderings genuinely differ by consumer, and both are declared rather
    than assumed:

    ``integral_floats_as_int``
        A whole number a spreadsheet stores as ``3.0`` prints as ``"3"``. A
        casilla value is a figure that goes on a return, so a spurious
        ``.0`` is wrong there; a bank statement's raw-field archive keeps the
        source's own spelling instead.
    ``temporal_as_iso``
        A ``date`` or ``datetime`` renders ISO-8601, with a datetime truncated
        to whole seconds. This pins the archived form of a booking stamp
        rather than inheriting whatever ``str()`` currently prints.

    The two axes are disjoint by type, so their order cannot matter.

    Returns:
        The cell's text under the requested renderings.
    """
    if value is None:
        return ""
    if temporal_as_iso:
        if isinstance(value, datetime):
            return value.isoformat(sep=" ", timespec="seconds")
        if isinstance(value, date):
            return value.isoformat()
    if integral_floats_as_int and isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def decode_tabular_bytes(source_bytes: bytes) -> tuple[str, str, TabularNotice | None]:
    """Decode ``source_bytes`` to text, reporting when the preferred codec did not fit.

    A UTF-8 BOM decides the codec outright: ``cp1252`` and ``iso-8859-1``
    decode any byte sequence at all, so a chain that reaches them first would
    silently mojibake a BOM-prefixed UTF-8 file rather than fail over.

    Returns:
        The decoded text, the codec used, and a notice when the configured
        preferred codec was not the one that worked.

    Raises:
        TabularSourceError: No candidate codec decoded the bytes.
    """
    preferred = load_settings().financial_default_csv_encoding.strip()
    if source_bytes.startswith(b"\xef\xbb\xbf"):
        candidates: tuple[str, ...] = ("utf-8-sig",)
    else:
        candidates = (preferred, *CSV_ENCODING_FALLBACK_CHAIN)
    seen: set[str] = set()
    for candidate in candidates:
        folded = candidate.lower()
        if folded in seen:
            continue
        seen.add(folded)
        try:
            text = source_bytes.decode(candidate)
        except (LookupError, UnicodeDecodeError) as exc:
            _logger.debug("tabular normalization: codec %r rejected (%s); trying next", candidate, exc)
            continue
        notice = (
            None
            if folded == preferred.lower()
            else TabularNotice(
                code="encoding_fallback",
                detail=f"decoded as {candidate!r}; the configured preference {preferred!r} did not fit",
            )
        )
        return text, candidate, notice
    raise TabularSourceError(
        f"tabular source could not be decoded as any of {', '.join(candidates)}",
    )


def _parse_with(text: str, delimiter: str, quotechar: str) -> list[tuple[int, list[str]]]:
    """Parse ``text`` under one candidate delimiter, keeping physical line numbers."""
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, quotechar=quotechar)
    parsed: list[tuple[int, list[str]]] = []
    line_start = 1
    for row in reader:
        parsed.append((line_start, list(row)))
        line_start = reader.line_num + 1
    return parsed


def _rectangle_score(widths: Counter[int]) -> tuple[int, int]:
    """Return ``(score, column_count)`` for one candidate parse's width histogram.

    The score rewards the largest consistent rectangle: how many rows share the
    most common field count, times that count. A wrong delimiter collapses
    every line into a single field, scoring nothing, because a one-column
    rectangle is not a table.
    """
    best_score = 0
    best_width = 0
    for width, frequency in widths.items():
        if width < 2:
            continue
        score = frequency * width
        if score > best_score or (score == best_score and width > best_width):
            best_score = score
            best_width = width
    return best_score, best_width


def _score_delimiter(text: str, delimiter: str, quotechar: str) -> tuple[int, int]:
    """Score one candidate delimiter without materializing its parse.

    Only the field-count histogram decides the delimiter, and
    :func:`csv.reader` is a lazy C iterator, so the histogram can be
    accumulated a row at a time. Scoring the four candidates by materializing
    each full parse instead built the whole table four times over to keep one
    of them; on a 50k-row statement that cost tens of megabytes of peak
    allocation, and cost :func:`detect_tabular_delimiter` — which wants no
    parse at all — the parse time as well.

    Every row is still visited, so the score is the whole-file score by
    construction: a bounded leading sample would be a different measurement,
    and would pick a different delimiter on exactly the preamble-bearing and
    summary-bearing exports this module exists to survive.
    """
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, quotechar=quotechar)
    widths: Counter[int] = Counter()
    for row in reader:
        if any(cell.strip() for cell in row):
            widths[len(row)] += 1
    return _rectangle_score(widths)


def _best_delimiter(text: str, quotechar: str) -> tuple[int, int, str] | None:
    """Return ``(score, column_count, delimiter)`` for the winning delimiter.

    ``None`` when no candidate produced a rectangle at all — a single-column
    file, or one no candidate delimiter splits. Ties are decided by
    :data:`CANDIDATE_DELIMITERS` order: the first candidate to reach a score
    holds it, so ``;`` outranks ``,`` at equal evidence.
    """
    best: tuple[int, int, str] | None = None
    for delimiter in CANDIDATE_DELIMITERS:
        score, width = _score_delimiter(text, delimiter, quotechar)
        if score == 0:
            continue
        if best is None or score > best[0]:
            best = (score, width, delimiter)
    return best


def _best_delimiter_parse(
    text: str,
    quotechar: str,
) -> tuple[int, int, str, list[tuple[int, list[str]]]] | None:
    """Return ``(score, column_count, delimiter, parsed)`` for the winning delimiter.

    The full parse is materialized once, for the winner only; the losing
    candidates are streamed for their score and never held.
    """
    best = _best_delimiter(text, quotechar)
    if best is None:
        return None
    score, width, delimiter = best
    return score, width, delimiter, _parse_with(text, delimiter, quotechar)


def detect_tabular_delimiter(text: str, *, quotechar: str = '"') -> str | None:
    """Return the delimiter that splits ``text`` into the most consistent rectangle.

    Scored over the whole file rather than a leading sample window, so a
    metadata preamble a sample-window sniffer would read as the table cannot
    decide the delimiter for the data below it.

    Returns:
        The winning member of :data:`CANDIDATE_DELIMITERS`, or ``None`` when no
        candidate produced a rectangle. A caller that must parse regardless
        chooses its own fallback.
    """
    best = _best_delimiter(text, quotechar)
    return None if best is None else best[2]


def _numeric_body(cell: str) -> str | None:
    """Return the digits-and-separators body of a printed amount, or ``None``.

    Only a currency symbol or an ISO code beside the digits is set aside. A
    cell whose letters are *interleaved* with its digits — ``col_0``,
    ``TPV-02``, ``S-2026/0429`` — is not an amount, and dropping its letters
    the way a naive condense does would read it as one.
    """
    stripped = cell.strip()
    if not stripped or not _DIGIT_RUN_RE.search(stripped):
        return None
    body = _CURRENCY_NOISE_RE.sub("", stripped).replace(" ", "").replace(" ", "")
    if not body or _NUMERIC_EVIDENCE_RE.fullmatch(body) is None:
        return None
    return body


def _looks_numeric(cell: str) -> bool:
    """Return whether a cell reads as a printed amount."""
    return _numeric_body(cell) is not None


def _looks_like_date(cell: str) -> bool:
    """Return whether a cell reads as a printed or compact date."""
    return _DATE_LIKE_RE.match(cell.strip()) is not None


def _row_is_data_like(cells: list[str]) -> bool:
    """Return whether a row carries the numeric or date evidence a movement row has."""
    return any(_looks_like_date(cell) or _looks_numeric(cell) for cell in cells)


def _header_score(cells: list[str], *, next_row: list[str] | None) -> int:
    """Score one candidate header row.

    A header is text: its cells are populated and none of them is a number or a
    date. The row *below* it decides too — a metadata line such as
    ``Titular;Nordeste Estudio Creativo SL`` is populated text as well, and is
    told apart from a real header only by what follows it.
    """
    populated = sum(1 for cell in cells if cell.strip())
    valued = sum(1 for cell in cells if _looks_numeric(cell) or _looks_like_date(cell))
    following = 3 if next_row is not None and _row_is_data_like(next_row) else -5
    return populated * 2 - valued * 3 + following


def _locate_header(parsed: list[tuple[int, list[str]]], *, column_count: int) -> int | None:
    """Return the index in ``parsed`` of the best header row, or ``None``.

    The following-row lookup walks ``parsed`` through :func:`itertools.islice`
    rather than a ``parsed[index + 1 :]`` slice: the slice copies the whole
    remaining table on each of the twenty candidate rows, so locating a header
    in a 50k-row export cost a million element copies to read at most a handful
    of rows. The slice is lazy now; which row it stops on is unchanged.
    """
    best_index: int | None = None
    best_score = 0
    for index, (_, cells) in enumerate(islice(parsed, _HEADER_SEARCH_LIMIT)):
        if len(cells) != column_count:
            continue
        next_row = next(
            (row for _, row in islice(parsed, index + 1, None) if any(cell.strip() for cell in row)),
            None,
        )
        score = _header_score(cells, next_row=next_row)
        if best_index is None or score > best_score:
            best_index = index
            best_score = score
    return best_index


def _is_summary_row(cells: list[str]) -> bool:
    """Return whether a data-region row is an appended aggregate rather than a movement."""
    leading = next((cell for cell in cells if cell.strip()), "")
    folded = fold_printed_phrase(leading)
    return any(
        folded == token or folded.startswith(f"{token} ") or folded.startswith(f"{token}:")
        for token in _SUMMARY_ROW_TOKENS
    )


def _decimal_evidence(cell: str) -> Literal[",", "."] | None:
    """Return which separator a cell proves is decimal, or ``None`` when it proves nothing.

    Only a cell that reads as a printed amount votes. A description such as
    ``Ref. 2026`` carries a dot beside digits without being a number at all,
    and letting it vote would swing the file's convention on prose.
    """
    condensed = _numeric_body(cell)
    if condensed is None:
        return None
    has_comma = "," in condensed
    has_dot = "." in condensed
    if has_comma and has_dot:
        return "," if condensed.rfind(",") > condensed.rfind(".") else "."
    if has_comma:
        return ","
    if has_dot:
        # ``1.234`` reads both ways with nothing in it to choose by, so it is
        # not evidence of anything. Everything else with a dot is a decimal.
        return None if european_thousands_reading_is_ambiguous(condensed) else "."
    return None


def _detect_decimal_separator(
    rows: list[tuple[int, list[str]]],
) -> tuple[Literal[",", "."], TabularNotice | None]:
    """Infer the file's decimal convention from every numeric cell that carries evidence."""
    votes: Counter[Literal[",", "."]] = Counter()
    for _, cells in rows:
        for cell in cells:
            evidence = _decimal_evidence(cell)
            if evidence is not None:
                votes[evidence] += 1
    if not votes:
        return ".", TabularNotice(
            code="decimal_convention_defaulted",
            detail="no numeric cell carried separator evidence; reading amounts as dot-decimal",
        )
    ranked = votes.most_common()
    winner = ranked[0][0]
    if len(ranked) > 1 and ranked[1][1] > 0:
        return winner, TabularNotice(
            code="decimal_convention_mixed",
            detail=(
                f"both conventions appear ({', '.join(f'{sep!r}x{count}' for sep, count in ranked)}); "
                f"reading amounts as {winner!r}-decimal"
            ),
        )
    return winner, None


def normalize_tabular_text(text: str, *, encoding: str, quotechar: str = '"') -> NormalizedTable:
    """Resolve already-decoded tabular ``text`` into a :class:`NormalizedTable`.

    Args:
        text: The decoded source.
        encoding: Codec the text was decoded under, recorded on the dialect.
        quotechar: Quoting character to honour.

    Returns:
        The normalized table.

    Raises:
        TabularSourceError: The source carries no delimited rectangle, or no
            row in it reads as a header.
    """
    notices: list[TabularNotice] = []
    best = _best_delimiter_parse(text, quotechar)
    if best is None:
        raise TabularSourceError(
            f"tabular source carries no delimited rectangle under any of {CANDIDATE_DELIMITERS}",
        )
    _, column_count, delimiter, parsed = best

    header_index = _locate_header(parsed, column_count=column_count)
    if header_index is None:
        raise TabularSourceError(
            f"tabular source has no row of {column_count} fields that reads as a header",
        )
    header_line, header_cells = parsed[header_index]

    preamble: list[NormalizedRow] = []
    for line_number, cells in parsed[:header_index]:
        if not any(cell.strip() for cell in cells):
            continue
        preamble.append(NormalizedRow(source_line_number=line_number, cells=tuple(cells)))
    if preamble:
        notices.append(
            TabularNotice(
                code="preamble_skipped",
                detail=f"{len(preamble)} metadata row(s) above the header were not read as movements",
                source_line_number=preamble[0].source_line_number,
            ),
        )

    rows: list[NormalizedRow] = []
    summary_rows: list[NormalizedRow] = []
    data_region = parsed[header_index + 1 :]
    for line_number, cells in data_region:
        if not any(cell.strip() for cell in cells):
            notices.append(
                TabularNotice(
                    code="blank_row_skipped",
                    detail="row carried no values",
                    source_line_number=line_number,
                ),
            )
            continue
        row = NormalizedRow(source_line_number=line_number, cells=tuple(cells))
        if _is_summary_row(cells):
            summary_rows.append(row)
            notices.append(
                TabularNotice(
                    code="summary_row_excluded",
                    detail=f"row leads with an aggregate label {cells[0]!r} and was not read as a movement",
                    source_line_number=line_number,
                ),
            )
            continue
        if len(cells) != column_count:
            notices.append(
                TabularNotice(
                    code="ragged_row",
                    detail=f"row carries {len(cells)} field(s) against the table's {column_count}",
                    source_line_number=line_number,
                ),
            )
        rows.append(row)

    decimal_separator, decimal_notice = _detect_decimal_separator(
        [(row.source_line_number, list(row.cells)) for row in rows],
    )
    if decimal_notice is not None:
        notices.append(decimal_notice)

    return NormalizedTable(
        dialect=TabularDialect(
            delimiter=delimiter,
            quotechar=quotechar,
            encoding=encoding,
            decimal_separator=decimal_separator,
            header_line_number=header_line,
            column_count=column_count,
        ),
        headers=tuple(header_cells),
        rows=tuple(rows),
        preamble=tuple(preamble),
        summary_rows=tuple(summary_rows),
        notices=tuple(notices),
    )


def normalize_tabular_bytes(source_bytes: bytes, *, quotechar: str = '"') -> NormalizedTable:
    """Decode and normalize raw tabular bytes into a :class:`NormalizedTable`.

    Raises:
        TabularSourceError: The bytes cannot be decoded, carry no delimited
            rectangle, or carry no header row.
    """
    text, encoding, encoding_notice = decode_tabular_bytes(source_bytes)
    table = normalize_tabular_text(text, encoding=encoding, quotechar=quotechar)
    if encoding_notice is None:
        return table
    return table.model_copy(update={"notices": (encoding_notice, *table.notices)})
