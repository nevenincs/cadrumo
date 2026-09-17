"""Published-authority proof that an open-ended fact keeps forward projection."""

from __future__ import annotations

from datetime import date

import pytest

from ...authority import bundled_indexed_authority
from ...schema_base import DateAxis
from ...schema_references import TemporalProjectionDirection
from ..resolution import MappingFactQuery

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_a_coverage_marked_fact_carries_its_newest_variant_forward_from_published_authority() -> None:
    # The taxonomy declares no end: its last reviewed year is not a statutory
    # repeal, so the published resolver carries it past the authored horizon.
    with bundled_indexed_authority().operation() as operation:
        support = operation.supported_filing_years()
        resolved = operation.resolve_governed_fact(
            MappingFactQuery(
                fact_id="irpf-ledger-category-taxonomy",
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=date(support.horizon + 1, 12, 31),
            ),
        )

    assert resolved.authored_valid_to is None
    assert resolved.projection_direction is TemporalProjectionDirection.FORWARD
    assert resolved.projected_from_date == date(support.horizon, 12, 31)
    assert resolved.source_variant_id == "irpf-ledger-category-taxonomy:2025"
