"""The CSV provider's file-level facts: the account a statement names, and unreadable tables.

Every case reads a real CSV through the real provider; the IBANs are synthetic.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest

from ......core.external_constants import CSV_EXTENSIONS
from ......tests.inventory import FIXTURES_DIR
from ..base import UNREADABLE_TABLE_REFUSAL, InvalidFinancialSourceError
from ..csv import CsvProvider
from ..detection import detect_provider

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_BBVA = FIXTURES_DIR / "financial" / "tabular-dialects" / "bank_bbva_2026Q1.csv"
_IBAN_ONE = "ES9121000418450200051332"
_IBAN_TWO = "ES7921000813610123456789"
_BAD_CHECKSUM = "ES9221000418450200051332"
_HEADER = "Fecha,Concepto,Importe\n"
_ROW = "08/01/2026,Pago tarjeta,-10.00\n"


def _statement_account(path: Path) -> str | None:
    provider = CsvProvider()
    digest = next(iter(provider.ingest(path))).raw.provenance.source_sha256
    return provider.statement_account(path, source_sha256=digest)


def _write(tmp_path: Path, preamble: str) -> Path:
    path = tmp_path / "statement.csv"
    path.write_text(preamble + _HEADER + _ROW, encoding="utf-8")
    return path


def test_the_account_a_preamble_prints_is_the_statement_account() -> None:
    """The BBVA export prints its account, grouped, in the rows above the header."""
    assert _statement_account(_BBVA) == _IBAN_ONE


def test_a_preamble_naming_one_account_twice_names_it(tmp_path: Path) -> None:
    path = _write(tmp_path, f"Cuenta,{_IBAN_ONE}\nIBAN,{_IBAN_ONE[:4]} {_IBAN_ONE[4:]}\n")

    assert _statement_account(path) == _IBAN_ONE


@pytest.mark.parametrize(
    ("preamble", "reason"),
    [
        ("", "no preamble"),
        ("Extracto de movimientos\nFecha de extraccion,18/02/2026\n", "no account printed"),
        (f"Cuenta,{_IBAN_ONE}\nOtra cuenta,{_IBAN_TWO}\n", "two different accounts"),
        (f"Cuenta,{_BAD_CHECKSUM}\n", "a number that fails the mod-97 check"),
        ("Cuenta,ES91\n", "a number too short to be an IBAN"),
    ],
)
def test_a_preamble_that_names_no_single_valid_account_names_none(tmp_path: Path, preamble: str, reason: str) -> None:
    assert _statement_account(_write(tmp_path, preamble)) is None, reason


def test_an_account_printed_below_the_header_is_a_row_not_the_statement_account(tmp_path: Path) -> None:
    path = tmp_path / "statement.csv"
    path.write_text(f"{_HEADER}08/01/2026,Transferencia {_IBAN_ONE},-10.00\n", encoding="utf-8")

    assert _statement_account(path) is None


def test_a_file_that_no_longer_holds_the_digested_bytes_names_no_account(tmp_path: Path) -> None:
    path = _write(tmp_path, f"Cuenta,{_IBAN_ONE}\n")
    provider = CsvProvider()
    digest = next(iter(provider.ingest(path))).raw.provenance.source_sha256

    path.write_text(f"Cuenta,{_IBAN_TWO}\n{_HEADER}{_ROW}", encoding="utf-8")

    assert provider.statement_account(path, source_sha256=digest) is None


def test_a_tab_separated_statement_is_read_as_the_same_table(tmp_path: Path) -> None:
    """``.tsv`` is a CSV extension because detection really reads the tab-separated spelling."""
    rows = list(csv.reader(io.StringIO(_BBVA.read_text(encoding="utf-8")), delimiter=";"))
    out = io.StringIO()
    csv.writer(out, delimiter="\t", lineterminator="\n").writerows(rows)
    tsv = tmp_path / "bbva.tsv"
    tsv.write_text(out.getvalue(), encoding="utf-8")

    detected = detect_provider(tsv)

    assert ".tsv" in CSV_EXTENSIONS
    assert isinstance(detected, CsvProvider)
    assert [row.raw.provenance.source_row_index for row in detected.ingest(tsv)] == [
        row.raw.provenance.source_row_index for row in CsvProvider().ingest(_BBVA)
    ]
    assert _statement_account(tsv) == _IBAN_ONE


def test_a_table_the_reader_cannot_read_is_a_bounded_refusal_not_a_csv_error(tmp_path: Path) -> None:
    """A cell past the reader's field limit stops it; the refusal names no content."""
    path = tmp_path / "huge-cell.csv"
    path.write_text(f"{_HEADER}08/01/2026,{'x' * 200_000},-10.00\n", encoding="utf-8")
    provider = CsvProvider()

    validation = provider.validate_source(path)

    assert not validation.is_valid
    assert validation.warnings == (UNREADABLE_TABLE_REFUSAL,)
    with pytest.raises(InvalidFinancialSourceError) as refusal:
        tuple(provider.ingest(path))
    assert "xxxx" not in str(refusal.value)
    assert provider.statement_account(path, source_sha256="0" * 64) is None
