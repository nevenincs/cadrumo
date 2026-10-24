"""CSV financial provider over one bank-neutral statement header vocabulary.

Provides :class:`CsvProvider`, an implementation of
:class:`~adapters.inbound.financial.providers.base.FinancialProvider`
that ingests bank CSV exports whose header row names its columns in the
statement vocabulary of :data:`STATEMENT_COLUMNS`: booking and value dates,
amount, currency, description, counterparty and reference, in Spanish,
Catalan, English and German. No bank is named and no bank's layout is assumed; each file's date
order and decimal separator are inferred from its own printed values. An
export whose headers fall outside the vocabulary is left to the column-role
mapping lane, which reads any layout.

Successful rows become :class:`~adapters.inbound.financial.providers.base.ParsedLedgerRow`
objects: the stored :class:`~domain.transactions.raw_transaction.RawTransaction` carries
an absolute amount and provenance, while
:class:`~domain.transactions.enums.TransactionDirection` records the source flow.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import override

from pydantic import BaseModel

from .....application.ledger.invoice_label_vocabulary import CURRENCY_CODES
from .....core.decimal.grammar import DecimalSeparatorValue
from .....core.errors.error_codes import resolve_error_message
from .....core.errors.hierarchy import CoreValidationError
from .....core.logging import get_logger
from .....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.parsing.codes import normalise_iso_4217_currency
from .....core.tabular import (
    TabularSourceError,
    decode_tabular_bytes,
    detect_tabular_delimiter,
)
from .....domain.transactions.enums import TransactionDirection
from .....domain.transactions.raw_transaction import SourceFormat
from .base import (
    FinancialProvider,
    FinancialValidationError,
    InvalidFinancialSourceError,
    ParsedLedgerRow,
    ProviderValidation,
    archive_cell_text,
    build_raw_transaction,
    default_currency,
    describe_dialect,
    infer_day_first,
    infer_decimal_separator,
    normalize_header,
    parse_date_value,
    parse_statement_amount,
    synthesize_transaction_id,
)

_logger = get_logger(__name__)


class CsvColumnMap(BaseModel):
    """Alias sets for the bank-neutral statement header vocabulary.

    Each tuple lists the lower-cased header strings the parser will
    treat as equivalent for the corresponding logical column. The
    :func:`layout_score` helper scores a candidate header row by the
    number of these aliases it satisfies.

    Attributes:
        booked_date: Aliases for the posting date column.
        value_date: Aliases for the value date column.
        amount: Aliases for the signed amount column.
        currency: Aliases for the optional currency column.
        description: Aliases for the free-form description column.
        counterparty: Aliases for the optional counterparty column.
        external_id: Aliases for the optional external transaction id.
    """

    model_config = _STRICT_FROZEN

    booked_date: tuple[str, ...]
    value_date: tuple[str, ...] = ()
    amount: tuple[str, ...]
    direction: tuple[str, ...] = ("direction",)
    currency: tuple[str, ...] = ()
    description: tuple[str, ...]
    counterparty: tuple[str, ...] = ()
    external_id: tuple[str, ...] = ()


#: A header closing with a currency code, bare or bracketed, once normalized.
_CURRENCY_SUFFIX_RE = re.compile(r"^(.+?) \(?([a-z]{3})\)?$")

STATEMENT_COLUMNS = CsvColumnMap(
    booked_date=(
        "fecha operación",
        "fecha operacion",
        "fecha movimiento",
        "data operació",
        "data operacio",
        "data moviment",
        "fecha",
        "data",
        "completed date",
        "booking date",
        "transaction date",
        "date",
        "datum",
    ),
    value_date=("fecha valor", "data valor", "value date", "started date", "valuta", "wertstellung"),
    amount=("importe", "importe euros", "import", "amount", "betrag"),
    currency=("moneda", "divisa", "currency", "wahrung", "waehrung"),
    description=(
        "concepto",
        "concepte",
        "descripción",
        "descripcion",
        "descripció",
        "descripcio",
        "movimiento",
        "moviment",
        "description",
        "payment reference",
        "verwendungszweck",
        "reference",
        "transaction type",
    ),
    counterparty=(
        "beneficiario",
        "beneficiari",
        "ordenante",
        "ordenant",
        "contraparte",
        "contrapartida",
        "payee",
        "counterparty",
        "partner name",
        "empfanger",
        "empfaenger",
    ),
    external_id=(
        "referencia",
        "referència",
        "referencia operación",
        "referencia operacion",
        "id operación",
        "id operacion",
        "número de referencia",
        "numero de referencia",
        "transaction id",
        "reference id",
        "id",
    ),
)
"""The statement header vocabulary, most specific alias first within each column.

