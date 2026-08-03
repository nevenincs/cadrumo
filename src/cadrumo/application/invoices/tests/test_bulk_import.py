"""Tests for the bulk CSV/XLSX invoice import application service.

:func:`~application.invoices.import_invoices_from_rows` delegates every row's
write to :func:`~application.invoices.create_catalogue_invoice` -- the sole
sanctioned :class:`~domain.invoices.Invoice` writer
(``composition-service-no-parallel-write-path``) -- and never persists a row
itself. These tests exercise it against the real encrypted
:class:`~adapters.persistence.profile.invoices.InvoiceCatalogueRepository` (real
master-key provider, real engine) -- no mocks.

See Also:
    :class:`~application.invoices.BulkInvoiceImportRow`
        Typed per-row boundary the tests validate before persistence.
    :func:`~application.invoices.read_bulk_invoice_import_rows`
        CSV/XLSX reader whose extension and column validation are covered here.
    :func:`~entrypoints.cli._ledger_business_invoice_cli.catalogue_import`
        CLI wrapper that feeds operator files into this application service.
"""

from __future__ import annotations

import io
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from openpyxl import Workbook
from pydantic import ValidationError

from ....adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ....domain.invoices import InvoiceValidationError
from ....domain.iva import InvoiceKind
from ....tests.secure_sql import isolated_runtime_profile
from .. import (
    BulkInvoiceImportRow,
    import_invoices_from_rows,
    read_bulk_invoice_import_rows,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET_ID = "29292929-2929-4292-8292-292929292929"
_CIF = "A58818501"


def _csv_rows(text: str) -> list[tuple[int, dict[str | Any, str | Any]]]:
    import csv as _csv

    reader = _csv.DictReader(io.StringIO(text))
    return list(enumerate(reader, start=2))


def test_bulk_invoice_row_model_requires_all_mandatory_fields() -> None:
    """The typed row model enforces every required field via pydantic, not a bare dict."""
    with pytest.raises(ValidationError):
        BulkInvoiceImportRow.model_validate({})


def test_import_invoices_from_rows_persists_through_create_catalogue_invoice(tmp_path: Path) -> None:
    """Each valid row creates a real, reloadable catalogue invoice."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        rows = _csv_rows(
            "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate\n"
            f"{_CIF},Papeleria Sol SL,BULK-A-001,2026-05-01,100.00,21\n"
            f"{_CIF},Papeleria Sol SL,BULK-A-002,2026-05-02,50.00,10\n",
        )
        result = import_invoices_from_rows(rows, bucket_id=_BUCKET_ID, kind=InvoiceKind.RECEIVED)

        assert result.rows == 2
        assert result.created == 2
        assert result.skipped_duplicate == 0
        assert result.refused == ()
        assert len(result.created_invoice_ids) == 2

        catalogue = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID).load()
        stored_numbers = {invoice.invoice_number for invoice in catalogue.invoices.values()}
        assert stored_numbers == {"BULK-A-001", "BULK-A-002"}
        for invoice_id in result.created_invoice_ids:
            assert invoice_id in catalogue.invoices


def test_import_invoices_from_rows_reimport_is_idempotent_no_op(tmp_path: Path) -> None:
    """Re-running the identical rows a second time skips every row as a duplicate."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        rows = _csv_rows(
            "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate\n"
            f"{_CIF},Papeleria Sol SL,BULK-B-001,2026-05-01,100.00,21\n",
        )
        first = import_invoices_from_rows(rows, bucket_id=_BUCKET_ID, kind=InvoiceKind.RECEIVED)
        assert first.created == 1

        second = import_invoices_from_rows(rows, bucket_id=_BUCKET_ID, kind=InvoiceKind.RECEIVED)
        assert second.created == 0
        assert second.skipped_duplicate == 1
        assert second.refused == ()

        catalogue = InvoiceCatalogueRepository(bucket_id=_BUCKET_ID).load()
        matching = [inv for inv in catalogue.invoices.values() if inv.invoice_number == "BULK-B-001"]
        assert len(matching) == 1


