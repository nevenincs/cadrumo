"""Tests for application registry tree report models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from .. import RegistryRevisionDetailReport, RegistryWorkbookParityDetailReport

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _workbook_parity_report(**updates: object) -> RegistryWorkbookParityDetailReport:
    payload: dict[str, object] = {
        "id": "workbook-parity-1",
        "workbook_source": "aeat-dr-303-2025",
        "formula_coverage": "record_design_layout",
        "runner_required": False,
        "output_cell_count": 1,
    }
    payload.update(updates)
    return RegistryWorkbookParityDetailReport(**payload)


def _revision_detail_report(**updates: object) -> RegistryRevisionDetailReport:
    payload: dict[str, object] = {
        "modelo": "303",
        "revision": "2009-y-siguientes",
        "legal_refs": ("ley-37-1992:art-99",),
        "source_refs": ("aeat-dr-303-2025",),
        "export_layout_ids": ("modelo-303-2025",),
        "export_layout_count": 1,
        "export_record_count": 1,
        "export_field_count": 1,
        "deadline_window_count": 0,
        "deadline_periods": (),
        "relation_ids": (),
        "relation_count": 0,
        "relation_dependency_roles": (),
        "filing_schedule_ids": (),
        "filing_schedule_count": 0,
        "portal_guard_policy_ids": (),
        "workbook_parity": (_workbook_parity_report(),),
        "support_removal_decision_count": 0,
    }
    payload.update(updates)
    return RegistryRevisionDetailReport(**payload)


@pytest.mark.parametrize(
    "field_update",
    (
        {"legal_refs": ("",)},
        {"source_refs": ("",)},
        {"export_layout_ids": ("bad id",)},
    ),
)
def test_revision_detail_report_rejects_invalid_registry_ref_ids(field_update: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match=next(iter(field_update))):
        _revision_detail_report(**field_update)


@pytest.mark.parametrize(
    "field_update",
    (
        {"id": ""},
        {"workbook_source": "bad source"},
    ),
)
def test_workbook_parity_detail_report_rejects_invalid_registry_ref_ids(field_update: dict[str, object]) -> None:
    with pytest.raises(ValidationError, match=next(iter(field_update))):
        _workbook_parity_report(**field_update)
