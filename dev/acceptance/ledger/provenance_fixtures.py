"""Synthetic import sources for the installed Ledger provenance matrix.

Each case names one supported (record kind, file format, importing frontend)
combination and writes its own synthetic source.  The expected stored
locator is computed here from the file's own layout, independently of the
product: delimited and workbook sources count physical rows with the header
as row 1, while OFX and N26 PDF statements have no row concept and store the
1-based ordinal of the transaction in the document.  Non-target filler rows
put the target at a position other than the first, so a hard-coded row
number cannot satisfy the check.
"""

from __future__ import annotations

import csv
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal

type RecordKind = Literal["transaction", "invoice"]
type ImportFrontend = Literal["cli", "tui"]
type LocatorKind = Literal["physical_row", "transaction_ordinal"]

_YEAR = 2025
_N26_HEADER = ("Date", "Payee", "Payment reference", "Amount (EUR)", "Currency", "Transaction ID")
_INVOICE_COLUMNS = (
    "counterparty_nif",
    "counterparty_name",
    "invoice_number",
    "invoice_date",
    "taxable_base",
    "iva_rate",
    "country_code",
    "notes",
)
_INVOICE_NIF = "B12345674"
_PDF_HEADER_LINE = "Beschreibung Verbuchungsdatum Betrag"


@dataclass(frozen=True, slots=True)
class StatementRow:
    """One synthetic bank movement."""

    day: int
    payee: str
    description: str
    amount: Decimal
    external_id: str


@dataclass(frozen=True, slots=True)
class InvoiceRow:
    """One synthetic invoice-book row."""

    day: int
    invoice_number: str
    taxable_base: Decimal
    notes: str

    def values(self) -> tuple[str, ...]:
        """Return the row in ``_INVOICE_COLUMNS`` order."""
        return (
            _INVOICE_NIF,
            "Synthetic supplier SL",
            self.invoice_number,
            f"{_YEAR}-03-{self.day:02d}",
            format(self.taxable_base, "f"),
            "21",
            "ES",
            self.notes,
        )


@dataclass(frozen=True, slots=True)
class ProvenanceCase:
    """One import combination and the locator its target record must display.

    ``provider`` is the statement provider token the importing frontend sends;
    invoice books have no provider selection.  ``target_key`` is the public
    description (transactions) or invoice number (invoices) used to find the
    record on every surface.
    """

    case_id: str
    record: RecordKind
    import_frontend: ImportFrontend
    file_format: str
    filename: str
    provider: str | None
    invoice_kind: Literal["received", "issued"] | None
    target_key: str
    locator: int
    locator_kind: LocatorKind
    row_count: int
    writer: Callable[[Path], None]

    def write(self, root: Path) -> Path:
        """Write this case's synthetic source under ``root`` and return its path."""
        path = root / self.filename
        if path.exists():
            raise FileExistsError(path.name)
        self.writer(path)
        return path

    def manifest_entry(self, path: Path) -> dict[str, object]:
        """Return the value-free coordinates a child process needs for this case."""
        return {
            "case_id": self.case_id,
            "record": self.record,
            "import_frontend": self.import_frontend,
            "path": str(path),
            "filename": self.filename,
            "provider": self.provider,
            "invoice_kind": self.invoice_kind,
            "target_key": self.target_key,
            "locator": self.locator,
        }

    def receipt_entry(self) -> dict[str, object]:
        """Return the sanitized per-case receipt fragment."""
        return {
            "case_id": self.case_id,
            "record": self.record,
            "import_frontend": self.import_frontend,
            "file_format": self.file_format,
            "filename": self.filename,
            "provider": self.provider,
            "invoice_kind": self.invoice_kind,
            "locator": self.locator,
            "locator_kind": self.locator_kind,
            "row_count": self.row_count,
        }


def _statement_rows(case_id: str, *, target_position: int, count: int, base: Decimal) -> tuple[StatementRow, ...]:
    """Build ``count`` unique movements with the target at ``target_position`` (1-based)."""
    rows = []
    for position in range(1, count + 1):
        is_target = position == target_position
        description = f"ledger-prov-{case_id}-target" if is_target else f"filler-{case_id}-{position}"
        rows.append(
            StatementRow(
                day=10 + position,
                payee=f"Ledger synthetic payee {case_id} {position}",
                description=description,
                amount=base + Decimal(position),
                external_id=f"{case_id}-{position}",
            )
        )
    return tuple(rows)


def _invoice_rows(case_id: str, *, target_position: int, count: int, base: Decimal) -> tuple[InvoiceRow, ...]:
    """Build ``count`` unique invoices with the target at ``target_position`` (1-based)."""
    return tuple(
        InvoiceRow(
            day=10 + position,
            invoice_number=f"PROV-{case_id}-T".upper()
            if position == target_position
            else f"FILL-{case_id}-{position}".upper(),
            taxable_base=base + Decimal(position),
            notes=f"ledger-prov-{case_id}-{position}",
        )
        for position in range(1, count + 1)
    )


