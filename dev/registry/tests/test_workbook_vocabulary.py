"""Closed-vocabulary contracts for the workbook parity classification types.

These live beside the harness that owns them rather than under the package
tests: the workbook parity tooling is contributor-only and does not ship, so a
test importing it from ``cadrumo`` asserts a boundary the tree no longer has.
"""

from __future__ import annotations

from enum import StrEnum

import pytest
from pydantic import ValidationError

from ..parity._workbook_parity_models import WorkbookRunnerAvailability
from ..parity._workbook_parity_types import WorkbookKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_WORKBOOK_KIND_VALUES: frozenset[str] = frozenset(
    {
        "formula_form",
        "record_design_layout",
        "validation_hints",
        "static_layout",
        "unsupported_binary_xls",
        "unreadable",
    },
)


def test_workbook_kind_enum_exposes_closed_classification_vocabulary() -> None:
    """Workbook reports expose a closed StrEnum vocabulary to callers."""
    assert issubclass(WorkbookKind, StrEnum)
    assert frozenset(member.value for member in WorkbookKind) == _WORKBOOK_KIND_VALUES
    assert {member.value: str(member) for member in WorkbookKind} == {value: value for value in _WORKBOOK_KIND_VALUES}


def test_workbook_runner_availability_accepts_only_declared_engines() -> None:
    """Runner availability records validate the public engine vocabulary."""
    libreoffice = WorkbookRunnerAvailability(
        status="available",
        engine="libreoffice-headless",
        executable="soffice",
        detail="LibreOffice executable found for local workbook recalculation",
    )
    excel = WorkbookRunnerAvailability(
        status="available",
        engine="excel-com",
        executable="{00024500-0000-0000-C000-000000000046}",
        detail="Excel COM automation is registered for local read-only workbook recalculation",
    )

    assert libreoffice.engine == "libreoffice-headless"
    assert excel.engine == "excel-com"
    with pytest.raises(ValidationError):
        WorkbookRunnerAvailability.model_validate(
            {
                "status": "available",
                "engine": "libreoffice",
                "executable": "libreoffice",
                "detail": "unsupported short engine name",
            },
        )