def test_import_invoices_from_rows_refuses_malformed_row_names_field(tmp_path: Path) -> None:
    """A malformed row (bad date) is refused naming its row number and field; valid rows still import."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        rows = _csv_rows(
            "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate\n"
            f"{_CIF},Papeleria Sol SL,BULK-C-001,2026-05-01,100.00,21\n"
            f"{_CIF},Papeleria Sol SL,BULK-C-002,not-a-date,50.00,10\n",
        )
        result = import_invoices_from_rows(rows, bucket_id=_BUCKET_ID, kind=InvoiceKind.RECEIVED)

        assert result.created == 1
        assert len(result.refused) == 1
        failure = result.refused[0]
        assert failure.row_number == 3
        assert failure.field == "invoice_date"


def test_import_invoices_from_rows_refuses_unsupported_iva_rate(tmp_path: Path) -> None:
    """An IVA percentage outside the closed slot taxonomy refuses that row, not the whole batch."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        rows = _csv_rows(
            "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate\n"
            f"{_CIF},Papeleria Sol SL,BULK-D-001,2026-05-01,100.00,13\n",
        )
        result = import_invoices_from_rows(rows, bucket_id=_BUCKET_ID, kind=InvoiceKind.RECEIVED)
        assert result.created == 0
        assert len(result.refused) == 1
        assert result.refused[0].field == "invoice"


def test_import_refuses_the_spanish_thousands_amount_instead_of_reading_it_as_cents(tmp_path: Path) -> None:
    """``1.234`` written by a gestor must refuse, not silently become one euro twenty-three.

    This is the shape a bare ``Decimal`` reads without complaint, because
    ``1.234`` is legal syntax for a different number. A gestor writing Spanish
    means one thousand two hundred and thirty-four euros; the old parser
    stored ``Decimal('1.234')`` and the invoice reached Modelo 303/390 a
    thousandfold light, as a wrong number rather than as any kind of failure.

    The row is refused naming its own field so the operator fixes the source.
    Reinterpreting it as ``1234`` is deliberately NOT the behaviour: the same
    text is a valid fractional amount under the grammar the file might
    equally be written in, and guessing between them would trade a loud
    refusal for a quiet reinterpretation of somebody's tax base.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        rows = _csv_rows(
            "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate\n"
            f"{_CIF},Papeleria Sol SL,BULK-ES-001,2026-05-01,1.234,21\n",
        )
        result = import_invoices_from_rows(rows, bucket_id=_BUCKET_ID, kind=InvoiceKind.RECEIVED)

        assert result.created == 0
        assert len(result.refused) == 1
        assert result.refused[0].field == "taxable_base"


@pytest.mark.parametrize(
    "taxable_base",
    (
        pytest.param("1.234,56", id="grouped-with-comma-decimal"),
        pytest.param("1234,56", id="bare-comma-decimal"),
        pytest.param("1.234", id="dot-grouped-thousands"),
    ),
)
def test_import_refuses_every_spanish_amount_grammar(taxable_base: str, tmp_path: Path) -> None:
    """No Spanish-written amount is silently accepted under the euro grammar.

    The three spellings a Spanish spreadsheet actually produces are asserted
    together because only one of them ever misbehaved: the comma forms always
    raised, and testing those alone would have proved nothing about the one
    that did not. That asymmetry is exactly how the defect shipped.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        rows = _csv_rows(
            "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate\n"
            f'{_CIF},Papeleria Sol SL,BULK-ES-002,2026-05-01,"{taxable_base}",21\n',
        )
        result = import_invoices_from_rows(rows, bucket_id=_BUCKET_ID, kind=InvoiceKind.RECEIVED)

        assert result.created == 0
        assert [failure.field for failure in result.refused] == ["taxable_base"]


