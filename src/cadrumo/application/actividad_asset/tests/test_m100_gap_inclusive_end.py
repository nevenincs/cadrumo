"""A Modelo 100 gap states the last day it covers beside its exclusive boundary."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from cadrumo.application.actividad_asset.operation_dtos import (
    ActivityAssetFilingHandoffSnapshot,
    ActivityAssetM100GapSnapshot,
)

from .operations_support import build_operations

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _gap_wire() -> dict[str, Any]:
    handoff = build_operations().filing_handoff(tax_year=2025)
    snapshot = ActivityAssetFilingHandoffSnapshot.from_domain(handoff)
    (gap,) = snapshot.m100_gaps
    return gap.model_dump()


def test_the_gap_serves_the_inclusive_end_beside_the_exclusive_one() -> None:
    gap = _gap_wire()

    assert gap["covered_until"] == date(2026, 1, 1)
    assert gap["covered_through"] == date(2025, 12, 31)


def test_an_inclusive_end_that_is_not_the_day_before_the_boundary_is_refused() -> None:
    wire = _gap_wire()
    wire["covered_through"] = date(2026, 1, 1) + timedelta(days=1)

    with pytest.raises(ValidationError, match="day before covered_until"):
        ActivityAssetM100GapSnapshot.model_validate(wire)
