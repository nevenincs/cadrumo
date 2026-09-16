"""Published-authority proof that storage-bounded facts keep temporal projection."""

from __future__ import annotations

from datetime import date

import pytest

from ...authority import bundled_indexed_authority
from ...schema_base import DateAxis
from ...schema_references import TemporalProjectionDirection
from ..resolution import MappingFactQuery

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_supportless_fact_with_coverage_end_still_projects_forward_from_published_authority() -> None:
    # The taxonomy's authored valid_to marks the last reviewed filing year, not a
    # statutory repeal, so the resolver must keep carrying it into later years.
    with bundled_indexed_authority().operation() as operation:
        resolved = operation.resolve_governed_fact(
            MappingFactQuery(
                fact_id="irpf-ledger-category-taxonomy",
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=date(2026, 12, 31),
            ),
        )

    assert resolved.authored_valid_to == date(2025, 12, 31)
    assert resolved.projection_direction is TemporalProjectionDirection.FORWARD
    assert resolved.projected_from_date == date(2025, 12, 31)
    assert resolved.source_variant_id == "irpf-ledger-category-taxonomy:2025"