def test_import_still_accepts_the_canonical_euro_amount(tmp_path: Path) -> None:
    """The refusal above is specific: a canonical dot-decimal amount still imports.

    Without this, a parser that refused every amount would pass the Spanish
    tests while breaking every real import.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        rows = _csv_rows(
            "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate\n"
            f"{_CIF},Papeleria Sol SL,BULK-ES-003,2026-05-01,1234.56,21\n",
        )
        result = import_invoices_from_rows(rows, bucket_id=_BUCKET_ID, kind=InvoiceKind.RECEIVED)

        assert result.refused == ()
        assert result.created == 1


def test_import_keeps_an_already_numeric_workbook_cell_unjudged(tmp_path: Path) -> None:
    """A numeric XLSX cell carries the workbook's representation, not the operator's grammar.

    The euro-grammar cap applies to text a person wrote. A spreadsheet
    formula can yield a float with more precision than a euro carries, and
    that precision is the workbook's doing; holding it to the typed-text
    grammar would refuse rows that never passed through anyone's keyboard.
    """
    xlsx_path = tmp_path / "invoices.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(
        ["counterparty_nif", "counterparty_name", "invoice_number", "invoice_date", "taxable_base", "iva_rate"],
    )
    sheet.append([_CIF, "Papeleria Sol SL", "BULK-ES-004", "2026-05-01", 1000 / 3, 21])
    workbook.save(xlsx_path)

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        rows = list(read_bulk_invoice_import_rows(xlsx_path))
        result = import_invoices_from_rows(rows, bucket_id=_BUCKET_ID, kind=InvoiceKind.RECEIVED)

        assert result.refused == ()
        assert result.created == 1


def test_read_bulk_invoice_import_rows_reads_csv_and_xlsx_identically(tmp_path: Path) -> None:
    """The CSV and XLSX readers yield the same row content for the same data."""
    csv_path = tmp_path / "invoices.csv"
    csv_path.write_text(
        "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,iva_rate\n"
        f"{_CIF},Papeleria Sol SL,BULK-E-001,2026-05-01,100.00,21\n",
        encoding="utf-8",
    )
    xlsx_path = tmp_path / "invoices.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(
        ["counterparty_nif", "counterparty_name", "invoice_number", "invoice_date", "taxable_base", "iva_rate"],
    )
    sheet.append([_CIF, "Papeleria Sol SL", "BULK-E-001", "2026-05-01", 100.00, 21])
    workbook.save(xlsx_path)

    csv_rows = list(read_bulk_invoice_import_rows(csv_path))
    xlsx_rows = list(read_bulk_invoice_import_rows(xlsx_path))

    assert len(csv_rows) == 1
    assert len(xlsx_rows) == 1
    assert csv_rows[0][1]["invoice_number"] == xlsx_rows[0][1]["invoice_number"] == "BULK-E-001"
    assert Decimal(str(csv_rows[0][1]["taxable_base"])) == Decimal(str(xlsx_rows[0][1]["taxable_base"]))


def test_read_bulk_invoice_import_rows_rejects_unknown_extension(tmp_path: Path) -> None:
    """An unsupported file extension refuses before any row is read."""
    bad_path = tmp_path / "invoices.txt"
    bad_path.write_text("counterparty_nif\n", encoding="utf-8")
    with pytest.raises(InvoiceValidationError):
        list(read_bulk_invoice_import_rows(bad_path))


def test_read_bulk_invoice_import_rows_rejects_unknown_column(tmp_path: Path) -> None:
    """An unrecognised CSV column is refused before any writes."""
    csv_path = tmp_path / "invoices.csv"
    csv_path.write_text(
        "counterparty_nif,counterparty_name,invoice_number,invoice_date,taxable_base,bogus\n"
        f"{_CIF},Papeleria Sol SL,BULK-F-001,2026-05-01,100.00,xyz\n",
        encoding="utf-8",
    )
    with pytest.raises(InvoiceValidationError):
        list(read_bulk_invoice_import_rows(csv_path))
