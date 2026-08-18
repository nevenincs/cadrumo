"""Cross-cutting narrowed-exception controls."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_corrupt_xlsx_returns_failed_report(tmp_path) -> None:
    from dev.registry._workbook_parity import scan_workbook

    bad_xlsx = tmp_path / "bad.xlsx"
    bad_xlsx.write_bytes(b"NOT AN XLSX FILE CONTENT AT ALL!!!")

    report = scan_workbook(bad_xlsx, root=tmp_path)

    assert report.scan_status == "failed"
    assert report.error is not None


def test_tokenizer_error_triggers_regex_fallback() -> None:
    from dev.registry._workbook_parity import _formula_references

    result = _formula_references("Sheet1", "=SUM(A1:B2", remaining=10)

    assert isinstance(result, tuple)


def test_well_formed_formula_returns_refs() -> None:
    from dev.registry._workbook_parity import _formula_references

    result = _formula_references("Sheet1", "=SUM(A1,B2,C3)", remaining=10)

    assert result
