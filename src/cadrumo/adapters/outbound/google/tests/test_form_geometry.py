"""Form geometry survives both workbook transports; destructive merges fail."""

from datetime import UTC, datetime
from io import BytesIO
from uuid import UUID

import pytest
from openpyxl import load_workbook

from .....application.storage.calc_sheets.records import (
    SheetCellAddress,
    SheetExportMetadata,
    SheetExportPlan,
    SheetGuideContent,
    SheetMergedRange,
    SheetNumberFormat,
    SheetReviewMetadata,
    SheetRowHeight,
    SheetStyledRange,
    SheetValueCell,
    TabName,
)
from .....application.storage.calc_sheets.theme import StyleRole
from .....core.period import Period
from ...workbook.calc_sheets_xlsx import materialize_export_plan
from .._calc_sheets_apply_formatting import (
    build_form_geometry_requests,
    build_grid_resize_requests,
    build_number_format_requests,
    build_styled_range_requests,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _plan() -> SheetExportPlan[SheetReviewMetadata]:
    return SheetExportPlan[SheetReviewMetadata](
        metadata=SheetReviewMetadata(
            kind="calculation",
            snapshot_digest="a" * 64,
            publication_id=UUID(int=1),
            title="Ejemplo",
            exported_at=datetime(2026, 10, 5, tzinfo=UTC),
        ),
        tabs=(TabName.FORM, TabName.GUIDE),
        guide=SheetGuideContent(title="Guía", paragraphs=("Ejemplo de diseño.",)),
        value_cells=(
            SheetValueCell(address=SheetCellAddress.at(TabName.FORM, 2, 2), value="Liquidación", role="label"),
        ),
        merged_ranges=(SheetMergedRange(tab=TabName.FORM, start_row=2, end_row=2, start_column=2, end_column=12),),
        row_heights=(SheetRowHeight(tab=TabName.FORM, row=2, height_pixels=48),),
        styled_ranges=(
            SheetStyledRange(
                tab=TabName.FORM,
                start_row=2,
                end_row=2,
                start_column=2,
                end_column=12,
                role=StyleRole.FORM_SECTION,
                boxed=True,
                wrap=True,
            ),
        ),
    )


def test_both_transports_preserve_form_geometry() -> None:
    plan = _plan()
    book = load_workbook(BytesIO(materialize_export_plan(plan)))
    form = book["Modelo"]
    assert str(next(iter(form.merged_cells.ranges))) == "B2:L2"
    assert form["B2"].value == "Liquidación"
    assert form.row_dimensions[2].height == 36
    assert form["B2"].border.top.style == "thin"
    requests = build_form_geometry_requests(plan, sheet_id_by_tab={"Modelo": 42})
    assert requests[0]["mergeCells"]["range"] == {
        "sheetId": 42,
        "startRowIndex": 1,
        "endRowIndex": 2,
        "startColumnIndex": 1,
        "endColumnIndex": 12,
    }
    assert requests[1]["updateDimensionProperties"]["properties"]["pixelSize"] == 48
    styled = build_styled_range_requests(plan, sheet_id_by_tab={"Modelo": 42})
    assert styled[0]["repeatCell"]["cell"]["userEnteredFormat"]["borders"]["top"]["style"] == "SOLID"


def test_merge_must_not_discard_another_value() -> None:
    plan = _plan()
    data = dict(plan)
    data["value_cells"] = (
        *plan.value_cells,
        SheetValueCell(address=SheetCellAddress.at(TabName.FORM, 2, 3), value="Do not lose", role="label"),
    )
    with pytest.raises(ValueError, match="discard"):
        SheetExportPlan[SheetReviewMetadata].model_validate(data)


def test_overlapping_merge_is_refused() -> None:
    plan = _plan()
    data = dict(plan)
    data["merged_ranges"] = (
        *plan.merged_ranges,
        SheetMergedRange(tab=TabName.FORM, start_row=2, end_row=3, start_column=10, end_column=12),
    )
    with pytest.raises(ValueError, match="overlap"):
        SheetExportPlan[SheetReviewMetadata].model_validate(data)


def test_geometry_alone_extends_the_native_grid() -> None:
    data = dict(_plan())
    data["merged_ranges"] = (
        SheetMergedRange(tab=TabName.FORM, start_row=1100, end_row=1101, start_column=1, end_column=30),
    )
    plan = SheetExportPlan[SheetReviewMetadata].model_validate(data)
    requests = build_grid_resize_requests(plan, sheet_id_by_tab={"Modelo": 42})
    grid = requests[0]["updateSheetProperties"]["properties"]["gridProperties"]
    assert grid["rowCount"] >= 1101
    assert grid["columnCount"] >= 30


def test_derived_guide_content_cannot_be_erased_by_a_merge() -> None:
    data = dict(_plan())
    data["metadata"] = SheetExportMetadata(
        modelo_id="130",
        revision_id="2019-y-siguientes",
        filing_year=2025,
        period=Period.from_year_and_code(2025, "4T"),
        engine_version="test",
        registry_sha="a" * 64,
        exported_at=datetime(2026, 10, 5, tzinfo=UTC),
    )
    data["merged_ranges"] = (SheetMergedRange(tab=TabName.GUIDE, start_row=1, end_row=3, start_column=1, end_column=2),)
    plan = SheetExportPlan.model_validate(data)
    with pytest.raises(ValueError, match="discard"):
        materialize_export_plan(plan)
    with pytest.raises(ValueError, match="discard"):
        build_form_geometry_requests(plan, sheet_id_by_tab={"Guía": 7})


def test_numeric_looking_box_label_remains_text_in_both_transports() -> None:
    data = dict(_plan())
    address = SheetCellAddress.at(TabName.FORM, 3, 9)
    data["value_cells"] = (*data["value_cells"], SheetValueCell(address=address, value="01", role="label"))
    data["number_formats"] = (SheetNumberFormat(address=address, data_type="text", pattern="@"),)
    plan = SheetExportPlan[SheetReviewMetadata].model_validate(data)
    cell = load_workbook(BytesIO(materialize_export_plan(plan)))["Modelo"]["I3"]
    assert cell.value == "01"
    assert cell.data_type == "s"
    assert cell.number_format == "@"
    request = build_number_format_requests(plan, sheet_id_by_tab={"Modelo": 42})[0]
    assert request["repeatCell"]["cell"]["userEnteredFormat"]["numberFormat"] == {"type": "TEXT", "pattern": "@"}
