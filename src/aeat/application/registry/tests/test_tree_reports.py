"""Tests for application registry tree report models."""

from __future__ import annotations

from typing import TypedDict

import pytest
from pydantic import ValidationError

from .. import RegistryRevisionDetailReport, RegistryWorkbookParityDetailReport

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class _WorkbookParityPayload(TypedDict, total=False):
    """Partial payload for RegistryWorkbookParityDetailReport."""

    id: str
    workbook_source: str
    formula_coverage: str
    runner_required: bool
    output_cell_count: int


class _RevisionDetailPayload(TypedDict, total=False):
    """Partial payload for RegistryRevisionDetailReport."""

    modelo: str
    revision: str
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    export_layout_ids: tuple[str, ...]
    export_layout_count: int
    export_record_count: int
    export_field_count: int
    deadline_window_count: int
    deadline_periods: tuple[str, ...]
    relation_ids: tuple[str, ...]
    relation_count: int
    relation_dependency_roles: tuple[str, ...]
    filing_schedule_ids: tuple[str, ...]
    filing_schedule_count: int
    portal_guard_policy_ids: tuple[str, ...]
    workbook_parity: tuple[RegistryWorkbookParityDetailReport, ...]
    support_removal_decision_count: int


def _workbook_parity_report(**updates: object) -> RegistryWorkbookParityDetailReport:
    base: _WorkbookParityPayload = {
        "id": "workbook-parity-1",
        "workbook_source": "aeat-dr-303-2025",
        "formula_coverage": "record_design_layout",
        "runner_required": False,
        "output_cell_count": 1,
    }
    payload: _WorkbookParityPayload = {**base, **updates}  # type: ignore[typeddict-unknown-key]
    return RegistryWorkbookParityDetailReport(**payload)


def _revision_detail_report(**updates: object) -> RegistryRevisionDetailReport:
    base: _RevisionDetailPayload = {
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
    payload: _RevisionDetailPayload = {**base, **updates}  # type: ignore[typeddict-unknown-key]
    return RegistryRevisionDetailReport(**payload)


@pytest.mark.parametrize(
    "field_update",
    (
        {"legal_refs": ("",)},
        {"source_refs": ("",)},
        {"export_layout_ids": ("bad id",)},
    ),
)
def test_revision_detail_report_rejects_invalid_registry_ref_ids(field_update: _RevisionDetailPayload) -> None:
    with pytest.raises(ValidationError, match=next(iter(field_update))):
        _revision_detail_report(**field_update)


@pytest.mark.parametrize(
    "field_update",
    (
        {"id": ""},
        {"workbook_source": "bad source"},
    ),
)
def test_workbook_parity_detail_report_rejects_invalid_registry_ref_ids(field_update: _WorkbookParityPayload) -> None:
    with pytest.raises(ValidationError, match=next(iter(field_update))):
        _workbook_parity_report(**field_update)
