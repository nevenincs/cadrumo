"""CSV financial provider with bank-layout-aware parsing.

Provides :class:`CsvProvider`, an implementation of
:class:`~adapters.inbound.financial.providers.FinancialProvider`
that ingests bank CSV exports for the BBVA, Santander, CaixaBank and
Revolut layouts. Each layout is described by a frozen
:class:`CsvBankLayout` carrying the header aliases, date-format
hint, and decimal-separator hint the parser needs.

Successful rows become :class:`~adapters.inbound.financial.providers.ParsedLedgerRow`
objects: the stored :class:`~domain.transactions.RawTransaction` carries
an absolute amount and provenance, while
:class:`~domain.transactions.TransactionDirection` records the source flow.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import override

from pydantic import BaseModel, Field

from .....core.decimal.grammar import DecimalSeparator, DecimalSeparatorValue
from .....core.errors.error_codes import resolve_error_message
from .....core.errors.hierarchy import CoreValidationError
from .....core.logging import get_logger
from .....core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from .....core.parsing import normalise_iso_4217_currency
from .....core.tabular import (
    TabularSourceError,
    decode_tabular_bytes,
    detect_tabular_delimiter,
)
from .....domain.transactions.enums import TransactionDirection
from .....domain.transactions.raw_transaction import SourceFormat
from ._constants import CSV_EXTENSIONS
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
    normalize_header,
    parse_amount_value,
    parse_date_value,
    synthesize_transaction_id,
)

_logger = get_logger(__name__)


class CsvColumnMap(BaseModel):
    """Alias sets for one bank CSV layout.

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


class CsvBankLayout(BaseModel):
    """Named bank CSV layout supported by the provider.

    Attributes:
        bank_name: Human-readable bank identifier embedded in
            synthetic transaction ids and detection diagnostics.
        columns: Header aliases for every logical column.
        day_first_dates: Whether the bank prints dates in
            ``DD/MM/YYYY`` (the European default) or ``YYYY-MM-DD``.
        decimal_separator: Decimal separator the bank uses; ``,`` for
            Spanish banks, ``.`` for Revolut.
    """

    model_config = _STRICT_FROZEN

    bank_name: str = Field(min_length=1)
    columns: CsvColumnMap
    day_first_dates: bool = True
    decimal_separator: DecimalSeparatorValue = DecimalSeparator.COMMA


BBVA_LAYOUT = CsvBankLayout(
    bank_name="BBVA",
    columns=CsvColumnMap(
        booked_date=("fecha operación", "fecha operacion"),
        value_date=("fecha valor",),
        amount=("importe", "importe euros"),
        currency=("moneda", "divisa"),
        description=("concepto", "descripcion"),
        counterparty=("beneficiario", "ordenante", "contraparte"),
        external_id=("referencia", "id operación", "id operacion"),
    ),
)
SANTANDER_LAYOUT = CsvBankLayout(
    bank_name="Santander",
    columns=CsvColumnMap(
        booked_date=("fecha", "fecha operación", "fecha operacion"),
        value_date=("fecha valor",),
        amount=("importe",),
        currency=("divisa", "moneda"),
        description=("concepto", "descripción", "descripcion"),
        counterparty=("beneficiario", "ordenante", "contrapartida"),
        external_id=("referencia", "número de referencia", "numero de referencia"),
    ),
)
CAIXABANK_LAYOUT = CsvBankLayout(
    bank_name="CaixaBank",
    columns=CsvColumnMap(
        booked_date=("fecha", "fecha movimiento"),
        value_date=("fecha valor",),
        amount=("importe",),
        currency=("divisa", "moneda"),
        description=("concepto", "descripción", "descripcion", "movimiento"),
        counterparty=("beneficiario", "ordenante", "contrapartida"),
        external_id=("referencia", "referencia operación", "referencia operacion"),
    ),
)
REVOLUT_LAYOUT = CsvBankLayout(
    bank_name="Revolut",
    columns=CsvColumnMap(
        booked_date=("completed date",),
        value_date=("started date",),
        amount=("amount",),
        currency=("currency",),
        description=("description",),
        counterparty=("payee", "counterparty"),
        external_id=("id", "reference"),
    ),
    day_first_dates=False,
    decimal_separator=DecimalSeparator.PERIOD,
)
N26_LAYOUT = CsvBankLayout(
    bank_name="N26",
    columns=CsvColumnMap(
        booked_date=("date", "datum", "booking date", "transaction date"),
        value_date=("value date", "valuta", "wertstellung"),
        amount=("amount (eur)", "betrag (eur)", "amount", "betrag"),
        currency=("currency", "wahrung", "waehrung"),
        description=("payment reference", "reference", "description", "verwendungszweck", "transaction type"),
        counterparty=("payee", "empfanger", "empfaenger", "counterparty", "partner name"),
        external_id=("id", "transaction id", "reference id"),
    ),
    day_first_dates=False,
    decimal_separator=DecimalSeparator.PERIOD,
)
CSV_LAYOUTS: tuple[CsvBankLayout, ...] = (
    N26_LAYOUT,
    BBVA_LAYOUT,
    SANTANDER_LAYOUT,
    CAIXABANK_LAYOUT,
    REVOLUT_LAYOUT,
)
"""Ordered tuple of bank layouts the CSV provider will try to match."""