Bank-neutral by construction: every alias is an ordinary statement column name
in Spanish, Catalan, English or German, never one bank's private label. Within a column
the order decides which header wins when a file prints several, so a booking
date outranks a plain date and a completion date outranks a start date.
"""


@dataclass(frozen=True, slots=True)
class StatementConventions:
    """How one statement prints its dates and amounts, inferred from the statement itself.

    Attributes:
        day_first: Whether numeric dates read day before month.
        decimal_separator: The decimal separator the printed amounts prove, or
            ``None`` when no amount proves either; an amount that is then
            ambiguous is refused.
    """

    day_first: bool
    decimal_separator: DecimalSeparatorValue | None


def infer_statement_conventions(
    rows: Iterable[Mapping[str, object]],
    lookup: Mapping[str, str],
    columns: CsvColumnMap = STATEMENT_COLUMNS,
) -> StatementConventions:
    """Infer one statement's date order and decimal separator from its data rows.

    Only cells holding printed text vote; a typed spreadsheet date or number
    carries no convention to infer.

    Raises:
        FinancialValidationError: The statement prints dates in both day-month
            and month-day order.
    """
    candidates = (find_column(lookup, columns.booked_date), find_column(lookup, columns.value_date))
    date_headers = tuple(header for header in candidates if header is not None)
    amount_header = find_column(lookup, columns.amount)
    printed_dates: list[str] = []
    printed_amounts: list[str] = []
    for row in rows:
        for header in date_headers:
            value = row.get(header)
            if isinstance(value, str):
                printed_dates.append(value)
        amount = row.get(amount_header) if amount_header is not None else None
        if isinstance(amount, str):
            printed_amounts.append(amount)
    day_first = infer_day_first(printed_dates)
    if day_first is None:
        raise FinancialValidationError("the statement prints dates in both day-month and month-day order")
    separator, _ = infer_decimal_separator(printed_amounts)
    return StatementConventions(day_first=day_first, decimal_separator=separator)


_AEAT_LEDGER_EXPORT_HEADERS = frozenset(
    normalize_header(header)
    for header in (
        "bucket_id",
        "transaction_id",
        "lifecycle_state",
        "booked_date",
        "effective_date",
        "amount",
        "currency",
        "direction",
        "business_classification",
    )
)
_AEAT_LEDGER_EXPORT_REFUSAL = "AEAT ledger CSV exports cannot be imported through the raw bank CSV provider"
_UNRECOGNISED_HEADERS = "CSV headers do not name a statement's date, amount and description columns"


@dataclass(frozen=True, slots=True)
class ParsedTabularTransactionRow:
    """Typed projection shared by CSV and spreadsheet statement rows."""

    provider_transaction_id: str
    booked_date: date
    value_date: date | None
    amount: Decimal
    direction: TransactionDirection | None
    currency: str
    description: str
    counterparty: str | None


class CsvProvider(FinancialProvider):
    """Ingest raw transactions from bank CSV exports.

    Finds the header row by scoring the first ten rows of the decoded text
    against :data:`STATEMENT_COLUMNS`, infers the file's date order and decimal
    separator from its data rows, then streams the rows through
    :func:`build_raw_transaction`. The
    decoder honours the ``financial_default_csv_encoding`` setting as the
    preferred encoding before falling back to a fixed
    UTF-8 / CP-1252 / ISO-8859-1 sequence.

    A CSV can provide either a source-signed amount or an explicit
    ``direction`` column. The adapter resolves that flow once at the parse
    boundary and emits magnitude-only raw transactions.
    """

    name = "CSV provider"
    source_format = SourceFormat.CSV
    # Corpus fixtures are synthetic CSVs modelled on real bank export schemas;
    # column-mapping fidelity is confirmed against published specifications.
    verification_source = "synthetic_from_bank_published_text"
    provisional_pending_specimen = False

    @override
    def validate_source(self, path: Path) -> ProviderValidation:
        """Validate CSV structure, encoding, and layout support.

        Returns:
            A :class:`ProviderValidation` with the validation outcome.
        """
        try:
            rows, _, encoding, dialect = self._load_rows(path)
        except InvalidFinancialSourceError as exc:
            return ProviderValidation(
                is_valid=False,
                warnings=(str(exc),),
            )
        if not rows:
            return ProviderValidation(
                is_valid=False,
                warnings=("CSV file is empty",),
                detected_encoding=encoding,
                detected_dialect=describe_dialect(dialect),
            )
        if _has_aeat_ledger_export_header(rows):
            return ProviderValidation(
                is_valid=False,
                warnings=(_AEAT_LEDGER_EXPORT_REFUSAL,),
                detected_encoding=encoding,
                detected_dialect=describe_dialect(dialect),
            )
        located = self._locate_header(rows)
        if located is None:
            return ProviderValidation(
                is_valid=False,
                warnings=(_UNRECOGNISED_HEADERS,),
                detected_encoding=encoding,
                detected_dialect=describe_dialect(dialect),
            )
        header_index, headers, lookup = located
        if len(rows) <= header_index + 1:
            return ProviderValidation(
                is_valid=False,
                warnings=("CSV has no data rows after the header",),
                detected_encoding=encoding,
                detected_dialect=describe_dialect(dialect),
            )
        try:
            infer_statement_conventions((_row_to_mapping(headers, row) for row in rows[header_index + 1 :]), lookup)
        except FinancialValidationError as exc:
            return ProviderValidation(
                is_valid=False,
                warnings=(str(exc),),
                detected_encoding=encoding,
                detected_dialect=describe_dialect(dialect),
            )
        warnings: list[str] = []
        if not bool(find_column(lookup, STATEMENT_COLUMNS.currency)):
            warnings.append(f"CSV has no currency column; falling back to {default_currency()}")
        summary = summary_row_positions([_row_to_mapping(headers, row) for row in rows[header_index + 1 :]], lookup)
        if summary:
            warnings.append(
                f"CSV ends with {len(summary)} summary row(s) that are not movements; "
                "a printed total must equal the sum of the movements",
            )
        return ProviderValidation(
            is_valid=True,
            warnings=tuple(warnings),
            detected_encoding=encoding,
            detected_dialect=describe_dialect(dialect),
        )

    @override
    def ingest(self, path: Path) -> Iterator[ParsedLedgerRow]:
        """Yield :class:`ParsedLedgerRow` records (magnitude + direction) from the CSV source."""
        _logger.debug("csv_provider ingest: loading source")
        rows, source_sha256, _, _ = self._load_rows(path)
        if _has_aeat_ledger_export_header(rows):
            raise InvalidFinancialSourceError(_AEAT_LEDGER_EXPORT_REFUSAL)
        located = self._locate_header(rows)
        if located is None:
            raise InvalidFinancialSourceError(_UNRECOGNISED_HEADERS)
        header_index, headers, lookup = located
        data_rows = rows[header_index + 1 :]
        try:
            conventions = infer_statement_conventions((_row_to_mapping(headers, row) for row in data_rows), lookup)
        except FinancialValidationError as exc:
            raise InvalidFinancialSourceError(str(exc)) from None
        mapped_rows = [_row_to_mapping(headers, row) for row in data_rows]
        summary = summary_row_positions(mapped_rows, lookup)
        movements: list[ParsedLedgerRow] = []
        for position, raw_fields in enumerate(mapped_rows):
            source_row_index = header_index + 2 + position
            if row_is_blank(raw_fields) or position in summary:
                continue
            try:
                parsed = parse_tabular_transaction_row(
                    conventions=conventions,
                    lookup=lookup,
                    raw_fields=raw_fields,
                    typed_fields=raw_fields,
                    synthetic_provider_name=self.name,
                    source_sha256=source_sha256,
                    source_row_index=source_row_index,
                    required_field_context="CSV row",
                )
            except (ValueError, FinancialValidationError) as exc:
                _logger.warning(
                    "csv_provider: parse error row=%d reason=%s",
                    source_row_index,
                    "financial_validation" if isinstance(exc, FinancialValidationError) else "invalid_value",
                )
                raise InvalidFinancialSourceError(
                    f"CSV row {source_row_index} could not be parsed: "
                    f"{str(exc) if isinstance(exc, FinancialValidationError) else 'invalid field value'}",
                ) from None
            movements.append(
                build_provider_row(
                    provider=self,
                    path=path,
                    source_sha256=source_sha256,
                    source_row_index=source_row_index,
                    parsed=parsed,
                    raw_fields=raw_fields,
                )
            )
        check_summary_totals(
            (mapped_rows[position] for position in sorted(summary)), lookup, conventions, movements, "CSV"
        )
        yield from movements

    def _load_rows(
        self,
        path: Path,
    ) -> tuple[list[list[str]], str, str, type[csv.Dialect]]:
        """Decode and parse the CSV file into raw rows."""
        source_bytes = self._read_source_bytes(path)
        source_sha256 = self._compute_sha256(source_bytes)
        text, encoding = self._decode_bytes(source_bytes)
        dialect = self._sniff_dialect(text)
        reader = csv.reader(io.StringIO(text), dialect)
        rows = [[cell.strip() for cell in row] for row in reader]
        return rows, source_sha256, encoding, dialect

    def _decode_bytes(self, source_bytes: bytes) -> tuple[str, str]:
        """Decode bytes through the shared tabular codec chain."""
        try:
            text, encoding, _ = decode_tabular_bytes(source_bytes)
        except TabularSourceError as exc:
            raise InvalidFinancialSourceError(resolve_error_message(exc)) from exc
        return text, encoding

    def _sniff_dialect(self, text: str) -> type[csv.Dialect]:
        """Detect the CSV delimiter through the shared whole-file dialect scorer."""
        delimiter = detect_tabular_delimiter(text)
        if delimiter is None:
            return csv.excel

        class _DetectedDialect(csv.excel):
            pass

        _DetectedDialect.delimiter = delimiter
        return _DetectedDialect

    def _locate_header(self, rows: list[list[str]]) -> tuple[int, list[str], Mapping[str, str]] | None:
        """Locate the row that best names the statement columns, or ``None`` when none does."""
        best: tuple[int, list[str], Mapping[str, str]] | None = None
        best_score = -1
        for index, row in enumerate(rows[:10]):
            if not any(cell.strip() for cell in row):
                continue
            lookup = header_lookup(row)
            score = layout_score(lookup)
            if score > best_score:
                best = (index, row, lookup)
                best_score = score
        if best_score < 3:
            return None
        return best


def header_lookup(headers: list[str]) -> dict[str, str]:
    """Build normalized->original header lookup for alias resolution.

    A header closing with a currency code, bare or bracketed (``amount_eur``,
    ``Importe (EUR)``), also answers to the name before the code, unless
    another header already carries that name.
    """
    lookup = {normalize_header(header): header for header in headers if header.strip()}
    for normalized, header in tuple(lookup.items()):
        match = _CURRENCY_SUFFIX_RE.match(normalized)
        if match is not None and match.group(2).upper() in CURRENCY_CODES:
            lookup.setdefault(match.group(1), header)
    return lookup


def summary_row_positions(rows: Sequence[Mapping[str, str]], lookup: Mapping[str, str]) -> frozenset[int]:
    """Return the positions of the summary rows an export appends after its movements.

    A spreadsheet-made export may close with a ``TOTAL`` or ``Saldo final`` row,
    whose date cell names the row in words instead of printing a date. Only the
    trailing run of such rows qualifies: a row without a date between movements
    is still refused as unreadable.
    """
    date_header = find_column(lookup, STATEMENT_COLUMNS.booked_date)
    positions: set[int] = set()
    for position in range(len(rows) - 1, -1, -1):
        fields = rows[position]
        if row_is_blank(fields):
            continue
        cell = fields.get(date_header, "") if date_header is not None else ""
        if not cell.strip() or any(char.isdigit() for char in cell):
            break
        positions.add(position)
    return frozenset(positions)


def check_summary_totals(
    summary_rows: Iterable[Mapping[str, str]],
    lookup: Mapping[str, str],
    conventions: StatementConventions,
    movements: Sequence[ParsedLedgerRow],
    context: str,
) -> None:
    """Refuse a summary row whose printed amount is not the sum of the movements.

    A total the movements do not add up to means a movement was lost or
    misread, so the export is refused whole rather than imported short.

    Raises:
        InvalidFinancialSourceError: A summary amount is unreadable or does not
            equal the signed sum of the movements.
    """
    amount_header = find_column(lookup, STATEMENT_COLUMNS.amount)
    if amount_header is None:
        return
    net = sum(
        (row.raw.amount if row.direction is TransactionDirection.INCOMING else -row.raw.amount for row in movements),
        Decimal(0),
    )
    for fields in summary_rows:
        printed = fields.get(amount_header, "").strip()
        if not printed:
            continue
        try:
            total = parse_statement_amount(printed, decimal_separator=conventions.decimal_separator)
        except (ValueError, FinancialValidationError):
            raise InvalidFinancialSourceError(f"{context}: the summary row's amount is not a readable amount") from None
        if total != net:
            raise InvalidFinancialSourceError(
                f"{context}: the summary row's total does not equal the sum of the movements",
            )


def layout_score(lookup: Mapping[str, str], columns: CsvColumnMap = STATEMENT_COLUMNS) -> int:
    """Return how well one header row names the statement columns."""
    required = (
        find_column(lookup, columns.booked_date),
        find_column(lookup, columns.amount),
        find_column(lookup, columns.description),
    )
    if any(column is None for column in required):
        return 0
    score = 3
    optional_groups = (
        columns.value_date,
        columns.currency,
        columns.counterparty,
        columns.external_id,
    )
    for aliases in optional_groups:
        if aliases and bool(find_column(lookup, aliases)):
            score += 1
    return score


def _has_aeat_ledger_export_header(rows: list[list[str]]) -> bool:
    """Return whether the CSV contains the canonical ledger export header."""
    return any(set(header_lookup(row)) >= _AEAT_LEDGER_EXPORT_HEADERS for row in rows[:10] if any(row))


def find_column(lookup: Mapping[str, str], aliases: tuple[str, ...]) -> str | None:
    """Resolve the first matching original header for ``aliases``."""
    for alias in aliases:
        header = lookup.get(normalize_header(alias))
        if header is not None:
            return header
    return None


def _row_to_mapping(headers: list[str], row: list[str]) -> dict[str, str]:
    """Convert one parsed CSV row into the stored raw-field mapping."""
    padded = row + [""] * max(0, len(headers) - len(row))
    return {header: padded[index] if index < len(padded) else "" for index, header in enumerate(headers)}


def row_is_blank(raw_fields: Mapping[str, str]) -> bool:
    """Return whether a parsed source row carries no usable values."""
    return not any(value.strip() for value in raw_fields.values())


def parse_tabular_transaction_row(
    *,
    conventions: StatementConventions,
    lookup: Mapping[str, str],
    raw_fields: Mapping[str, str],
    typed_fields: Mapping[str, object],
    synthetic_provider_name: str,
    source_sha256: str,
    source_row_index: int,
    required_field_context: str,
) -> ParsedTabularTransactionRow:
    """Project one statement row into typed transaction fields."""
    columns = STATEMENT_COLUMNS
    transaction_id = _value_from_aliases(raw_fields, lookup, columns.external_id)
    if not (transaction_id is not None and transaction_id):
        transaction_id = synthesize_transaction_id(
            provider_name=synthetic_provider_name,
            source_sha256=source_sha256,
            source_row_index=source_row_index,
        )
    booked_date_header, booked_date_raw = _required_typed_value_and_header(
        typed_fields,
        lookup,
        columns.booked_date,
        "booked_date",
        required_field_context,
    )
    booked_date = parse_date_value(
        booked_date_raw,
        day_first=conventions.day_first,
        label=booked_date_header,
    )
    value_date_resolved = _typed_value_and_header_from_aliases(typed_fields, lookup, columns.value_date)
    value_date: date | None = None
    if value_date_resolved is not None:
        value_date_header, value_raw = value_date_resolved
        value_date = parse_date_value(value_raw, day_first=conventions.day_first, label=value_date_header)
    amount = parse_statement_amount(
        _required_typed_value(typed_fields, lookup, columns.amount, "amount", required_field_context),
        decimal_separator=conventions.decimal_separator,
    )
    direction = _direction_from_aliases(raw_fields, lookup, columns.direction)
    currency = _currency_from_aliases(
        raw_fields,
        lookup,
        columns.currency,
        required_field_context,
    )
    description = _required_value(raw_fields, lookup, columns.description, "description")
    counterparty = _value_from_aliases(raw_fields, lookup, columns.counterparty)
    return ParsedTabularTransactionRow(
        provider_transaction_id=transaction_id,
        booked_date=booked_date,
        value_date=value_date,
        amount=amount,
        direction=direction,
        currency=currency,
        description=description,
        counterparty=counterparty,
    )


def build_provider_row(
    *,
    provider: FinancialProvider,
    path: Path,
    source_sha256: str,
    source_row_index: int,
    parsed: ParsedTabularTransactionRow,
    raw_fields: Mapping[str, str],
) -> ParsedLedgerRow:
    """Emit the ledger row for one parsed tabular statement row.

    Shared post-parse tail for the CSV and spreadsheet providers. Delegates to
    :func:`build_raw_transaction` for the magnitude/provenance
    :class:`~domain.transactions.raw_transaction.RawTransaction` and its sign-derived
    direction, then overrides the flow with ``parsed.direction`` when the
    layout carried an explicit direction column. The direction-at-parse-boundary
    contract is unchanged: the sign is consumed exactly once, at the adapter
    boundary.
    """
    built = build_raw_transaction(
        provider=provider,
        path=path,
        source_sha256=source_sha256,
        source_row_index=source_row_index,
        provider_transaction_id=parsed.provider_transaction_id,
        booked_date=parsed.booked_date,
        value_date=parsed.value_date,
        amount=parsed.amount,
        currency=parsed.currency,
        counterparty=parsed.counterparty,
        description=parsed.description,
        raw_fields=raw_fields,
    )
    if parsed.direction is not None:
        return ParsedLedgerRow(raw=built.raw, direction=parsed.direction)
    return built


def _value_from_aliases(
    raw_fields: Mapping[str, str],
    lookup: Mapping[str, str],
    aliases: tuple[str, ...],
) -> str | None:
    """Resolve and read the first non-empty value for a logical column."""
    header = find_column(lookup, aliases)
    if header is None:
        return None
    value = raw_fields.get(header, "")
    normalized = archive_cell_text(value)
    return normalized or None


def _currency_from_aliases(
    raw_fields: Mapping[str, str],
    lookup: Mapping[str, str],
    aliases: tuple[str, ...],
    context: str,
) -> str:
    """Resolve, default, and validate the optional currency column.

    The ISO 4217 shape policy is owned by
    :func:`~core.parsing.codes.normalise_iso_4217_currency`, shared with the OFX
    statement header and with the persisted
    :class:`~domain.transactions.raw_transaction.RawTransaction`; only the column-naming
    context of the refusal is built here.
    """
    header = find_column(lookup, aliases)
    if header is None:
        return default_currency()
    raw = archive_cell_text(raw_fields.get(header, ""))
    if not raw:
        return default_currency()
    try:
        return normalise_iso_4217_currency(raw)
    except CoreValidationError:
        raise FinancialValidationError(
            "currency field must be a three-letter ISO 4217 code",
        ) from None


def _typed_value_from_aliases(
    raw_fields: Mapping[str, object],
    lookup: Mapping[str, str],
    aliases: tuple[str, ...],
) -> object | None:
    """Resolve and read the first non-empty typed value for a logical column."""
    header = find_column(lookup, aliases)
    if header is None:
        return None
    value = raw_fields.get(header, "")
    return value if archive_cell_text(value) else None


def _typed_value_and_header_from_aliases(
    raw_fields: Mapping[str, object],
    lookup: Mapping[str, str],
    aliases: tuple[str, ...],
) -> tuple[str, object] | None:
    """Resolve and read the first non-empty typed value with its source header."""
    header = find_column(lookup, aliases)
    if header is None:
        return None
    value = raw_fields.get(header, "")
    return (header, value) if archive_cell_text(value) else None


def _direction_from_aliases(
    raw_fields: Mapping[str, str],
    lookup: Mapping[str, str],
    aliases: tuple[str, ...],
) -> TransactionDirection | None:
    """Resolve an optional explicit transaction direction column."""
    header = find_column(lookup, aliases)
    if header is None:
        return None
    raw = archive_cell_text(raw_fields.get(header, ""))
    if not raw:
        raise FinancialValidationError("missing direction value")
    normalized = "_".join(raw.replace("-", " ").replace("_", " ").upper().split())
    try:
        return TransactionDirection(normalized)
    except ValueError:
        expected = ", ".join(direction.value for direction in TransactionDirection)
        raise FinancialValidationError(f"unsupported direction value; expected one of {expected}") from None


def _required_value(
    raw_fields: Mapping[str, str],
    lookup: Mapping[str, str],
    aliases: tuple[str, ...],
    field_name: str,
) -> str:
    """Resolve a required logical column and reject missing values."""
    value = _value_from_aliases(raw_fields, lookup, aliases)
    if value is None:
        raise InvalidFinancialSourceError(f"CSV row is missing required field {field_name!r}")
    return value


def _required_typed_value(
    raw_fields: Mapping[str, object],
    lookup: Mapping[str, str],
    aliases: tuple[str, ...],
    field_name: str,
    context: str,
) -> object:
    """Resolve a required logical column from typed tabular cell values."""
    value = _typed_value_from_aliases(raw_fields, lookup, aliases)
    if value is None:
        raise InvalidFinancialSourceError(f"{context} is missing required field {field_name!r}")
    return value


def _required_typed_value_and_header(
    raw_fields: Mapping[str, object],
    lookup: Mapping[str, str],
    aliases: tuple[str, ...],
    field_name: str,
    context: str,
) -> tuple[str, object]:
    """Resolve a required logical column and retain the source header label."""
    resolved = _typed_value_and_header_from_aliases(raw_fields, lookup, aliases)
    if resolved is None:
        raise InvalidFinancialSourceError(f"{context} is missing required field {field_name!r}")
    return resolved
