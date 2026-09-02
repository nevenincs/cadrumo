"""Pure Google Sheets presentation and validation request builders.

The live apply adapter coordinates Drive and Sheets calls.  This sibling owns
the pure request bodies that render a :class:`SheetExportPlan`'s declared
formatting, grid, protection, and input-validation facets.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal
from typing import TYPE_CHECKING, Final, Literal

from ....application.storage.calc_sheets.records import (
    SheetAutoFilter,
    SheetCellConstraint,
    SheetColumnWidth,
    SheetExportPlan,
    SheetFrozenView,
    SheetProtectedRange,
    TabName,
)
from ....application.storage.calc_sheets.theme import (
    ROLE_STYLES,
    STYLED_RANGE_VERTICAL_ALIGN,
    WORKBOOK_FONT_FAMILY,
    hex_to_rgb_floats,
)

if TYPE_CHECKING:
    from googleapiclient._apis.sheets.v4.schemas import (
        BooleanCondition,
        CellFormat,
        Color,
        GridRange,
        Request,
        TextFormat,
    )

#: Sheets number-format types, spelled as the literals the API accepts so an
#: unsupported value is refused here rather than at the wire.
_NUMBER_FORMAT_TYPE: Final[Mapping[str, Literal["NUMBER", "PERCENT"]]] = {
    "money": "NUMBER",
    "integer": "NUMBER",
    "percentage": "PERCENT",
}


def _sheets_color(hex_value: str) -> Color:
    """Convert an ``RRGGBB`` hex colour into the Sheets API ``Color`` shape.

    The shared palette lives in the application layer and cannot name an
    adapter-side API schema, so the conversion to the wire type happens here.
    """
    rgb = hex_to_rgb_floats(hex_value)
    return {"red": rgb["red"], "green": rgb["green"], "blue": rgb["blue"]}


def build_number_format_requests(
    plan: SheetExportPlan,
    *,
    sheet_id_by_tab: Mapping[str, int],
) -> list[Request]:
    """Apply each numeric casilla's display format, mirroring the offline workbook.

    Money/integer cells render as NUMBER with the casilla's pattern; ratio cells
    as PERCENT — so the online Sheet shows the same money/percentage presentation
    as the offline xls and the official AEAT workbook.
    """
    requests: list[Request] = []
    for number_format in plan.number_formats:
        sheet_id = sheet_id_by_tab.get(number_format.address.tab.value)
        if sheet_id is None:
            continue
        requests.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": number_format.address.row - 1,
                        "endRowIndex": number_format.address.row,
                        "startColumnIndex": number_format.address.column - 1,
                        "endColumnIndex": number_format.address.column,
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "numberFormat": {
                                "type": _NUMBER_FORMAT_TYPE[number_format.data_type],
                                "pattern": number_format.pattern,
                            },
                        },
                    },
                    "fields": "userEnteredFormat.numberFormat",
                },
            },
        )
    return requests


def build_emphasis_format_requests(
    plan: SheetExportPlan,
    *,
    sheet_id_by_tab: Mapping[str, int],
) -> list[Request]:
    """Bold the section-header cells and start/final anchor labels.

    Mirrors the offline workbook's section-header + anchor styling so the two
    transports present the same official-workbook orientation. The label text is
    written by the value batch; this only sets the bold weight.
    """
    requests: list[Request] = []
    addresses = [header.address for header in plan.section_headers] + [anchor.address for anchor in plan.anchors]
    for address in addresses:
        sheet_id = sheet_id_by_tab.get(address.tab.value)
        if sheet_id is None:
            continue
        requests.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": address.row - 1,
                        "endRowIndex": address.row,
                        "startColumnIndex": address.column - 1,
                        "endColumnIndex": address.column,
                    },
                    "cell": {"userEnteredFormat": {"textFormat": {"bold": True}}},
                    "fields": "userEnteredFormat.textFormat.bold",
                },
            },
        )
    return requests


_HORIZONTAL_ALIGN: Final[Mapping[str, Literal["LEFT", "CENTER", "RIGHT"]]] = {
    "left": "LEFT",
    "center": "CENTER",
    "right": "RIGHT",
}
_VERTICAL_ALIGN: Final[Mapping[str, Literal["TOP", "MIDDLE", "BOTTOM"]]] = {
    "top": "TOP",
    "middle": "MIDDLE",
    "bottom": "BOTTOM",
}
# Approximate Sheets pixel size for one character column-width unit.
_PIXELS_PER_WIDTH_UNIT: Final[int] = 7


def build_base_font_requests(
    plan: SheetExportPlan,
    *,
    sheet_id_by_tab: Mapping[str, int],
) -> list[Request]:
    """Set the monospace family across every tab's whole grid in one request each.

    The role-specific styled-range requests (which carry bold / colour / fill)
    run after these and merge on top, so the workbook reads in the chosen
    monospace family while the per-role emphasis still lands. Mirrors the
    offline materialiser's base-font pass over every populated cell.
    """
    family = plan.font_family or WORKBOOK_FONT_FAMILY
    requests: list[Request] = []
    for tab in TabName:
        sheet_id = sheet_id_by_tab.get(tab.value)
        if sheet_id is None:
            continue
        requests.append(
            {
                "repeatCell": {
                    "range": {"sheetId": sheet_id},
                    "cell": {"userEnteredFormat": {"textFormat": {"fontFamily": family}}},
                    "fields": "userEnteredFormat.textFormat.fontFamily",
                },
            },
        )
    return requests


def build_styled_range_requests(
    plan: SheetExportPlan,
    *,
    sheet_id_by_tab: Mapping[str, int],
) -> list[Request]:
    """Render each role-tagged styled range as a ``repeatCell`` format request.

    Resolves the range's :class:`StyleRole` through the shared ``ROLE_STYLES``
    palette — the same source the offline materialiser reads — so the slate
    header band, blue-grey section banners, pale-yellow input boxes, grey
    computed cells, green result, and wrapped body columns render identically
    online and offline. Later ranges win on overlap (the API applies requests in
    order), matching the engine's accent-last ordering.
    """
    family = plan.font_family or WORKBOOK_FONT_FAMILY
    requests: list[Request] = []
    for styled in plan.styled_ranges:
        sheet_id = sheet_id_by_tab.get(styled.tab.value)
        if sheet_id is None:
            continue
        style = ROLE_STYLES[styled.role]
        text_format: TextFormat = {"fontFamily": family, "bold": style.bold}
        if style.font_hex is not None:
            text_format["foregroundColor"] = _sheets_color(style.font_hex)
        user_format: CellFormat = {
            "textFormat": text_format,
            "horizontalAlignment": _HORIZONTAL_ALIGN[style.align],
            "verticalAlignment": _VERTICAL_ALIGN[STYLED_RANGE_VERTICAL_ALIGN],
            "wrapStrategy": "WRAP" if styled.wrap else "OVERFLOW_CELL",
        }
        fields = [
            "userEnteredFormat.textFormat",
            "userEnteredFormat.horizontalAlignment",
            "userEnteredFormat.verticalAlignment",
            "userEnteredFormat.wrapStrategy",
        ]
        if style.fill_hex is not None:
            user_format["backgroundColor"] = _sheets_color(style.fill_hex)
            fields.append("userEnteredFormat.backgroundColor")
        requests.append(
            {
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": styled.start_row - 1,
                        "endRowIndex": styled.end_row,
                        "startColumnIndex": styled.start_column - 1,
                        "endColumnIndex": styled.end_column,
                    },
                    "cell": {"userEnteredFormat": user_format},
                    "fields": ",".join(fields),
                },
            },
        )
    return requests


def build_column_width_requests(
    column_widths: Iterable[SheetColumnWidth],
    *,
    sheet_id_by_tab: Mapping[str, int],
) -> list[Request]:
    """Size each declared column so labels and legal-ref columns do not clip."""
    requests: list[Request] = []
    for width in column_widths:
        sheet_id = sheet_id_by_tab.get(width.tab.value)
        if sheet_id is None:
            continue
        requests.append(
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": sheet_id,
                        "dimension": "COLUMNS",
                        "startIndex": width.column - 1,
                        "endIndex": width.column,
                    },
                    "properties": {"pixelSize": width.width * _PIXELS_PER_WIDTH_UNIT},
                    "fields": "pixelSize",
                },
            },
        )
    return requests


def build_frozen_view_requests(
    frozen_views: Iterable[SheetFrozenView],
    *,
    sheet_id_by_tab: Mapping[str, int],
) -> list[Request]:
    """Freeze the header rows / leading columns so they stay visible on scroll."""
    requests: list[Request] = []
    for frozen in frozen_views:
        sheet_id = sheet_id_by_tab.get(frozen.tab.value)
        if sheet_id is None:
            continue
        requests.append(
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "gridProperties": {
                            "frozenRowCount": frozen.frozen_rows,
                            "frozenColumnCount": frozen.frozen_columns,
                        },
                    },
                    "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount",
                },
            },
        )
    return requests


def build_auto_filter_requests(
    auto_filters: Iterable[SheetAutoFilter],
    *,
    sheet_id_by_tab: Mapping[str, int],
) -> list[Request]:
    """Install a basic filter over each tab's header + data rows."""
    requests: list[Request] = []
    for filter_range in auto_filters:
        sheet_id = sheet_id_by_tab.get(filter_range.tab.value)
        if sheet_id is None:
            continue
        requests.append(
            {
                "setBasicFilter": {
                    "filter": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": filter_range.start_row - 1,
                            "endRowIndex": filter_range.end_row,
                            "startColumnIndex": filter_range.start_column - 1,
                            "endColumnIndex": filter_range.end_column,
                        },
                    },
                },
            },
        )
    return requests