def _statement_cells(row: StatementRow) -> tuple[str, ...]:
    return (
        f"{_YEAR}-03-{row.day:02d}",
        row.payee,
        row.description,
        format(row.amount, "f"),
        "EUR",
        row.external_id,
    )


def _write_delimited(path: Path, header: tuple[str, ...], rows: list[tuple[str, ...]], delimiter: str) -> None:
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream, delimiter=delimiter)
        writer.writerow(header)
        writer.writerows(rows)


def _write_workbook(path: Path, header: tuple[str, ...], rows: list[tuple[str, ...]]) -> None:
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    if sheet is None:
        raise RuntimeError("new workbook has no active worksheet")
    sheet.append(header)
    for row in rows:
        sheet.append(row)
    workbook.save(path)


def statement_delimited_writer(rows: tuple[StatementRow, ...]) -> Callable[[Path], None]:
    """Write an N26-layout CSV statement."""
    return lambda path: _write_delimited(path, _N26_HEADER, [_statement_cells(row) for row in rows], ",")


def statement_workbook_writer(rows: tuple[StatementRow, ...]) -> Callable[[Path], None]:
    """Write an N26-layout XLSX statement with the header on worksheet row 1."""
    return lambda path: _write_workbook(path, _N26_HEADER, [_statement_cells(row) for row in rows])


def _ofx_document(rows: tuple[StatementRow, ...]) -> str:
    transactions = "".join(
        "          <STMTTRN>\n"
        f"            <TRNTYPE>{'CREDIT' if row.amount > 0 else 'DEBIT'}\n"
        f"            <DTPOSTED>{_YEAR}03{row.day:02d}000000\n"
        f"            <TRNAMT>{format(row.amount, 'f')}\n"
        f"            <FITID>{row.external_id}\n"
        f"            <NAME>{row.payee}\n"
        f"            <MEMO>{row.description}\n"
        "          </STMTTRN>\n"
        for row in rows
    )
    return (
        "OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nSECURITY:NONE\nENCODING:USASCII\nCHARSET:1252\n"
        "COMPRESSION:NONE\nOLDFILEUID:NONE\nNEWFILEUID:NONE\n\n"
        "<OFX>\n  <SIGNONMSGSRSV1>\n    <SONRS>\n      <STATUS>\n        <CODE>0\n        <SEVERITY>INFO\n"
        f"      </STATUS>\n      <DTSERVER>{_YEAR}0331090000\n      <LANGUAGE>ENG\n    </SONRS>\n"
        "  </SIGNONMSGSRSV1>\n  <BANKMSGSRSV1>\n    <STMTTRNRS>\n      <TRNUID>1\n      <STATUS>\n"
        "        <CODE>0\n        <SEVERITY>INFO\n      </STATUS>\n      <STMTRS>\n        <CURDEF>EUR\n"
        "        <BANKACCTFROM>\n          <BANKID>0000\n          <ACCTID>SYNTHETIC-LEDGER\n"
        "          <ACCTTYPE>CHECKING\n        </BANKACCTFROM>\n        <BANKTRANLIST>\n"
        f"          <DTSTART>{_YEAR}0301000000\n          <DTEND>{_YEAR}0331235959\n"
        f"{transactions}"
        "        </BANKTRANLIST>\n        <LEDGERBAL>\n          <BALAMT>0.00\n"
        f"          <DTASOF>{_YEAR}0331235959\n        </LEDGERBAL>\n      </STMTRS>\n    </STMTTRNRS>\n"
        "  </BANKMSGSRSV1>\n</OFX>\n"
    )


def statement_ofx_writer(rows: tuple[StatementRow, ...]) -> Callable[[Path], None]:
    """Write a single-account OFX 1.02 SGML statement."""

    def write(path: Path) -> None:
        path.write_text(_ofx_document(rows), encoding="ascii", newline="\n")

    return write


def _n26_pdf_lines(rows: tuple[StatementRow, ...]) -> tuple[str, ...]:
    lines = [
        f"Kontoauszug Nr. 3/{_YEAR}",
        "N26 Bank SE",
        f"01.03.{_YEAR} bis 31.03.{_YEAR}",
        _PDF_HEADER_LINE,
    ]
    for row in rows:
        amount = format(row.amount, "f").replace(".", ",")
        sign = "+" if row.amount > 0 else ""
        lines.append(f"{row.payee} {row.day:02d}.03.{_YEAR} {sign}{amount}EUR")
        lines.append(row.description)
    return tuple(lines)


