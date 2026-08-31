"""Online modelo-export request-pipeline integration.

The live Drive/Sheets write itself is validated by manual operator testing
(``aeat config google sync calc export`` against a real account) — write-shaped
online tests are project-forbidden. What CAN and
MUST be gated in CI is that, for a real modelo, the apply adapter assembles the
COMPLETE set of Google-Sheets API write requests from the plan with no network:
values, live formulas, the Evidencia surface, number formats, and the
section-header / start-final emphasis. A regression that drops any request batch
is caught here, offline.
"""

from __future__ import annotations

from datetime import date

import pytest

from .....application.storage.calc_sheets.engine import build_export_plan
from .....domain.calculations.registry.authority import bundled_authority
from .._calc_sheets_apply_formatting import (
    _build_auto_filter_requests,
    _build_base_font_requests,
    _build_column_width_requests,
    _build_emphasis_format_requests,
    _build_frozen_view_requests,
    _build_number_format_requests,
    _build_styled_range_requests,
)
from .._calc_sheets_apply_values import (
    _build_evidence_value_data,
    _build_formula_data,
    _build_value_data,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def _m130_plan():
    snapshot = bundled_authority().snapshot("130", filing_year=2025, period="1T", on=date(2025, 4, 1))
    return build_export_plan(snapshot)


def test_apply_request_pipeline_is_complete_for_a_real_modelo() -> None:
    plan = _m130_plan()
    sheet_id_by_tab = {
        "Entradas": 0,
        "Cálculos": 1,
        "Procedencia": 2,
        "Tarifas": 3,
        "Guía": 4,
        "Evidencia": 5,
        "Detalle": 6,
    }

    value_data = _build_value_data(plan.value_cells)
    formula_data = _build_formula_data(plan.formula_cells)
    evidence_data = _build_evidence_value_data(plan)
    number_format_requests = _build_number_format_requests(plan, sheet_id_by_tab=sheet_id_by_tab)
    emphasis_requests = _build_emphasis_format_requests(plan, sheet_id_by_tab=sheet_id_by_tab)

    # Every batch the live export depends on is present + well-formed.
    assert value_data, "value writes missing"
    assert formula_data, "live formula writes missing"
    assert all(str(entry["values"][0][0]).startswith("=") for entry in formula_data)
    assert evidence_data, "Evidencia surface writes missing"
    assert number_format_requests, "number-format requests missing"
    assert emphasis_requests, "section-header / anchor emphasis requests missing"

    # Every request targets a known tab (no stray sheetId).
    for request in number_format_requests + emphasis_requests:
        assert request["repeatCell"]["range"]["sheetId"] in sheet_id_by_tab.values()


def test_apply_design_request_set_is_complete_for_a_real_modelo() -> None:
    # The online apply renders the full design system: monospace base font,
    # role-tinted styled ranges, sized columns, frozen header rows, and filters
    # mirroring the offline materialiser from the same plan facets.
    plan = _m130_plan()
    sheet_id_by_tab = {
        "Entradas": 0,
        "Cálculos": 1,
        "Procedencia": 2,
        "Tarifas": 3,
        "Guía": 4,
        "Evidencia": 5,
        "Detalle": 6,
    }

    base_font = _build_base_font_requests(plan, sheet_id_by_tab=sheet_id_by_tab)
    styled = _build_styled_range_requests(plan, sheet_id_by_tab=sheet_id_by_tab)
    widths = _build_column_width_requests(plan.column_widths, sheet_id_by_tab=sheet_id_by_tab)
    frozen = _build_frozen_view_requests(plan.frozen_views, sheet_id_by_tab=sheet_id_by_tab)
    filters = _build_auto_filter_requests(plan.auto_filters, sheet_id_by_tab=sheet_id_by_tab)

    # The base font sets a monospace family on every tab's whole grid.
    assert base_font, "base font requests missing"
    families = {req["repeatCell"]["cell"]["userEnteredFormat"]["textFormat"]["fontFamily"] for req in base_font}
    assert families == {plan.font_family}

    # Styled ranges carry fills / bold / alignment; at least one sets a fill.
    assert styled, "styled range requests missing"
    assert any("backgroundColor" in req["repeatCell"]["cell"]["userEnteredFormat"] for req in styled)

    assert widths, "column width requests missing"
    assert all(req["updateDimensionProperties"]["properties"]["pixelSize"] > 0 for req in widths)

    # Frozen header rows present; at least one tab freezes its header row.
    assert frozen, "frozen view requests missing"
    assert any(req["updateSheetProperties"]["properties"]["gridProperties"]["frozenRowCount"] >= 1 for req in frozen)

    assert filters, "basic filter requests missing"
    for request in styled + widths + frozen + filters:
        sheet_id = (
            request.get("repeatCell", {}).get("range", {}).get("sheetId")
            if "repeatCell" in request
            else request.get("updateDimensionProperties", {}).get("range", {}).get("sheetId")
            if "updateDimensionProperties" in request
            else request.get("updateSheetProperties", {}).get("properties", {}).get("sheetId")
            if "updateSheetProperties" in request
            else request.get("setBasicFilter", {}).get("filter", {}).get("range", {}).get("sheetId")
        )
        assert sheet_id in sheet_id_by_tab.values()
