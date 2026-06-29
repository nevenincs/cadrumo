"""CLI guidance for date-valued registry bindings."""

from __future__ import annotations

import pytest

from ....core.resources import resources
from ....domain.calculations.registry import RegistryValidationError, revision_date_binding_ids
from .._modelo import _missing_binding_guidance

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_missing_date_binding_guidance_points_to_profile_not_binding_override() -> None:
    """M100 birth date is a real date binding and must not suggest --binding."""

    snapshot = resources().modelos.authority.snapshot("100", filing_year=2025, period="0A")
    binding_id = "renta-2025-profile-taxpayer-birth-date"
    assert binding_id in revision_date_binding_ids(snapshot.revision)

    error = RegistryValidationError(
        f"date_binding {binding_id!r} has no supplied value; required by age_at_year_end",
        translated_message="errors.calc.date_binding_value_missing",
        context={"binding_id": binding_id},
    )

    guidance = _missing_binding_guidance(error, "no-such-work-unit")

    assert binding_id in guidance
    assert "active profile" in guidance
    assert "bindings list --missing" in guidance
    assert "--binding KEY=VALUE" not in guidance
