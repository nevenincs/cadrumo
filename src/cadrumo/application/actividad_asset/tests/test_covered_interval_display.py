"""A claim interval is half-open, and every read model that shows one also states its last covered day.

Figures use 2,000.00 at 26% linear from 1 January 2025.  A baja on 30 June 2026
keeps 181 days of that year and, once removed, leaves 1 July - 31 December 2026
claimable.
"""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from cadrumo.application.actividad_asset.activity_asset_read_models import (
    ActivityAssetClaimableInterval,
    ActivityAssetPlanClaim,
)

from .test_baja_correction import _ASSET, _disposed, _without_baja

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_a_claim_of_a_full_year_reads_through_the_last_day_of_the_year() -> None:
    operations, _, _ = _disposed()

    row = {item.tax_year: item for item in operations.plan(_ASSET)}[2025]

    (claim,) = row.claims
    assert (claim.covered_from, claim.covered_until, claim.covered_through) == (
        date(2025, 1, 1),
        date(2026, 1, 1),
        date(2025, 12, 31),
    )


def test_the_shortened_claim_ends_the_day_of_the_baja_and_the_gap_resumes_the_next_day() -> None:
    operations, _, baja = _disposed()
    operations.correct(_without_baja(baja))

    row = {item.tax_year: item for item in operations.plan(_ASSET)}[2026]

    (claim,) = (item for item in row.claims if item.effective)
    assert (claim.covered_until, claim.covered_through) == (date(2026, 7, 1), date(2026, 6, 30))
    (gap,) = row.claimable_intervals
    assert (gap.covered_from, gap.covered_until, gap.covered_through) == (
        date(2026, 7, 1),
        date(2027, 1, 1),
        date(2026, 12, 31),
    )


def test_a_read_model_refuses_an_inclusive_end_that_is_not_the_day_before_the_boundary() -> None:
    with pytest.raises(ValidationError, match="covered_through"):
        ActivityAssetClaimableInterval(
            covered_from=date(2026, 7, 1),
            covered_until=date(2027, 1, 1),
            covered_through=date(2027, 1, 1),
        )
    assert ActivityAssetPlanClaim.model_fields["covered_through"].is_required()
