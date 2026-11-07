"""A statement's date reaches the operation date only when its header names the devengo."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ......application.ledger.import_ports import LedgerParsedRow
from ......domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ...ledger_import import FinancialProviderBoundary
from ..csv import CsvProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]
_YEAR = filing_year_envelope().horizon


def _parsed_rows(tmp_path: Path, header: str, row: str) -> list[LedgerParsedRow]:
    source = tmp_path / "statement.csv"
    source.write_text(f"{header}\n{row}\n", encoding="utf-8")
    return list(FinancialProviderBoundary(CsvProvider()).ingest(source))


def test_a_column_naming_the_devengo_is_the_operation_date(tmp_path: Path) -> None:
    (parsed,) = _parsed_rows(
        tmp_path,
        "Fecha;Fecha de devengo;Concepto;Importe;Divisa",
        f"02/04/{_YEAR};30/03/{_YEAR};VENTA;1210,00;EUR",
    )
    assert parsed.raw.booked_date == date(_YEAR, 4, 2)
    assert parsed.operation_date == date(_YEAR, 3, 30)


@pytest.mark.parametrize(
    "header",
    [
        "Fecha;Concepto;Importe;Divisa",
        "Fecha operacion;Concepto;Importe;Divisa",
        "Fecha operación;Concepto;Importe;Divisa",
    ],
)
def test_a_bank_date_is_never_taken_for_an_operation_date(tmp_path: Path, header: str) -> None:
    (parsed,) = _parsed_rows(tmp_path, header, f"02/04/{_YEAR};VENTA;1210,00;EUR")
    assert parsed.raw.booked_date == date(_YEAR, 4, 2)
    assert parsed.operation_date is None
