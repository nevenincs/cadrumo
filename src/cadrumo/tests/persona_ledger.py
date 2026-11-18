"""Parse a persona's ledger rows and the documents its rows name."""

from __future__ import annotations

import csv
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

from .inventory import REPO_ROOT
from .persona_identities import _Roles
from .persona_toml import _amount, _choice, _keys, _optional_string, _string, _strings, _Table, _tables
from .persona_types import DocumentGenerator, LedgerRow, PersonaDocument, YearToken, _fail

LEDGER_COLUMNS: tuple[str, ...] = (
    "ref",
    "year",
    "month",
    "day",
    "description",
    "amount",
    "currency",
    "counterparty",
    "classification",
    "category_id",
    "irpf_category",
    "iva_category",
    "taxable_base",
    "iva_rate",
    "iva_amount",
    "recargo_amount",
    "deduction_kind",
    "invoice_kind",
    "invoice_number",
    "retencion_rate",
    "retencion_amount",
    "document",
)
"""The ``ledger.csv`` header, in order."""


LEDGER_ACCRUAL_COLUMNS: tuple[str, ...] = ("accrual_year", "accrual_month", "accrual_day")
"""Optional trailing ``ledger.csv`` columns: a row's accrual date, stated where the devengo criterion needs it."""


def _cell(row: Mapping[str, str], column: str) -> str | None:
    return row[column] or None


def _cell_amount(row: Mapping[str, str], column: str, where: str) -> Decimal | None:
    text = _cell(row, column)
    return None if text is None else _amount(text, f"{where}.{column}")


def _ledger_row(row: Mapping[str, str], where: str, roles: _Roles) -> LedgerRow:
    month, day = int(row["month"]), int(row["day"])
    counterparty = _cell(row, "counterparty")
    invoice_kind = _cell(row, "invoice_kind")
    ledger_row = LedgerRow(
        ref=row["ref"],
        year=YearToken.parse(row["year"], where=f"{where}.year"),
        month=month,
        day=day,
        description=row["description"],
        amount=_amount(row["amount"], f"{where}.amount"),
        currency=row["currency"],
        counterparty=None if counterparty is None else roles(counterparty, where),
        classification=_choice(row["classification"], ("BUSINESS", "PERSONAL"), where),
        category_id=_cell(row, "category_id"),
        irpf_category=_cell(row, "irpf_category"),
        iva_category=_cell(row, "iva_category"),
        taxable_base=_cell_amount(row, "taxable_base", where),
        iva_rate=_cell_amount(row, "iva_rate", where),
        iva_amount=_cell_amount(row, "iva_amount", where),
        recargo_amount=_cell_amount(row, "recargo_amount", where),
        deduction_kind=_cell(row, "deduction_kind"),
        invoice_kind=None if invoice_kind is None else _choice(invoice_kind, ("issued", "received"), where),
        invoice_number=_cell(row, "invoice_number"),
        retencion_rate=_cell_amount(row, "retencion_rate", where),
        retencion_amount=_cell_amount(row, "retencion_amount", where),
        document=_cell(row, "document"),
        accrual=_accrual(row, where),
    )
    if not 1 <= month <= 12 or not 1 <= day <= 31:
        raise _fail(where, "month or day out of range")
    if not ledger_row.ref or not ledger_row.description or ledger_row.currency != "EUR":
        raise _fail(where, "a row needs a ref, a description and EUR")
    _check_invoice_arithmetic(ledger_row, where)
    return ledger_row


def _accrual(row: Mapping[str, str], where: str) -> tuple[YearToken, int, int] | None:
    cells = [row.get(column) or None for column in LEDGER_ACCRUAL_COLUMNS]
    if all(cell is None for cell in cells):
        return None
    year, month, day = cells
    if year is None or month is None or day is None:
        raise _fail(where, "an accrual date states its year, month and day")
    accrual = (YearToken.parse(year, where=f"{where}.accrual_year"), int(month), int(day))
    if not 1 <= accrual[1] <= 12 or not 1 <= accrual[2] <= 31:
        raise _fail(where, "accrual month or day out of range")
    return accrual


def _check_invoice_arithmetic(row: LedgerRow, where: str) -> None:
    """``|amount| = base + iva + recargo - retencion``, with IVA left out under reverse charge."""
    if row.taxable_base is None:
        return
    iva = Decimal(0) if row.reverse_charge or row.iva_amount is None else row.iva_amount
    total = row.taxable_base + iva + (row.recargo_amount or 0) - (row.retencion_amount or 0)
    if abs(row.amount) != total:
        raise _fail(where, f"amount {row.amount} differs from its invoice figures {total}")


def _parse_ledger(text: str, *, where: str, roles: _Roles) -> tuple[LedgerRow, ...]:
    """Parse ``ledger.csv`` text; a header other than :data:`LEDGER_COLUMNS`, optionally followed by
    :data:`LEDGER_ACCRUAL_COLUMNS`, is refused."""
    reader = csv.DictReader(text.splitlines())
    if tuple(reader.fieldnames or ()) not in (LEDGER_COLUMNS, LEDGER_COLUMNS + LEDGER_ACCRUAL_COLUMNS):
        raise _fail(
            where, f"header must be {','.join(LEDGER_COLUMNS)}, optionally with {','.join(LEDGER_ACCRUAL_COLUMNS)}"
        )
    rows = tuple(_ledger_row(row, f"{where}:{index + 2}", roles) for index, row in enumerate(reader))
    refs = [row.ref for row in rows]
    if len(set(refs)) != len(refs):
        raise _fail(where, "a ledger ref is repeated")
    return rows


def _documents(document: _Table, where: str, persona_id: str, refs: frozenset[str]) -> tuple[PersonaDocument, ...]:
    _keys(document, where, required=frozenset({"format", "persona", "documents"}))
    if document["persona"] != persona_id:
        raise _fail(where, "persona differs from its directory")
    documents: list[PersonaDocument] = []
    for index, table in enumerate(_tables(document["documents"], where)):
        here = f"{where} documents[{index}]"
        _keys(
            table,
            here,
            required=frozenset({"id", "media_type", "attach_to", "relation"}),
            optional=frozenset({"note", "path", "generator"}),
        )
        if ("path" in table) == ("generator" in table):
            raise _fail(here, "a document names exactly one of path and generator")
        path: Path | None = None
        generator: DocumentGenerator | None = None
        attach_to = _strings(table, "attach_to", here)
        if "path" in table:
            path = REPO_ROOT / _string(table, "path", here)
            if not path.is_file():
                raise _fail(here, "the referenced specimen does not exist")
        else:
            generator = _choice(_string(table, "generator", here), ("facturae",), here)
            if len(attach_to) != 1:
                raise _fail(here, "a generated document is the invoice of exactly one row")
        if not set(attach_to) <= refs:
            raise _fail(here, "attach_to names a ref the ledger does not hold")
        documents.append(
            PersonaDocument(
                id=_string(table, "id", here),
                path=path,
                generator=generator,
                media_type=_string(table, "media_type", here),
                attach_to=attach_to,
                relation=_choice(_string(table, "relation", here), ("specimen", "source"), here),
                note=_optional_string(table, "note", here),
            )
        )
    return tuple(documents)


__all__ = [
    "LEDGER_ACCRUAL_COLUMNS",
    "LEDGER_COLUMNS",
]
