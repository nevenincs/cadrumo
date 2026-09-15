"""The filing runtime reads the period surface of the year it holds, not the flat tuple.

Both sites carry a filing year: the provider snapshot resolves one from the
revision's own selector, and the subview is built off a snapshot that knows its
year. In an override year the flat tuple still leads with a token the edition
does not file, so a flat read stamps that token onto the filing handoff.
"""

from __future__ import annotations

import pytest

from ....core.period import Period
from ...tests.period_override_authority import (
    DROPPED_PERIOD,
    OVERRIDE_MODELO,
    OVERRIDE_PERIODS,
    OVERRIDE_REVISION,
    OVERRIDE_YEAR,
    override_authority,
)
from ..runtime import _snapshot_for_provider, subview_from_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_the_provider_snapshot_uses_the_period_the_override_year_serves() -> None:
    authority = override_authority()
    modelo = authority.modelo(OVERRIDE_MODELO)

    snapshot = _snapshot_for_provider(
        authority,
        modelo,
        filing_year=OVERRIDE_YEAR,
        period=Period.from_year_and_code(OVERRIDE_YEAR, OVERRIDE_PERIODS[0]),
    )

    assert snapshot.filing_year == OVERRIDE_YEAR
    assert snapshot.revision.id == OVERRIDE_REVISION
    assert snapshot.period == OVERRIDE_PERIODS[0]
    assert snapshot.period != DROPPED_PERIOD


def test_the_subview_declares_the_overridden_year_surface() -> None:
    authority = override_authority()
    snapshot = authority.snapshot(
        OVERRIDE_MODELO,
        filing_year=OVERRIDE_YEAR,
        period=OVERRIDE_PERIODS[0],
        revision_id=OVERRIDE_REVISION,
    )

    subview = subview_from_snapshot(snapshot)

    assert subview.period_selector_periods == OVERRIDE_PERIODS
    assert DROPPED_PERIOD not in subview.period_selector_periods
