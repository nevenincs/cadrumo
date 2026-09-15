"""The cross-period dependency inventory enumerates the periods of the year it scans.

The inventory snapshots one coordinate per declared period of the scanned
filing year. Enumerating the flat tuple in an override year builds a snapshot
for a period the edition does not file that year, and reports a filing blocker
against a coordinate that cannot be filed.
"""

from __future__ import annotations

from typing import Final

import pytest

from ...tests.period_override_authority import authority_with_period_override, pinned_operation_for_authority
from ..cross_period_clean_state import cross_period_dependency_inventory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO: Final = "130"
_REVISION: Final = "2019-y-siguientes"
_YEAR: Final = 2024
_DROPPED: Final = "1T"
_SERVED: Final = ("2T", "3T", "4T")


def test_the_inventory_covers_only_the_periods_the_override_year_serves() -> None:
    authority = authority_with_period_override(
        modelo_id=_MODELO,
        revision_id=_REVISION,
        year=_YEAR,
        periods=_SERVED,
    )
    declared = authority.modelo(_MODELO).revisions[_REVISION].period_selector
    assert declared.periods[0] == _DROPPED, "the fixture must discriminate a flat read"

    inventory = cross_period_dependency_inventory(
        pinned_operation_for_authority(authority),
        filing_year=_YEAR,
        modelos=[_MODELO],
    )

    covered = {str(item.target_period.code) for item in inventory.items}
    assert covered == set(_SERVED)
    assert _DROPPED not in covered
