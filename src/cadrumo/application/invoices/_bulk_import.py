"""Bulk CSV/XLSX transport for creating catalogue :class:`Invoice` records.

The accountant/gestor batch case: a spreadsheet of invoice rows (counterparty
NIF, invoice number, date, taxable base, IVA rate) is turned into one
:class:`~domain.invoices.Invoice` per row. This module is a typed transport
over :func:`~application.invoices.create_catalogue_invoice` -- the sole
sanctioned :class:`Invoice` writer (``composition-service-no-parallel-write-path``);
it never persists a row itself.

Each row's identity is the same content-derived
:attr:`~domain.invoices.Invoice.invoice_id` hash the single-invoice
``catalogue create`` verb and the evidence-confirm slice use, so a re-import of
an unchanged file is a guarded no-op per row
(``single-subject-mutation-is-idempotent-guarded``): an already-catalogued
identical row is reported ``skipped_duplicate``, never re-written and never
raised as an error. A malformed row (missing required field, invalid NIF,
unsupported IVA rate) is collected as a ``refused`` row carrying its 1-based
CSV row number and the failing field, and the remaining valid rows are still
applied -- partial-success semantics matching the ledger CSV import and bulk
classify pattern (``no-silent-under-declaration``: a bad row is reported, never
silently dropped).

See Also:
    :func:`~application.invoices.import_invoices_from_rows`
        Public application facade for applying validated bulk rows.
    :func:`~application.invoices.create_catalogue_invoice`
        Single catalogue writer invoked for every accepted row.
    :func:`~application.invoices.create_invoice_via_wizard`
        Manual single-invoice path with the same writer and idempotent identity.
    :func:`~application.ledger.confirm_invoice_draft_from_evidence`
        Evidence-confirm path that also delegates the final invoice write to
        the catalogue writer.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator, Mapping, Sequence
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from ...adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ...core import STRICT_FROZEN_CONFIG
from ...core.external_constants import DEFAULT_CURRENCY
from ...core.parsing import parse_iso8601_date
from ...domain.invoices import InvoiceCatalogueRepositoryProtocol, InvoiceValidationError
from ...domain.iva import InvoiceKind
from ._creation import build_catalogue_invoice, create_catalogue_invoice

__all__ = [
    "BULK_INVOICE_IMPORT_ALLOWED_COLUMNS",
    "BULK_INVOICE_IMPORT_REQUIRED_COLUMNS",
    "BulkInvoiceImportResult",
    "BulkInvoiceImportRow",
    "BulkInvoiceImportRowFailure",
    "import_invoices_from_rows",
    "read_bulk_invoice_import_rows",
]

BULK_INVOICE_IMPORT_REQUIRED_COLUMNS: frozenset[str] = frozenset(
    {
        "counterparty_nif",
        "counterparty_name",
        "invoice_number",
        "invoice_date",
        "taxable_base",
    },
)

BULK_INVOICE_IMPORT_OPTIONAL_COLUMNS: frozenset[str] = frozenset(
    {
        "iva_rate",
        "currency",
        "country_code",
        "notes",
    },
)

BULK_INVOICE_IMPORT_ALLOWED_COLUMNS: frozenset[str] = (
    BULK_INVOICE_IMPORT_REQUIRED_COLUMNS | BULK_INVOICE_IMPORT_OPTIONAL_COLUMNS
)


class BulkInvoiceImportRow(BaseModel):
    """One parsed row from a bulk invoice import CSV/XLSX file.

    Mirrors the operator fields ``aeat app ledger invoice catalogue create``
    accepts one at a time; ``taxable_base`` and ``iva_rate`` synthesise the
    single line item exactly as :func:`build_catalogue_invoice` does for the
    single-invoice verb, so a bulk row produces an identical
    :class:`~domain.invoices.Invoice` shape.
    """

    model_config = STRICT_FROZEN_CONFIG

    counterparty_nif: str = Field(min_length=1)
    counterparty_name: str = Field(min_length=1)
    invoice_number: str = Field(min_length=1)
    invoice_date: date
    taxable_base: Decimal
    iva_rate: Decimal | None = None
    currency: str = DEFAULT_CURRENCY
    country_code: str = "ES"
    notes: str = ""


class BulkInvoiceImportRowFailure(BaseModel):
    """One row that could not be parsed or persisted during a bulk import."""

    model_config = STRICT_FROZEN_CONFIG

    row_number: int = Field(ge=1)
    field: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class BulkInvoiceImportResult(BaseModel):
    """Aggregate outcome of one bulk invoice import run.

    Uses the same partial-success semantics as the ledger CSV import and bulk
    classify surfaces: every parseable, non-duplicate row is created; rows that
    fail validation are collected in ``refused``; rows whose derived
    ``invoice_id`` already exists in the catalogue are counted in
    ``skipped_duplicate`` (the idempotent-guarded re-import no-op) rather than
    raised as an error.
    """

    model_config = STRICT_FROZEN_CONFIG

    rows: int = Field(ge=0)
    created: int = Field(ge=0)
    skipped_duplicate: int = Field(ge=0)
    refused: tuple[BulkInvoiceImportRowFailure, ...] = ()
    created_invoice_ids: tuple[str, ...] = ()


def _cell_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _parse_row_date(raw: str, *, row_number: int, field: str) -> date:
    try:
        value = parse_iso8601_date(raw)
    except ValueError as exc:
        raise _RowParseError(row_number=row_number, field=field, reason=f"invalid ISO-8601 date: {raw!r}") from exc
    if value is None:
        raise _RowParseError(row_number=row_number, field=field, reason=f"invalid ISO-8601 date: {raw!r}")
    return value


def _parse_row_decimal(raw: str, *, row_number: int, field: str) -> Decimal:
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise _RowParseError(row_number=row_number, field=field, reason=f"invalid decimal amount: {raw!r}") from exc
    if not value.is_finite():
        raise _RowParseError(row_number=row_number, field=field, reason=f"invalid decimal amount: {raw!r}")
    return value


class _RowParseError(Exception):
    """Internal control-flow exception carrying one row's failure detail."""

    def __init__(self, *, row_number: int, field: str, reason: str) -> None:
        super().__init__(reason)
        self.row_number = row_number
        self.field = field
        self.reason = reason