def build_grid_resize_requests(
    plan: SheetExportPlan,
    *,
    sheet_id_by_tab: Mapping[str, int],
) -> list[Request]:
    """Compute requests to grow tabs beyond the default Sheets grid.

    Resizes always grow; an operator-expanded grid is never shrunk.
    """
    default_rows = 1000
    default_columns = 26
    row_headroom = 50

    max_row: dict[str, int] = {}
    max_col: dict[str, int] = {}

    def bump(tab_value: str, row: int, column: int) -> None:
        if max_row.get(tab_value, 0) < row:
            max_row[tab_value] = row
        if max_col.get(tab_value, 0) < column:
            max_col[tab_value] = column

    for vcell in plan.value_cells:
        bump(vcell.address.tab.value, vcell.address.row, vcell.address.column)
    for fcell in plan.formula_cells:
        bump(fcell.address.tab.value, fcell.address.row, fcell.address.column)
    bump("Guía", 1 + len(plan.guide.paragraphs) + 10, 4)
    for row_set in plan.row_sets:
        bump(row_set.tab.value, row_set.first_data_row + 50, len(row_set.columns))

    requests: list[Request] = []
    for tab_value, max_r in max_row.items():
        sheet_id = sheet_id_by_tab.get(tab_value)
        if sheet_id is None:
            continue
        requests.append(
            {
                "updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "gridProperties": {
                            "rowCount": max(max_r + row_headroom, default_rows),
                            "columnCount": max(max_col.get(tab_value, 1), default_columns),
                        },
                    },
                    "fields": "gridProperties.rowCount,gridProperties.columnCount",
                },
            },
        )
    return requests


