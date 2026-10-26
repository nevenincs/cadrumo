"""Actual transport preserves saved comparison cells and their human presentation."""

from io import BytesIO

import pytest
from openpyxl import load_workbook

from .....application.modelo.tests.test_reconciliation_export import (
    reconciliation_plan_fixture,
    reconciliation_projection_fixture,
)
from ..calc_sheets_xlsx import materialize_export_plan

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


def test_materialized_saved_comparison_keeps_both_values_grounding_and_missing_evidence_literal() -> None:
    plan = reconciliation_plan_fixture(reconciliation_projection_fixture())
    assert plan.metadata.kind == "reconciliation"
    assert plan.formula_cells == ()
    payload = materialize_export_plan(plan)
    assert materialize_export_plan(plan) == payload
    workbook = load_workbook(BytesIO(payload))
    differences = workbook["Detalle"]
    assert differences.protection.sheet
    assert differences["D2"].protection.locked
    assert differences["D2"].value == "100.000"
    assert differences["E2"].value is None
    assert differences["G2"].value == "saved-law"
    assert differences["H2"].value == "saved-source"
    assert workbook["Evidencia"]["C2"].value == "=not a spreadsheet formula"
    assert workbook["Evidencia"]["C2"].data_type == "s"
    assert workbook["Evidencia"]["D2"].value == "reason: missing_evidence"
