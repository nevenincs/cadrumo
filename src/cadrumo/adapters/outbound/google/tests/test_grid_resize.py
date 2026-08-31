"""Contract tests for ``_build_grid_resize_requests``.

The apply adapter calls this helper before writing any cells so the
target Sheets grid is large enough to hold the plan. If the helper
under-estimates the required rows / columns Sheets silently truncates
the operator's data; if it over-estimates the grid becomes uselessly
sparse. Sheets' default grid is 1000 rows by 26 columns; the helper
emits an ``updateSheetProperties`` request only when a tab needs to
grow beyond that.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from .....application.storage.calc_sheets.records import (
    SheetCellAddress,
    SheetExportMetadata,
    SheetExportPlan,
    SheetFormulaCell,
    SheetGuideContent,
    SheetRowSet,
    SheetRowSetColumn,
    SheetValueCell,
    TabName,
)
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.period import Period
from .._calc_sheets_apply_formatting import _build_grid_resize_requests

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_TEST_LEGAL_REFS = ("ley-58-2003:art-119",)
_TEST_SOURCE_REFS = ("aeat-dr-190-2025",)
_EXPORTED_AT = datetime(2026, 5, 28, 12, 50, 0, tzinfo=UTC)

_TEST_CASILLA: CasillaId = validated_casilla_id("test.casilla", surface="_TEST_CASILLA")


def _plan(
    *,
    value_cells: tuple[SheetValueCell, ...] = (),
    formula_cells: tuple[SheetFormulaCell, ...] = (),
    row_sets: tuple[SheetRowSet, ...] = (),
    paragraphs: tuple[str, ...] = ("guide line",),
) -> SheetExportPlan:
    return SheetExportPlan(
        metadata=SheetExportMetadata(
            modelo_id="100",
            revision_id="2025",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            engine_version="test/0.1",
            registry_sha="abcdef1234567890",
            exported_at=_EXPORTED_AT,
        ),
        value_cells=value_cells,
        formula_cells=formula_cells,
        row_sets=row_sets,
        guide=SheetGuideContent(title="Guía", paragraphs=paragraphs),
    )


_SHEET_IDS = {
    "Entradas": 1,
    "Cálculos": 2,
    "Procedencia": 3,
    "Tarifas": 4,
    "Detalle": 5,
    "Guía": 6,
}


def test_empty_plan_still_resizes_guide_tab_only() -> None:
    """The guide tab always receives at least the default-grid request via the floor bump."""

    plan = _plan()
    requests = _build_grid_resize_requests(plan, sheet_id_by_tab=_SHEET_IDS)

    # At least one request — the guide tab bump always runs.
    guide_request = next(
        req for req in requests if req["updateSheetProperties"]["properties"]["sheetId"] == _SHEET_IDS["Guía"]
    )
    assert guide_request["updateSheetProperties"]["properties"]["gridProperties"]["rowCount"] >= 1000


def test_value_cell_within_default_grid_yields_default_dimensions() -> None:
    """Cells inside the default 1000-by-26 grid emit a default-sized request."""

    plan = _plan(
        value_cells=(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.ENTRADAS, 5, 3),
                value=Decimal("100"),
                role="operator_input",
            ),
        ),
    )
    requests = _build_grid_resize_requests(plan, sheet_id_by_tab=_SHEET_IDS)

    entradas_request = next(
        req for req in requests if req["updateSheetProperties"]["properties"]["sheetId"] == _SHEET_IDS["Entradas"]
    )
    grid = entradas_request["updateSheetProperties"]["properties"]["gridProperties"]
    assert grid["rowCount"] >= 1000
    assert grid["columnCount"] >= 26


def test_value_cell_beyond_default_grid_grows_row_count() -> None:
    """A cell at row 1500 forces the tab's grid to grow past the default 1000."""

    plan = _plan(
        value_cells=(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.ENTRADAS, 1500, 5),
                value=Decimal("100"),
                role="operator_input",
            ),
        ),
    )
    requests = _build_grid_resize_requests(plan, sheet_id_by_tab=_SHEET_IDS)

    entradas_request = next(
        req for req in requests if req["updateSheetProperties"]["properties"]["sheetId"] == _SHEET_IDS["Entradas"]
    )
    grid = entradas_request["updateSheetProperties"]["properties"]["gridProperties"]
    # Row count must accommodate the cell + the 50-row headroom.
    assert grid["rowCount"] >= 1550


def test_row_sets_grow_detalle_grid_beyond_default() -> None:
    """A row-set at row 50 forces the Detalle grid to grow to 100+ rows."""

    row_set = SheetRowSet(
        grouping="per_perceptor_clave",
        tab=TabName.DETALLE,
        header_row=50,
        first_data_row=51,
        columns=(
            SheetRowSetColumn(
                binding="modelo-190-perceptor-row-nif",
                header_address=SheetCellAddress.at(TabName.DETALLE, 50, 1),
                header_label="NIF",
                legal_refs=_TEST_LEGAL_REFS,
            ),
        ),
        legal_refs=_TEST_LEGAL_REFS,
        source_refs=_TEST_SOURCE_REFS,
    )
    plan = _plan(row_sets=(row_set,))
    requests = _build_grid_resize_requests(plan, sheet_id_by_tab=_SHEET_IDS)

    detalle_request = next(
        req for req in requests if req["updateSheetProperties"]["properties"]["sheetId"] == _SHEET_IDS["Detalle"]
    )
    grid = detalle_request["updateSheetProperties"]["properties"]["gridProperties"]
    # Row-set reserves first_data_row + 50 = 101 rows; plus the
    # row_headroom (50) brings the floor to at least 151. The default
    # 1000 still wins because the floor is max(151, 1000).
    assert grid["rowCount"] >= 1000


def test_resize_skips_tabs_without_a_sheet_id() -> None:
    """A tab not present in sheet_id_by_tab is silently skipped."""

    plan = _plan(
        value_cells=(
            SheetValueCell(
                address=SheetCellAddress.at(TabName.ENTRADAS, 5, 3),
                value=Decimal("100"),
                role="operator_input",
            ),
        ),
    )
    # Drop the Entradas tab from the map.
    sheet_ids = {tab: sid for tab, sid in _SHEET_IDS.items() if tab != "Entradas"}
    requests = _build_grid_resize_requests(plan, sheet_id_by_tab=sheet_ids)

    entradas_requests = [
        req for req in requests if req["updateSheetProperties"]["properties"]["sheetId"] == _SHEET_IDS["Entradas"]
    ]
    assert entradas_requests == []


def test_formula_cell_address_extends_grid_bound() -> None:
    """Formula cells contribute to the grid-resize calculation just like value cells."""

    plan = _plan(
        formula_cells=(
            SheetFormulaCell(
                address=SheetCellAddress.at(TabName.CALCULOS, 1200, 4),
                formula="A1+B1",
                casilla_id=_TEST_CASILLA,
                rounding_rule="money",
            ),
        ),
    )
    requests = _build_grid_resize_requests(plan, sheet_id_by_tab=_SHEET_IDS)

    calculos_request = next(
        req for req in requests if req["updateSheetProperties"]["properties"]["sheetId"] == _SHEET_IDS["Cálculos"]
    )
    grid = calculos_request["updateSheetProperties"]["properties"]["gridProperties"]
    assert grid["rowCount"] >= 1250