def build_protected_range_requests(
    protected: Iterable[SheetProtectedRange],
    *,
    sheet_id_by_tab: Mapping[str, int],
) -> list[Request]:
    """Build immutable-sheet protection requests for the plan's declared ranges."""
    requests: list[Request] = []
    for region in protected:
        sheet_id = sheet_id_by_tab.get(region.tab.value)
        if sheet_id is None:
            continue
        requests.append(
            {
                "addProtectedRange": {
                    "protectedRange": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": region.start_row - 1,
                            "endRowIndex": region.end_row,
                            "startColumnIndex": region.start_column - 1,
                            "endColumnIndex": region.end_column,
                        },
                        "description": region.description,
                        "warningOnly": False,
                        "editors": {"users": []},
                    },
                },
            },
        )
    return requests


def build_cell_constraint_requests(
    constraints: Iterable[SheetCellConstraint],
    *,
    sheet_id_by_tab: Mapping[str, int],
) -> list[Request]:
    """Translate each constrained cell into validation and grounding-note requests."""
    requests: list[Request] = []
    for constraint in constraints:
        sheet_id = sheet_id_by_tab.get(constraint.address.tab.value)
        if sheet_id is None:
            continue
        condition = _condition_for_constraint(constraint)
        if condition is None:
            continue
        cell_range: GridRange = {
            "sheetId": sheet_id,
            "startRowIndex": constraint.address.row - 1,
            "endRowIndex": constraint.address.row,
            "startColumnIndex": constraint.address.column - 1,
            "endColumnIndex": constraint.address.column,
        }
        requests.append(
            {
                "setDataValidation": {
                    "range": cell_range,
                    "rule": {
                        "condition": condition,
                        "inputMessage": _input_message_for_constraint(constraint),
                        "strict": True,
                        "showCustomUi": True,
                    },
                },
            },
        )
        requests.append(
            {
                "updateCells": {
                    "range": cell_range,
                    "rows": [{"values": [{"note": _input_message_for_constraint(constraint)}]}],
                    "fields": "note",
                },
            },
        )
    return requests


def _condition_for_constraint(constraint: SheetCellConstraint) -> BooleanCondition | None:
    """Resolve the tightest Sheets BooleanCondition for a constraint."""
    lower = constraint.min_value
    upper = constraint.max_value
    if constraint.sign == "non_negative":
        floor = Decimal("0")
        lower = floor if lower is None else max(lower, floor)
    elif constraint.sign == "non_positive":
        ceiling = Decimal("0")
        upper = ceiling if upper is None else min(upper, ceiling)
    if lower is not None and upper is not None:
        return {
            "type": "NUMBER_BETWEEN",
            "values": [
                {"userEnteredValue": format(lower, "f")},
                {"userEnteredValue": format(upper, "f")},
            ],
        }
    if lower is not None:
        return {
            "type": "NUMBER_GREATER_THAN_EQ",
            "values": [{"userEnteredValue": format(lower, "f")}],
        }
    if upper is not None:
        return {
            "type": "NUMBER_LESS_THAN_EQ",
            "values": [{"userEnteredValue": format(upper, "f")}],
        }
    return None


def _input_message_for_constraint(constraint: SheetCellConstraint) -> str:
    """Render the operator-visible constraint bounds and legal references."""
    parts: list[str] = []
    if constraint.sign == "non_negative":
        parts.append("≥ 0")
    elif constraint.sign == "non_positive":
        parts.append("≤ 0")
    if constraint.min_value is not None:
        parts.append(f"≥ {format(constraint.min_value, 'f')}")
    if constraint.max_value is not None:
        parts.append(f"≤ {format(constraint.max_value, 'f')}")
    bounds = " ∧ ".join(parts) if parts else "any"
    refs = ", ".join(constraint.legal_refs)
    return f"Casilla {constraint.casilla_id}: {bounds}. Refs: {refs}."
