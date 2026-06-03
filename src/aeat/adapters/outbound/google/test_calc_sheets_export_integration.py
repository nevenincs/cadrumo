"""Online modelo-export request-pipeline integration (W05 / follow-up S05).

The live Drive/Sheets write itself is validated by manual operator testing
(``aeat config google sync calc export`` against a real account) — external-write
tests are project-forbidden (``live_write`` is collection-dropped). What CAN and
MUST be gated in CI is that, for a real modelo, the apply adapter assembles the
COMPLETE set of Google-Sheets API write requests from the plan with no network:
values, live formulas, the Evidencia surface, number formats, and the
section-header / start-final emphasis. A regression that drops any request batch
is caught here, offline.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....application.storage.calc_sheets import build_export_plan
from ....core.resources import resources
from ._calc_sheets_apply import (
    _build_emphasis_format_requests,
    _build_evidence_value_data,
    _build_formula_data,
    _build_number_format_requests,
    _build_value_data,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound]


def _m130_plan():
    snapshot = resources().modelos.authority.snapshot("130", filing_year=2025, period="1T", on=date(2025, 4, 1))
    return build_export_plan(snapshot)


def test_apply_request_pipeline_is_complete_for_a_real_modelo() -> None:
    plan = _m130_plan()
    sheet_id_by_tab = {"Entradas": 0, "Cálculos": 1, "Procedencia": 2, "Tarifas": 3, "Guía": 4, "Evidencia": 5, "Detalle": 6}

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