def statement_pdf_writer(rows: tuple[StatementRow, ...]) -> Callable[[Path], None]:
    """Write a one-page synthetic statement in the N26 text-line layout."""
    from cadrumo.tests.pdf_fixtures import text_pdf_bytes

    def write(path: Path) -> None:
        path.write_bytes(text_pdf_bytes(_n26_pdf_lines(rows)))

    return write


def invoice_delimited_writer(rows: tuple[InvoiceRow, ...], *, delimiter: str) -> Callable[[Path], None]:
    """Write a CSV or TSV invoice book."""
    return lambda path: _write_delimited(path, _INVOICE_COLUMNS, [row.values() for row in rows], delimiter)


def _write_legacy_workbook(path: Path, header: tuple[str, ...], rows: list[tuple[object, ...]]) -> None:
    from cadrumo.tests.xls_fixtures import xls_workbook_bytes

    path.write_bytes(xls_workbook_bytes([("Sheet1", [list(header), *(list(row) for row in rows)])]))


def statement_legacy_workbook_writer(rows: tuple[StatementRow, ...]) -> Callable[[Path], None]:
    """Write an N26-layout Excel 97-2003 statement with typed date and amount cells."""

    def cells(row: StatementRow) -> tuple[object, ...]:
        return (date(_YEAR, 3, row.day), row.payee, row.description, float(row.amount), "EUR", row.external_id)

    return lambda path: _write_legacy_workbook(path, _N26_HEADER, [cells(row) for row in rows])


def invoice_legacy_workbook_writer(rows: tuple[InvoiceRow, ...]) -> Callable[[Path], None]:
    """Write an Excel 97-2003 invoice book with the header on worksheet row 1."""
    return lambda path: _write_legacy_workbook(path, _INVOICE_COLUMNS, [row.values() for row in rows])


def invoice_workbook_writer(rows: tuple[InvoiceRow, ...]) -> Callable[[Path], None]:
    """Write an XLSX/XLSM invoice book with the header on worksheet row 1."""
    return lambda path: _write_workbook(path, _INVOICE_COLUMNS, [row.values() for row in rows])


def _statement_case(
    case_id: str,
    *,
    frontend: ImportFrontend,
    file_format: str,
    provider: str,
    target_position: int,
    count: int,
    base: str,
) -> ProvenanceCase:
    rows = _statement_rows(case_id, target_position=target_position, count=count, base=Decimal(base))
    if file_format in {"csv", "txt"}:
        writer, locator_kind, locator = statement_delimited_writer(rows), "physical_row", target_position + 1
    elif file_format == "xlsx":
        writer, locator_kind, locator = statement_workbook_writer(rows), "physical_row", target_position + 1
    elif file_format == "xls":
        writer, locator_kind, locator = statement_legacy_workbook_writer(rows), "physical_row", target_position + 1
    elif file_format in {"ofx", "qfx"}:
        writer, locator_kind, locator = statement_ofx_writer(rows), "transaction_ordinal", target_position
    elif file_format == "pdf":
        writer, locator_kind, locator = statement_pdf_writer(rows), "transaction_ordinal", target_position
    else:
        raise ValueError(f"unsupported synthetic statement format {file_format}")
    return ProvenanceCase(
        case_id=case_id,
        record="transaction",
        import_frontend=frontend,
        file_format=file_format,
        filename=f"ledger-prov-{case_id}.{file_format}",
        provider=provider,
        invoice_kind=None,
        target_key=f"ledger-prov-{case_id}-target",
        locator=locator,
        locator_kind=locator_kind,
        row_count=count,
        writer=writer,
    )


def _invoice_case(
    case_id: str,
    *,
    frontend: ImportFrontend,
    file_format: str,
    invoice_kind: Literal["received", "issued"],
    target_position: int,
    count: int,
    base: str,
) -> ProvenanceCase:
    rows = _invoice_rows(case_id, target_position=target_position, count=count, base=Decimal(base))
    if file_format == "csv":
        writer = invoice_delimited_writer(rows, delimiter=",")
    elif file_format == "tsv":
        writer = invoice_delimited_writer(rows, delimiter="\t")
    elif file_format in {"xlsx", "xlsm"}:
        writer = invoice_workbook_writer(rows)
    elif file_format == "xls":
        writer = invoice_legacy_workbook_writer(rows)
    else:
        raise ValueError(f"unsupported synthetic invoice-book format {file_format}")
    return ProvenanceCase(
        case_id=case_id,
        record="invoice",
        import_frontend=frontend,
        file_format=file_format,
        filename=f"ledger-prov-{case_id}.{file_format}",
        provider=None,
        invoice_kind=invoice_kind,
        target_key=rows[target_position - 1].invoice_number,
        locator=target_position + 1,
        locator_kind="physical_row",
        row_count=count,
        writer=writer,
    )