def _parse_bulk_invoice_row(raw_row: Mapping[str, object], *, row_number: int) -> BulkInvoiceImportRow:
    """Return a validated :class:`BulkInvoiceImportRow`, or raise :class:`_RowParseError`.

    Every field failure is attributed to its originating column name so a
    refusal names both the row number and the field that failed
    (``no-silent-under-declaration``) rather than a bare "row invalid".
    """
    missing = [column for column in BULK_INVOICE_IMPORT_REQUIRED_COLUMNS if not _cell_text(raw_row.get(column))]
    if missing:
        raise _RowParseError(row_number=row_number, field=missing[0], reason="required field is missing or blank")

    invoice_date_raw = _cell_text(raw_row.get("invoice_date"))
    invoice_date = _parse_row_date(invoice_date_raw, row_number=row_number, field="invoice_date")

    taxable_base_raw = _cell_text(raw_row.get("taxable_base"))
    taxable_base = _parse_row_decimal(taxable_base_raw, row_number=row_number, field="taxable_base")

    iva_rate_raw = _cell_text(raw_row.get("iva_rate"))
    iva_rate = _parse_row_decimal(iva_rate_raw, row_number=row_number, field="iva_rate") if iva_rate_raw else None

    currency_raw = _cell_text(raw_row.get("currency")) or DEFAULT_CURRENCY
    country_code_raw = _cell_text(raw_row.get("country_code")) or "ES"

    try:
        return BulkInvoiceImportRow(
            counterparty_nif=_cell_text(raw_row.get("counterparty_nif")),
            counterparty_name=_cell_text(raw_row.get("counterparty_name")),
            invoice_number=_cell_text(raw_row.get("invoice_number")),
            invoice_date=invoice_date,
            taxable_base=taxable_base,
            iva_rate=iva_rate,
            currency=currency_raw,
            country_code=country_code_raw,
            notes=_cell_text(raw_row.get("notes")),
        )
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {"loc": ("row",), "msg": "invalid row"}
        field = str(first["loc"][0]) if first.get("loc") else "row"
        raise _RowParseError(row_number=row_number, field=field, reason=str(first.get("msg", "invalid row"))) from exc


