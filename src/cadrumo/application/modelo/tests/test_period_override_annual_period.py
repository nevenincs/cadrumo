"""The year-only period chosen for binding readiness comes from that year's surface.

``annual_period_for_year`` picks the first period its covering revision serves
so a snapshot resolves. In an override year the first flat token is a period
the edition does not file, and a snapshot built on it would be refused.
"""

from __future__ import annotations

import pytest

from ...tests.period_override_authority import (
    DROPPED_PERIOD,
    OVERRIDE_MODELO,
    OVERRIDE_PERIODS,
    OVERRIDE_REVISION,
    OVERRIDE_YEAR,
    override_operation,
)
from ..binding_readiness import annual_period_for_year

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_the_annual_period_is_the_first_the_override_year_serves() -> None:
    with override_operation() as operation:
        declared = operation.revision(OVERRIDE_MODELO, OVERRIDE_REVISION).period_selector
        assert declared.periods[0] == DROPPED_PERIOD, "the fixture must discriminate a flat read"

        chosen = annual_period_for_year(operation, modelo=OVERRIDE_MODELO, filing_year=OVERRIDE_YEAR)

    assert chosen == OVERRIDE_PERIODS[0]


def test_a_year_the_override_does_not_name_keeps_the_flat_surface() -> None:
    with override_operation() as operation:
        chosen = annual_period_for_year(operation, modelo=OVERRIDE_MODELO, filing_year=OVERRIDE_YEAR + 1)

    assert chosen == DROPPED_PERIOD