def provenance_cases() -> tuple[ProvenanceCase, ...]:
    """Return every supported import combination the installed matrix proves.

    CLI statements use explicit provider tokens except ``auto``, which covers
    detection for the ``.txt``, ``.qfx`` and legacy ``.xls`` files.  The TUI
    exposes ``auto``, ``csv``, ``ofx``, ``xlsx`` and ``pdf-n26``; invoice books
    take no provider in either frontend.
    """
    return (
        _statement_case(
            "cli-csv", frontend="cli", file_format="csv", provider="csv", target_position=2, count=2, base="10.00"
        ),
        _statement_case(
            "cli-txt", frontend="cli", file_format="txt", provider="auto", target_position=1, count=1, base="20.00"
        ),
        _statement_case(
            "cli-xlsx", frontend="cli", file_format="xlsx", provider="xlsx", target_position=3, count=3, base="30.00"
        ),
        _statement_case(
            "cli-ofx", frontend="cli", file_format="ofx", provider="ofx", target_position=3, count=3, base="40.00"
        ),
        _statement_case(
            "cli-qfx", frontend="cli", file_format="qfx", provider="auto", target_position=1, count=1, base="50.00"
        ),
        _statement_case(
            "cli-pdf", frontend="cli", file_format="pdf", provider="pdf-n26", target_position=2, count=2, base="-60.00"
        ),
        _statement_case(
            "cli-xls", frontend="cli", file_format="xls", provider="auto", target_position=2, count=3, base="55.00"
        ),
        _invoice_case(
            "cli-inv-csv",
            frontend="cli",
            file_format="csv",
            invoice_kind="received",
            target_position=1,
            count=1,
            base="100.00",
        ),
        _invoice_case(
            "cli-inv-tsv",
            frontend="cli",
            file_format="tsv",
            invoice_kind="received",
            target_position=2,
            count=2,
            base="110.00",
        ),
        _invoice_case(
            "cli-inv-xlsx",
            frontend="cli",
            file_format="xlsx",
            invoice_kind="issued",
            target_position=3,
            count=3,
            base="120.00",
        ),
        _invoice_case(
            "cli-inv-xlsm",
            frontend="cli",
            file_format="xlsm",
            invoice_kind="received",
            target_position=1,
            count=1,
            base="130.00",
        ),
        _invoice_case(
            "cli-inv-xls",
            frontend="cli",
            file_format="xls",
            invoice_kind="received",
            target_position=2,
            count=3,
            base="135.00",
        ),
        _statement_case(
            "tui-csv", frontend="tui", file_format="csv", provider="csv", target_position=1, count=2, base="70.00"
        ),
        _statement_case(
            "tui-xlsx", frontend="tui", file_format="xlsx", provider="xlsx", target_position=2, count=2, base="80.00"
        ),
        _statement_case(
            "tui-ofx", frontend="tui", file_format="ofx", provider="ofx", target_position=2, count=2, base="90.00"
        ),
        _statement_case(
            "tui-qfx", frontend="tui", file_format="qfx", provider="auto", target_position=1, count=1, base="95.00"
        ),
        _statement_case(
            "tui-pdf", frontend="tui", file_format="pdf", provider="pdf-n26", target_position=3, count=3, base="-66.00"
        ),
        _statement_case(
            "tui-xls", frontend="tui", file_format="xls", provider="auto", target_position=3, count=3, base="97.00"
        ),
        _invoice_case(
            "tui-inv-csv",
            frontend="tui",
            file_format="csv",
            invoice_kind="issued",
            target_position=2,
            count=2,
            base="140.00",
        ),
        _invoice_case(
            "tui-inv-tsv",
            frontend="tui",
            file_format="tsv",
            invoice_kind="received",
            target_position=1,
            count=1,
            base="150.00",
        ),
        _invoice_case(
            "tui-inv-xlsx",
            frontend="tui",
            file_format="xlsx",
            invoice_kind="received",
            target_position=2,
            count=2,
            base="160.00",
        ),
        _invoice_case(
            "tui-inv-xlsm",
            frontend="tui",
            file_format="xlsm",
            invoice_kind="issued",
            target_position=1,
            count=1,
            base="170.00",
        ),
        _invoice_case(
            "tui-inv-xls",
            frontend="tui",
            file_format="xls",
            invoice_kind="issued",
            target_position=1,
            count=2,
            base="175.00",
        ),
    )


__all__ = [
    "ImportFrontend",
    "InvoiceRow",
    "LocatorKind",
    "ProvenanceCase",
    "RecordKind",
    "StatementRow",
    "provenance_cases",
]