_AEAT_LEDGER_EXPORT_HEADERS = frozenset(
    {
        "bucket_id",
        "transaction_id",
        "lifecycle_state",
        "booked_date",
        "effective_date",
        "amount",
        "currency",
        "direction",
        "business_classification",
    },
)
_AEAT_LEDGER_EXPORT_REFUSAL = "AEAT ledger CSV exports cannot be imported through the raw bank CSV provider"


@dataclass(frozen=True, slots=True)
class ParsedTabularTransactionRow:
    """Typed projection shared by CSV and spreadsheet bank-layout rows."""

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

    Detects the bank layout by scoring the first ten rows of the
    decoded text against every entry in :data:`CSV_LAYOUTS`, then
    streams the data rows through :func:`build_raw_transaction`. The
    decoder honours the ``financial_default_csv_encoding`` setting as the
    preferred encoding before falling back to a fixed
    UTF-8 / CP-1252 / ISO-8859-1 sequence.

    CSV layouts can provide either a source-signed amount or an explicit
    ``direction`` column. The adapter resolves that flow once at the parse
    boundary and emits magnitude-only raw transactions.
    """

    name = "CSV provider"
    supported_extensions = CSV_EXTENSIONS
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
        header_index, layout, _, _ = self._locate_header(rows)
        if layout is None:
            return ProviderValidation(
                is_valid=False,
                warnings=("CSV headers do not match any supported bank layout",),
                detected_encoding=encoding,
                detected_dialect=describe_dialect(dialect),
            )
        if len(rows) <= header_index + 1:
            return ProviderValidation(
                is_valid=False,
                warnings=(f"{layout.bank_name} CSV has no data rows after the header",),
                detected_encoding=encoding,
                detected_dialect=describe_dialect(dialect),
            )
        warnings: list[str] = []
        lookup = header_lookup(rows[header_index])
        if not find_column(lookup, layout.columns.currency):
            warnings.append(
                f"{_currency_warning_subject(layout, lookup)} has no currency column; "
                f"falling back to {default_currency()}",
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
        _logger.debug("csv_provider ingest: loading %s", path.name)
        rows, source_sha256, _, _ = self._load_rows(path)
        if _has_aeat_ledger_export_header(rows):
            raise InvalidFinancialSourceError(_AEAT_LEDGER_EXPORT_REFUSAL)
        header_index, layout, headers, lookup = self._locate_header(rows)
        if layout is None or headers is None or lookup is None:
            raise InvalidFinancialSourceError("CSV headers do not match any supported bank layout")
        _logger.info("csv_provider ingest: matched layout=%s path=%s", layout.bank_name, path.name)
        data_rows = rows[header_index + 1 :]
        for source_row_index, row in enumerate(data_rows, start=header_index + 2):
            raw_fields = _row_to_mapping(headers, row)
            if row_is_blank(raw_fields):
                continue
            try:
                parsed = parse_tabular_transaction_row(
                    layout=layout,
                    lookup=lookup,
                    raw_fields=raw_fields,
                    typed_fields=raw_fields,
                    synthetic_provider_name=layout.bank_name,
                    source_sha256=source_sha256,
                    source_row_index=source_row_index,
                    required_field_context="CSV row",
                )
            except (ValueError, FinancialValidationError) as exc:
                _logger.warning(
                    "csv_provider: parse error row=%d file=%s",
                    source_row_index,
                    path.name,
                    exc_info=True,
                )
                raise InvalidFinancialSourceError(
                    f"CSV row {source_row_index} could not be parsed: {resolve_error_message(exc)}",
                ) from exc
            yield build_provider_row(
                provider=self,
                path=path,
                source_sha256=source_sha256,
                source_row_index=source_row_index,
                parsed=parsed,
                raw_fields=raw_fields,
            )

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

    def _locate_header(
        self,
        rows: list[list[str]],
    ) -> tuple[int, CsvBankLayout | None, list[str] | None, Mapping[str, str] | None]:
        """Locate the best header row and matching bank layout."""
        best_index = -1
        best_layout: CsvBankLayout | None = None
        best_headers: list[str] | None = None
        best_lookup: Mapping[str, str] | None = None
        best_score = -1
        for index, row in enumerate(rows[:10]):
            if not any(cell.strip() for cell in row):
                continue
            lookup = header_lookup(row)
            for layout in CSV_LAYOUTS:
                score = layout_score(lookup, layout)
                if score > best_score:
                    best_index = index
                    best_layout = layout
                    best_headers = row
                    best_lookup = lookup
                    best_score = score
        if best_score < 3:
            return 0, None, None, None
        return best_index, best_layout, best_headers, best_lookup


def header_lookup(headers: list[str]) -> dict[str, str]:
    """Build normalized->original header lookup for alias resolution."""
    return {normalize_header(header): header for header in headers if header.strip()}


def layout_score(lookup: Mapping[str, str], layout: CsvBankLayout) -> int:
    """Return a match score for one layout against one header row."""
    required = (
        find_column(lookup, layout.columns.booked_date),
        find_column(lookup, layout.columns.amount),
        find_column(lookup, layout.columns.description),
    )
    if any(column is None for column in required):
        return 0
    score = 3
    optional_groups = (
        layout.columns.value_date,
        layout.columns.currency,
        layout.columns.counterparty,
        layout.columns.external_id,
    )
    for aliases in optional_groups:
        if aliases and find_column(lookup, aliases):
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


_GENERIC_CSV_WARNING_ALIASES = frozenset({"date", "description", "amount", "direction"})


def _currency_warning_subject(layout: CsvBankLayout, lookup: Mapping[str, str]) -> str:
    """Return the provider label for a missing-currency warning.

    A generic CSV with headers like ``Date,Description,Amount`` scores against
    the N26 layout because those are valid N26 aliases, but it does not carry
    any bank-specific signal. Keep that warning provider-neutral while preserving
    provider-specific wording for real N26 and other bank exports.
    """
    matched_aliases: set[str] = set()
    alias_groups = (
        layout.columns.booked_date,
        layout.columns.value_date,
        layout.columns.amount,
        layout.columns.direction,
        layout.columns.description,
        layout.columns.counterparty,
        layout.columns.external_id,
    )
    for aliases in alias_groups:
        for alias in aliases:
            normalized = normalize_header(alias)
            if normalized in lookup:
                matched_aliases.add(normalized)
    if matched_aliases and matched_aliases <= _GENERIC_CSV_WARNING_ALIASES:
        return "CSV"
    return f"{layout.bank_name} CSV"


def _row_to_mapping(headers: list[str], row: list[str]) -> dict[str, str]:
    """Convert one parsed CSV row into the stored raw-field mapping."""
    padded = row + [""] * max(0, len(headers) - len(row))
    return {header: padded[index] if index < len(padded) else "" for index, header in enumerate(headers)}


def row_is_blank(raw_fields: Mapping[str, str]) -> bool:
    """Return whether a parsed source row carries no usable values."""
    return not any(value.strip() for value in raw_fields.values())


def parse_tabular_transaction_row(
    *,
    layout: CsvBankLayout,
    lookup: Mapping[str, str],
    raw_fields: Mapping[str, str],
    typed_fields: Mapping[str, object],
    synthetic_provider_name: str,
    source_sha256: str,
    source_row_index: int,
    required_field_context: str,
) -> ParsedTabularTransactionRow:
    """Project one bank-layout row into typed transaction fields."""
    transaction_id = _value_from_aliases(raw_fields, lookup, layout.columns.external_id)
    if not transaction_id:
        transaction_id = synthesize_transaction_id(
            provider_name=synthetic_provider_name,
            source_sha256=source_sha256,
            source_row_index=source_row_index,
        )
    booked_date_header, booked_date_raw = _required_typed_value_and_header(
        typed_fields,
        lookup,
        layout.columns.booked_date,
        "booked_date",
        required_field_context,
    )
    booked_date = parse_date_value(
        booked_date_raw,
        day_first=layout.day_first_dates,
        label=booked_date_header,
    )
    value_date_resolved = _typed_value_and_header_from_aliases(typed_fields, lookup, layout.columns.value_date)
    value_date: date | None = None
    if value_date_resolved is not None:
        value_date_header, value_raw = value_date_resolved
        value_date = parse_date_value(value_raw, day_first=layout.day_first_dates, label=value_date_header)
    amount = parse_amount_value(
        _required_typed_value(typed_fields, lookup, layout.columns.amount, "amount", required_field_context),
        decimal_separator=layout.decimal_separator,
    )
    direction = _direction_from_aliases(raw_fields, lookup, layout.columns.direction)
    currency = _currency_from_aliases(
        raw_fields,
        lookup,
        layout.columns.currency,
        required_field_context,
    )
    description = _required_value(raw_fields, lookup, layout.columns.description, "description")
    counterparty = _value_from_aliases(raw_fields, lookup, layout.columns.counterparty)
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
    """Emit the ledger row for one parsed tabular bank-layout row.

    Shared post-parse tail for the CSV and spreadsheet providers. Delegates to
    :func:`build_raw_transaction` for the magnitude/provenance
    :class:`~domain.transactions.RawTransaction` and its sign-derived
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
    :func:`~core.parsing.normalise_iso_4217_currency`, shared with the OFX
    statement header and with the persisted
    :class:`~domain.transactions.RawTransaction`; only the column-naming
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
    except CoreValidationError as exc:
        raise FinancialValidationError(
            f"{context} currency column {header!r} must be a three-letter ISO 4217 code; got {raw!r}",
        ) from exc


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
    except ValueError as exc:
        expected = ", ".join(direction.value for direction in TransactionDirection)
        raise FinancialValidationError(f"unsupported direction value: {raw!r}; expected one of {expected}") from exc


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