def _read_csv_rows(text: str) -> Iterator[tuple[int, Mapping[str, object]]]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return
    unknown = frozenset(reader.fieldnames) - BULK_INVOICE_IMPORT_ALLOWED_COLUMNS
    if unknown:
        raise InvoiceValidationError(
            "bulk invoice import CSV contains unknown columns",
            translated_message="application.invoices.bulk_import.errors.unknown_columns",
            context={"unknown_columns": ", ".join(sorted(unknown))},
        )
    missing_required = BULK_INVOICE_IMPORT_REQUIRED_COLUMNS - frozenset(reader.fieldnames)
    if missing_required:
        raise InvoiceValidationError(
            "bulk invoice import CSV is missing required columns",
            translated_message="application.invoices.bulk_import.errors.missing_columns",
            context={"missing_columns": ", ".join(sorted(missing_required))},
        )
    for row_number, raw_row in enumerate(reader, start=2):  # header is row 1
        yield row_number, dict(raw_row)


def _read_xlsx_rows(path: Path) -> Iterator[tuple[int, Mapping[str, object]]]:
    from openpyxl import load_workbook

    workbook = load_workbook(filename=path, read_only=True, data_only=True)
    try:
        worksheet = workbook.worksheets[0]
        rows_iter = worksheet.iter_rows(values_only=True)
        try:
            header_row = next(rows_iter)
        except StopIteration:
            return
        headers = [_cell_text(cell) for cell in header_row]
        unknown = frozenset(headers) - BULK_INVOICE_IMPORT_ALLOWED_COLUMNS
        if unknown:
            raise InvoiceValidationError(
                "bulk invoice import workbook contains unknown columns",
                translated_message="application.invoices.bulk_import.errors.unknown_columns",
                context={"unknown_columns": ", ".join(sorted(unknown))},
            )
        missing_required = BULK_INVOICE_IMPORT_REQUIRED_COLUMNS - frozenset(headers)
        if missing_required:
            raise InvoiceValidationError(
                "bulk invoice import workbook is missing required columns",
                translated_message="application.invoices.bulk_import.errors.missing_columns",
                context={"missing_columns": ", ".join(sorted(missing_required))},
            )
        for row_number, row in enumerate(rows_iter, start=2):  # header is row 1
            if not any(cell is not None and str(cell).strip() for cell in row):
                continue
            raw_row: dict[str, object] = {}
            for index, header in enumerate(headers):
                if not header:
                    continue
                cell = row[index] if index < len(row) else None
                raw_row[header] = cell.isoformat() if isinstance(cell, date) else cell
            yield row_number, raw_row
    finally:
        workbook.close()


def read_bulk_invoice_import_rows(path: Path) -> Iterator[tuple[int, Mapping[str, object]]]:
    """Yield ``(row_number, raw_row)`` pairs from a CSV or XLSX bulk-import file.

    ``row_number`` is 1-based against the file's own rows (the header is row
    1), so a refusal names exactly the row an operator would count by opening
    the file in a spreadsheet application.

    Raises:
        InvoiceValidationError: When the file extension is unsupported, or the
            header carries unknown columns or omits a required column.
    """
    suffix = path.suffix.lower()
    if suffix == ".csv":
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            raise InvoiceValidationError(
                "bulk invoice import file could not be read",
                translated_message="application.invoices.bulk_import.errors.file_read_failed",
                context={"path_name": path.name, "error_type": type(exc).__name__},
            ) from exc
        yield from _read_csv_rows(text)
        return
    if suffix in {".xlsx", ".xlsm"}:
        yield from _read_xlsx_rows(path)
        return
    raise InvoiceValidationError(
        "bulk invoice import file must be .csv or .xlsx",
        translated_message="application.invoices.bulk_import.errors.unsupported_extension",
        context={"path_name": path.name, "extension": suffix},
    )


