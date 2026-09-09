"""Design-system facets: font, role fills, freezes, filters, widths, wrap.

The export must mirror the official AEAT modelo look. This locks the engine
emitting the typed styling facets consumed by the live Google Sheets adapter.
"""

from __future__ import annotations

from datetime import date

import pytest

from .....domain.calculations.registry.authority import bundled_authority
from ..engine import build_export_plan
from ..records import TabName
from ..theme import WORKBOOK_FONT_FAMILY, StyleRole

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _m130_plan():
    snapshot = bundled_authority().snapshot("130", filing_year=2025, period="1T", on=date(2025, 4, 1))
    return build_export_plan(snapshot)


def test_engine_emits_design_facets() -> None:
    plan = _m130_plan()

    assert plan.font_family == WORKBOOK_FONT_FAMILY

    roles = {styled.role for styled in plan.styled_ranges}
    # The full role vocabulary the official look relies on is present.
    assert {StyleRole.HEADER, StyleRole.SECTION_BANNER, StyleRole.INPUT, StyleRole.COMPUTED, StyleRole.RESULT} <= roles

    # A header band on row 1 of both data tabs.
    header_tabs = {
        styled.tab for styled in plan.styled_ranges if styled.role is StyleRole.HEADER and styled.start_row == 1
    }
    assert TabName.ENTRADAS in header_tabs
    assert TabName.CALCULOS in header_tabs

    # The input column lives on Entradas; the computed column on Cálculos.
    input_tabs = {styled.tab for styled in plan.styled_ranges if styled.role is StyleRole.INPUT}
    computed_tabs = {styled.tab for styled in plan.styled_ranges if styled.role is StyleRole.COMPUTED}
    assert input_tabs == {TabName.ENTRADAS}
    assert computed_tabs == {TabName.CALCULOS}

    # Frozen header row + basic filter on the data tabs; sized columns.
    frozen = {view.tab: view for view in plan.frozen_views}
    assert frozen[TabName.ENTRADAS].frozen_rows == 1
    assert frozen[TabName.CALCULOS].frozen_rows == 1
    assert {flt.tab for flt in plan.auto_filters} >= {TabName.ENTRADAS, TabName.CALCULOS}
    assert {width.tab for width in plan.column_widths} >= {TabName.ENTRADAS, TabName.CALCULOS}


def test_result_accent_is_ordered_after_the_computed_column() -> None:
    # The green result accent must win over the broad grey computed column on
    # overlap, so it is emitted later in declaration order.
    plan = _m130_plan()
    roles_in_order = [styled.role for styled in plan.styled_ranges]
    assert StyleRole.RESULT in roles_in_order
    assert StyleRole.COMPUTED in roles_in_order
    assert roles_in_order.index(StyleRole.RESULT) > roles_in_order.index(StyleRole.COMPUTED)
