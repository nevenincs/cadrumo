"""Tests for official AEAT workbook parity backend infrastructure."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from openpyxl import Workbook

from ._workbook_parity import (
    SyntheticInputSet,
    SyntheticInputValue,
    WorkbookCellRef,
    WorkbookScanOptions,
    compare_registry_to_workbook,
    discover_workbooks,
    inventory_workbook_coverage,
    scan_workbook,
    verify_workbook_backend,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def _write_formula_workbook(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Modelo"
    worksheet["A1"] = Decimal("10")
    worksheet["A2"] = Decimal("21")
    worksheet["B1"] = "=A1+A2"
    worksheet["B2"] = "=SUM(A1:A2)"
    workbook.save(path)


def test_scan_workbook_discovers_xlsx_formula_cells(tmp_path: Path) -> None:
    workbook_path = tmp_path / "modelo_303" / "files" / "303-test.xlsx"
    _write_formula_workbook(workbook_path)

    report = scan_workbook(workbook_path, root=tmp_path, options=WorkbookScanOptions(per_file_timeout_seconds=5))

    assert report.path == "modelo_303/files/303-test.xlsx"
    assert report.modelo == "303"
    assert report.extension == ".xlsx"
    assert report.scan_status == "scanned"
    assert report.workbook_kind == "formula_form"
    assert report.formula_cells == 2
    assert {cell.coordinate for cell in report.output_candidates} == {"B1", "B2"}
    assert {cell.coordinate for cell in report.input_candidates} >= {"A1", "A2"}


def test_scan_workbook_records_binary_xls_as_unsupported(tmp_path: Path) -> None:
    workbook_path = tmp_path / "modelo_111" / "files" / "111-test.xls"
    workbook_path.parent.mkdir(parents=True, exist_ok=True)
    workbook_path.write_bytes(b"\xd0\xcf\x11\xe0")

    report = scan_workbook(workbook_path, root=tmp_path)

    assert report.modelo == "111"
    assert report.extension == ".xls"
    assert report.scan_status == "unsupported"
    assert report.workbook_kind == "unsupported_binary_xls"
    assert report.formula_cells == 0
    assert "parser or conversion path" in (report.error or "")


def test_inventory_workbook_coverage_is_deterministic(tmp_path: Path) -> None:
    _write_formula_workbook(tmp_path / "modelo_303" / "files" / "b.xlsx")
    _write_formula_workbook(tmp_path / "modelo_303" / "files" / "a.xlsx")

    reports = inventory_workbook_coverage(tmp_path, options=WorkbookScanOptions(per_file_timeout_seconds=5))

    assert [report.path for report in reports] == [
        "modelo_303/files/a.xlsx",
        "modelo_303/files/b.xlsx",
    ]


def test_inventory_workbook_coverage_reuses_unchanged_previous_report(tmp_path: Path) -> None:
    workbook_path = tmp_path / "modelo_303" / "files" / "a.xlsx"
    _write_formula_workbook(workbook_path)
    first = inventory_workbook_coverage(tmp_path, options=WorkbookScanOptions(per_file_timeout_seconds=5))

    reports = inventory_workbook_coverage(
        tmp_path,
        options=WorkbookScanOptions(per_file_timeout_seconds=5),
        previous_reports=first,
    )

    assert reports == first


def test_discover_workbooks_requires_existing_root(tmp_path: Path) -> None:
    missing = tmp_path / "missing"

    with pytest.raises(Exception, match="workbook root does not exist"):
        discover_workbooks(missing)


def test_compare_registry_to_workbook_reports_mismatch(tmp_path: Path) -> None:
    workbook_path = tmp_path / "modelo_303" / "files" / "303-test.xlsx"
    _write_formula_workbook(workbook_path)
    workbook = scan_workbook(workbook_path, root=tmp_path)
    synthetic = SyntheticInputSet(
        id="synthetic-303-basic",
        modelo="303",
        revision="2026",
        values=(
            SyntheticInputValue(
                id="base",
                value=Decimal("10"),
                workbook_cell=WorkbookCellRef(sheet="Modelo", coordinate="A1"),
                registry_binding="vat.base",
            ),
        ),
    )

    report = compare_registry_to_workbook(
        synthetic_input=synthetic,
        workbook=workbook,
        runner=verify_workbook_backend(tmp_path, scan_limit=1).runner,
        expected_workbook_values={"result": Decimal("31")},
        actual_registry_values={"result": Decimal("30")},
        output_cells={"result": WorkbookCellRef(sheet="Modelo", coordinate="B1", formula="=A1+A2")},
        registry_snapshot_id="303:2026:1T",
        legal_refs={"result": ("ley-37-1992:art-90",)},
        source_refs={"result": ("aeat-dr-303-2026",)},
    )

    assert report.status == "mismatch"
    assert report.registry_snapshot_id == "303:2026:1T"
    assert report.comparisons[0].status == "mismatch"
    assert report.comparisons[0].expected_workbook_value == Decimal("31")
    assert report.comparisons[0].legal_refs == ("ley-37-1992:art-90",)
    assert report.comparisons[0].source_refs == ("aeat-dr-303-2026",)


def test_verify_workbook_backend_reports_existing_backend(tmp_path: Path) -> None:
    _write_formula_workbook(tmp_path / "modelo_390" / "files" / "390-test.xlsx")

    report = verify_workbook_backend(tmp_path, scan_limit=10)

    assert report.backend_exists
    assert report.workbook_count == 1
    assert report.scanned_count == 1
    assert report.formula_workbook_count == 1
    assert report.failed_count == 0
    assert report.modelo_coverage[0].modelo == "390"
    assert report.modelo_coverage[0].formula_workbook_count == 1