def import_invoices_from_rows(
    rows: Sequence[tuple[int, Mapping[str, object]]],
    *,
    bucket_id: str,
    kind: InvoiceKind,
    repository: InvoiceCatalogueRepositoryProtocol | None = None,
) -> BulkInvoiceImportResult:
    """Create one catalogue :class:`Invoice` per valid row in *rows*.

    Every accepted row is handed to
    :func:`~application.invoices.create_catalogue_invoice` -- this
    function never persists a row itself
    (``composition-service-no-parallel-write-path``). Because
    :class:`~domain.invoices.Invoice` identity is a content-derived hash of
    ``(kind, invoice_number, issued_at, counterparty_tax_id, currency,
    grand_total)``, re-importing the identical file a second time resolves
    every row to its already-catalogued ``invoice_id`` and reports it in
    ``skipped_duplicate`` -- no second write, no raised error
    (``single-subject-mutation-is-idempotent-guarded``). A row whose resolved
    fields genuinely differ (a corrected amount, a new invoice number) mints a
    distinct record rather than overwriting one filer's data with another's.

    A malformed row (missing/blank required field, invalid date, unsupported
    IVA rate percentage, invalid NIF) is collected in ``refused`` with its row
    number and the failing field name; the remaining valid rows still import
    (partial-success semantics).
    """
    repo = repository or InvoiceCatalogueRepository(bucket_id=bucket_id)
    catalogue = repo.load()
    existing_ids = set(catalogue.invoices)

    refused: list[BulkInvoiceImportRowFailure] = []
    created = 0
    skipped_duplicate = 0
    created_ids: list[str] = []

    for row_number, raw_row in rows:
        try:
            parsed = _parse_bulk_invoice_row(raw_row, row_number=row_number)
        except _RowParseError as exc:
            refused.append(BulkInvoiceImportRowFailure(row_number=exc.row_number, field=exc.field, reason=exc.reason))
            continue

        try:
            candidate = build_catalogue_invoice(
                bucket_id=bucket_id,
                kind=kind,
                counterparty_name=parsed.counterparty_name,
                counterparty_tax_id=parsed.counterparty_nif,
                counterparty_country=parsed.country_code,
                invoice_number=parsed.invoice_number,
                issued_at=parsed.invoice_date,
                taxable_base=parsed.taxable_base,
                iva_rate=parsed.iva_rate,
                currency=parsed.currency,
                notes=parsed.notes,
            )
        except (InvoiceValidationError, ValidationError) as exc:
            reason = str(exc.errors()[0].get("msg", str(exc))) if isinstance(exc, ValidationError) else str(exc)
            refused.append(BulkInvoiceImportRowFailure(row_number=row_number, field="invoice", reason=reason))
            continue

        if candidate.invoice_id in existing_ids:
            # Guarded idempotent retry (single-subject-mutation-is-idempotent-guarded):
            # a re-import of the same file resolves every row to an
            # already-catalogued identity -- report it, do not re-write or raise.
            skipped_duplicate += 1
            continue

        result = create_catalogue_invoice(
            bucket_id=bucket_id,
            kind=kind,
            counterparty_name=parsed.counterparty_name,
            counterparty_tax_id=parsed.counterparty_nif,
            counterparty_country=parsed.country_code,
            invoice_number=parsed.invoice_number,
            issued_at=parsed.invoice_date,
            taxable_base=parsed.taxable_base,
            iva_rate=parsed.iva_rate,
            currency=parsed.currency,
            notes=parsed.notes,
            repository=repo,
        )
        existing_ids.add(result.invoice.invoice_id)
        created_ids.append(result.invoice.invoice_id)
        created += 1

    return BulkInvoiceImportResult(
        rows=len(rows),
        created=created,
        skipped_duplicate=skipped_duplicate,
        refused=tuple(refused),
        created_invoice_ids=tuple(created_ids),
    )
