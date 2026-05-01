"""CSV financial provider with bank-layout-aware parsing."""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .....core.config import load_settings
from .._raw_transaction import RawTransaction, SourceFormat
from ._base import (
    FinancialProvider,
    InvalidFinancialSourceError,
    ProviderValidation,
    build_raw_transaction,
    coerce_cell_text,
    default_currency,
    describe_dialect,
    normalize_header,
    parse_amount_value,
    parse_date_value,
    synthesize_transaction_id,
)

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")


class CsvColumnMap(BaseModel):
    """Alias sets for one bank CSV layout."""

    model_config = _STRICT_FROZEN

    booked_date: tuple[str, ...]
    value_date: tuple[str, ...] = ()
    amount: tuple[str, ...]
    currency: tuple[str, ...] = ()
    description: tuple[str, ...]
    counterparty: tuple[str, ...] = ()
    external_id: tuple[str, ...] = ()


class CsvBankLayout(BaseModel):
    """Named bank CSV layout supported by the provider."""

    model_config = _STRICT_FROZEN

    bank_name: str = Field(min_length=1)
    columns: CsvColumnMap
    day_first_dates: bool = True
    decimal_separator: Literal[",", "."] = ","


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
    decimal_separator=".",
)
CSV_LAYOUTS: tuple[CsvBankLayout, ...] = (
    BBVA_LAYOUT,
    SANTANDER_LAYOUT,
    CAIXABANK_LAYOUT,
    REVOLUT_LAYOUT,
)


class CsvProvider(FinancialProvider):
    """Ingest raw transactions from bank CSV exports."""

    name = "CSV provider"
    supported_extensions = frozenset({".csv", ".txt"})
    source_format = SourceFormat.CSV

    def validate_source(self, path: Path) -> ProviderValidation:
        """Validate CSV structure, encoding, and layout support."""
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
        if not _find_column(_header_lookup(rows[header_index]), layout.columns.currency):
            warnings.append(
                f"{layout.bank_name} CSV has no currency column; falling back to {default_currency()}",
            )
        return ProviderValidation(
            is_valid=True,
            warnings=tuple(warnings),
            detected_encoding=encoding,
            detected_dialect=describe_dialect(dialect),
        )

    def ingest(self, path: Path) -> Iterator[RawTransaction]:
        """Yield strict raw transactions from the CSV source."""
        rows, source_sha256, _, _ = self._load_rows(path)
        header_index, layout, headers, lookup = self._locate_header(rows)
        if layout is None or headers is None or lookup is None:
            raise InvalidFinancialSourceError("CSV headers do not match any supported bank layout")
        data_rows = rows[header_index + 1 :]
        for source_row_index, row in enumerate(data_rows, start=header_index + 2):
            raw_fields = _row_to_mapping(headers, row)
            if _row_is_blank(raw_fields):
                continue
            try:
                transaction_id = _value_from_aliases(raw_fields, lookup, layout.columns.external_id)
                if not transaction_id:
                    transaction_id = synthesize_transaction_id(
                        provider_name=layout.bank_name,
                        source_sha256=source_sha256,
                        source_row_index=source_row_index,
                    )
                booked_date = parse_date_value(
                    _required_value(raw_fields, lookup, layout.columns.booked_date, "booked_date"),
                    day_first=layout.day_first_dates,
                )
                value_text = _value_from_aliases(raw_fields, lookup, layout.columns.value_date)
                value_date = parse_date_value(value_text, day_first=layout.day_first_dates) if value_text else None
                amount = parse_amount_value(
                    _required_value(raw_fields, lookup, layout.columns.amount, "amount"),
                    decimal_separator=layout.decimal_separator,
                )
                currency = _value_from_aliases(raw_fields, lookup, layout.columns.currency) or default_currency()
                description = _required_value(raw_fields, lookup, layout.columns.description, "description")
                counterparty = _value_from_aliases(raw_fields, lookup, layout.columns.counterparty)
            except ValueError as exc:
                raise InvalidFinancialSourceError(
                    f"CSV row {source_row_index} could not be parsed: {exc}",
                ) from exc
            yield build_raw_transaction(
                provider=self,
                path=path,
                source_sha256=source_sha256,
                source_row_index=source_row_index,
                transaction_id=transaction_id,
                booked_date=booked_date,
                value_date=value_date,
                amount=amount,
                currency=currency,
                counterparty=counterparty,
                description=description,
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
        """Decode bytes using the configured preference order."""
        preferred = load_settings().financial_default_csv_encoding.strip() or "utf-8"
        candidates = (preferred, "utf-8-sig", "utf-8", "cp1252", "iso-8859-1")
        seen: set[str] = set()
        for candidate in candidates:
            normalized = candidate.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            try:
                return source_bytes.decode(candidate), candidate
            except LookupError:
                continue
            except UnicodeDecodeError:
                continue
        raise InvalidFinancialSourceError("CSV source could not be decoded as utf-8/cp1252/iso-8859-1")

    def _sniff_dialect(self, text: str) -> type[csv.Dialect]:
        """Detect the CSV delimiter and quoting rules."""
        sample = "\n".join(line for line in text.splitlines() if line.strip())[:4096]
        try:
            return csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            return csv.excel

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
            lookup = _header_lookup(row)
            for layout in CSV_LAYOUTS:
                score = _layout_score(lookup, layout)
                if score > best_score:
                    best_index = index
                    best_layout = layout
                    best_headers = row
                    best_lookup = lookup
                    best_score = score
        if best_score < 3:
            return 0, None, None, None
        return best_index, best_layout, best_headers, best_lookup


def _header_lookup(headers: list[str]) -> dict[str, str]:
    """Build normalized->original header lookup for alias resolution."""
    return {normalize_header(header): header for header in headers if header.strip()}


def _layout_score(lookup: Mapping[str, str], layout: CsvBankLayout) -> int:
    """Return a match score for one layout against one header row."""
    required = (
        _find_column(lookup, layout.columns.booked_date),
        _find_column(lookup, layout.columns.amount),
        _find_column(lookup, layout.columns.description),
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
        if aliases and _find_column(lookup, aliases):
            score += 1
    return score


def _find_column(lookup: Mapping[str, str], aliases: tuple[str, ...]) -> str | None:
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


def _row_is_blank(raw_fields: Mapping[str, str]) -> bool:
    """Return whether a parsed source row carries no usable values."""
    return not any(value.strip() for value in raw_fields.values())


def _value_from_aliases(
    raw_fields: Mapping[str, str],
    lookup: Mapping[str, str],
    aliases: tuple[str, ...],
) -> str | None:
    """Resolve and read the first non-empty value for a logical column."""
    header = _find_column(lookup, aliases)
    if header is None:
        return None
    value = raw_fields.get(header, "")
    normalized = coerce_cell_text(value)
    return normalized or None


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
