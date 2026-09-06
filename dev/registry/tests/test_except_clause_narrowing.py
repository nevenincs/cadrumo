"""Cross-cutting narrowed-exception controls."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_corrupt_xlsx_returns_failed_report(tmp_path) -> None:
    from ..parity._workbook_parity import scan_workbook

    bad_xlsx = tmp_path / "bad.xlsx"
    bad_xlsx.write_bytes(b"NOT AN XLSX FILE CONTENT AT ALL!!!")

    report = scan_workbook(bad_xlsx, root=tmp_path)

    assert report.scan_status == "failed"
    assert report.error is not None


def test_tokenizer_error_triggers_regex_fallback() -> None:
    from openpyxl.formula import Tokenizer
    from openpyxl.formula.tokenizer import TokenizerError

    from ..parity._workbook_parity import _formula_references
    from ..parity._workbook_parity_models import WorkbookCellRef

    formula = '="unterminated string A1'
    with pytest.raises(TokenizerError):
        Tokenizer(formula)

    result = _formula_references("Sheet1", formula, remaining=10)

    assert result == (WorkbookCellRef(sheet="Sheet1", coordinate="A1"),)


def test_well_formed_formula_returns_refs() -> None:
    from ..parity._workbook_parity import _formula_references

    result = _formula_references("Sheet1", "=SUM(A1,B2,C3)", remaining=10)

    assert result
