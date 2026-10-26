"""Independent fixture-shape checks for the PROFILE-01 lifecycle scenario."""

from __future__ import annotations

import pytest

from ..scenario import build_profile_row_lifecycle_scenario

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_repeatable_row_scenario_has_a_clearable_fact_and_a_selector_backed_survivor() -> None:
    """The one shared input is sufficient to distinguish clear from removal."""
    scenario = build_profile_row_lifecycle_scenario()

    assert scenario.section == "activities"
    assert scenario.required_field == "description"
    assert scenario.clearable_field == "cnae"
    assert scenario.selector_field == "iae_epigraph"
    assert [field for field, _value in scenario.add_values()] == ["description", "cnae", "iae_epigraph"]
    assert scenario.path("7", scenario.selector_field) == "activities.7.iae_epigraph"


@pytest.mark.parametrize("row_key", ("", "base", "-1", "one"))
def test_scenario_refuses_non_numeric_repeatable_row_identity(row_key: str) -> None:
    """Acceptance cannot accidentally turn display labels or positions into row identity."""
    scenario = build_profile_row_lifecycle_scenario()

    with pytest.raises(ValueError, match="row identity"):
        scenario.path(row_key, scenario.required_field)
