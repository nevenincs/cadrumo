"""Saved comparison plans preserve exact detail and readable localized presentation."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import pytest

from ....core.external_constants import OutputLanguage
from ...storage.calc_sheets.records import TabName
from ..reconciliation_export import build_modelo_reconciliation_export_plan
from ..reconciliation_export_labels import ReconciliationWorkbookLabels
from ..reconciliation_list_operation import ModeloReconciliationListEntryProjection, ModeloReconciliationListProjection
from ..reconciliation_records import ModeloReconciliationAdvisory, ModeloReconciliationDiffKind
from .reconciliation_fixture import RECONCILIATION_PROFILE_FIXTURE as _PROFILE
from .reconciliation_fixture import reconciliation_history_entry_fixture as _history_entry

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def reconciliation_projection_fixture() -> ModeloReconciliationListProjection:
    entry = _history_entry(event_id="a" * 64)
    difference = entry.diffs[0].model_copy(
        update={
            "diff_kind": ModeloReconciliationDiffKind.TOTAL,
            "legal_refs": ("saved-law",),
            "source_refs": ("saved-source",),
            "work_unit_value": "100.000",
            "evidence_value": "",
        }
    )
    entry = entry.model_copy(
        update={
            "diffs": (difference,),
            "advisory_count": 1,
            "advisories": (
                ModeloReconciliationAdvisory(
                    code="totals_not_reconciled",
                    message="=not a spreadsheet formula",
                    context={"reason": "missing_evidence"},
                ),
            ),
        }
    )
    return ModeloReconciliationListProjection(
        profile_id=_PROFILE,
        reconciliation_count=1,
        reconciliations=(ModeloReconciliationListEntryProjection.from_history_entry(entry),),
    )


def reconciliation_plan_fixture(projection: ModeloReconciliationListProjection):
    return build_modelo_reconciliation_export_plan(
        projection,
        publication_id=UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"),
        exported_at=datetime(2026, 10, 7, tzinfo=UTC),
        label=lambda key: key,
    )


def test_export_refuses_missing_detail_and_profile_substitution() -> None:
    projection = reconciliation_projection_fixture()
    with pytest.raises(ValueError, match="incomplete"):
        reconciliation_plan_fixture(
            projection.model_copy(
                update={"reconciliations": (projection.reconciliations[0].model_copy(update={"diffs": ()}),)}
            )
        )
    with pytest.raises(ValueError):
        reconciliation_plan_fixture(
            projection.model_copy(update={"profile_id": UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")})
        )


def test_empty_history_is_an_exportable_empty_review() -> None:
    plan = reconciliation_plan_fixture(
        ModeloReconciliationListProjection(profile_id=_PROFILE, reconciliation_count=0, reconciliations=())
    )
    assert len(plan.value_cells) == 34
    assert plan.formula_cells == ()


def test_human_review_leads_with_localized_facts_and_keeps_full_identity_in_references() -> None:
    projection = reconciliation_projection_fixture()
    plan = build_modelo_reconciliation_export_plan(
        projection,
        publication_id=UUID(int=1),
        exported_at=datetime(2026, 10, 7, tzinfo=UTC),
        label=ReconciliationWorkbookLabels(OutputLanguage.EN),
    )
    cells = {(cell.address.tab, cell.address.a1): cell.value for cell in plan.value_cells}
    assert cells[TabName.FORM, "A2"] == "Reconciliation R-aaaaaaaa"
    assert cells[TabName.FORM, "B2"] == "2026-03-10 12:00 UTC"
    assert cells[TabName.FORM, "F2"] == "Differences found"
    assert cells[TabName.FORM, "G2"] == "Filing receipt"
    assert cells[TabName.DETALLE, "A2"] == "R-aaaaaaaa"
    assert cells[TabName.DETALLE, "B2"] == "Filed total"
    assert cells[TabName.DETALLE, "C2"] == "total_ingresar"
    assert cells[TabName.PROVENANCE, "B2"] == projection.reconciliations[0].event_id
    assert cells[TabName.PROVENANCE, "I2"] == projection.reconciliations[0].work_unit_id
    assert all(len(str(cell.value)) < 64 for cell in plan.value_cells if cell.address.tab is TabName.FORM)
    widths = {width.column: width.width for width in plan.column_widths if width.tab is TabName.FORM}
    assert widths[3] < widths[1]
    assert len(widths) == 9
