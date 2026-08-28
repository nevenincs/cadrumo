"""Tests for application registry tree report models."""

from __future__ import annotations

from typing import TypedDict

import pytest
from pydantic import ValidationError

from ..tree import RegistryRevisionDetailReport, RegistryTreeReport, RegistryWorkbookParityDetailReport

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


_REVISION_INVALID_REF_CASES: tuple[_RevisionDetailPayload, ...] = (
    {"legal_refs": ("",)},
    {"source_refs": ("",)},
    {"export_layout_ids": ("bad id",)},
)

_WORKBOOK_PARITY_INVALID_REF_CASES: tuple[_WorkbookParityPayload, ...] = (
    {"id": ""},
    {"workbook_source": "bad source"},
)


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
        "revision": "2022",
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
    }
    payload: _RevisionDetailPayload = {**base, **updates}  # type: ignore[typeddict-unknown-key]
    return RegistryRevisionDetailReport(**payload)


def test_revision_detail_report_rejects_invalid_registry_ref_ids() -> None:
    for field_update in _REVISION_INVALID_REF_CASES:
        field_name = next(iter(field_update))
        with pytest.raises(ValidationError, match=field_name):
            _revision_detail_report(**field_update)


def test_workbook_parity_detail_report_rejects_invalid_registry_ref_ids() -> None:
    for field_update in _WORKBOOK_PARITY_INVALID_REF_CASES:
        field_name = next(iter(field_update))
        with pytest.raises(ValidationError, match=field_name):
            _workbook_parity_report(**field_update)
_NEGATIVE_REVISION_COUNT_FIELDS = (
    "export_layout_count",
    "export_record_count",
    "export_field_count",
    "deadline_window_count",
    "relation_count",
    "filing_schedule_count",
)


def test_revision_detail_report_rejects_a_negative_inventory_count() -> None:
    """Every revision tally is a ``len()``, so a negative one is incoherent.

    The bound lives here rather than on the CLI payload that renders it, so a
    caller that never builds a JSON envelope inherits the same refusal.
    """
    for field_name in _NEGATIVE_REVISION_COUNT_FIELDS:
        with pytest.raises(ValidationError, match=field_name):
            _revision_detail_report(**{field_name: -1})


def test_workbook_parity_detail_report_rejects_a_negative_output_cell_count() -> None:
    """``output_cell_count`` counts declared output cells and cannot go below zero."""
    with pytest.raises(ValidationError, match="output_cell_count"):
        _workbook_parity_report(output_cell_count=-1)


def test_zero_is_accepted_as_a_real_inventory_count() -> None:
    """The positive control: the bound is ``ge=0``, not ``gt=0``.

    A revision legitimately declares no deadline windows, relations, or filing
    schedules, so a bound rejecting zero would refuse real registry data.
    """
    report = _revision_detail_report(
        deadline_window_count=0,
        relation_count=0,
        filing_schedule_count=0,
    )

    assert report.deadline_window_count == 0
    assert report.relation_count == 0
    assert report.filing_schedule_count == 0
_TREE_INVENTORY_COUNT_FIELDS = (
    "modelo_count",
    "revision_count",
    "legal_reference_count",
    "source_reference_count",
    "casilla_count",
    "formula_count",
    "extraction_profile_count",
    "cross_reference_count",
    "workbook_parity_ref_count",
    "verification_expectation_count",
    "application_link_count",
    "relation_count",
    "filing_schedule_count",
)


def _tree_report(**updates: object) -> RegistryTreeReport:
    """Build a whole-tree report, valid unless an update makes it otherwise."""
    payload: dict[str, object] = {
        "registry_root": "/registry",
        "application_link_surfaces": (),
        "relation_dependency_roles": (),
        "modelos": ("303",),
        "revision_details": (_revision_detail_report(),),
        "verified": True,
    }
    payload.update({field: 0 for field in _TREE_INVENTORY_COUNT_FIELDS})
    payload.update(updates)
    return RegistryTreeReport(**payload)  # type: ignore[arg-type]


def test_tree_report_accepts_a_whole_tree_of_real_tallies() -> None:
    """The positive control: the refusals below are not refusing everything."""
    report = _tree_report(modelo_count=1, casilla_count=117)

    assert report.modelo_count == 1
    assert report.casilla_count == 117


def test_tree_report_rejects_a_negative_inventory_count() -> None:
    """Each whole-tree tally is a ``len()`` or a sum of them, never negative.

    None of these counts is authored in registry TOML; every one is derived at
    report assembly, so a negative value could only come from a defect in the
    assembly itself -- which is exactly what this refuses to pass on.
    """
    for field_name in _TREE_INVENTORY_COUNT_FIELDS:
        with pytest.raises(ValidationError, match=field_name):
            _tree_report(**{field_name: -1})
