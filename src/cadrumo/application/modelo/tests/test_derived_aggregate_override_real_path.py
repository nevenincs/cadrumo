"""Inward policy coverage for refusing writes to derived Modelo aggregates.

The real profile and calculation path is covered by the outer persistence test
with the same name. This application test keeps the policy seam independent from
encrypted storage and profile-registration integration.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.application.user_profile.validation import reject_invalid_profile_facts
from cadrumo.domain.user_profile.errors import ProfileSchemaValidationError
from cadrumo.domain.user_profile.values import UserProfileFact

from ....domain.calculations.registry.tests.published_authority import published_profile_schema

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BUCKET = "51300000-0000-4000-8000-000000000513"
_DERIVED_PATH = "renta_family.descendientes_minimos_aggregate_2024"
_SENTINEL = Decimal("4321.37")


def test_operator_write_door_refuses_a_value_at_the_derived_aggregate_path() -> None:
    """A derived aggregate path is rejected at the application write policy."""

    with pytest.raises(ProfileSchemaValidationError) as refusal:
        reject_invalid_profile_facts(
            _BUCKET,
            (UserProfileFact(path=_DERIVED_PATH, value=_SENTINEL),),
            require_complete=False,
            schema=published_profile_schema(),
        )

    assert _DERIVED_PATH in str(refusal.value)
    assert "is computed by the engine" in str(refusal.value)
