"""A refused inventory operation always names the sentence of its own reason."""

from __future__ import annotations

from uuid import UUID

import pytest

from cadrumo.application.inventory.errors import (
    InventoryActividadConflictError,
    InventoryActividadNotFoundError,
    InventoryServiceInputError,
)
from cadrumo.application.inventory.registered_executor import _refusal_for_error
from cadrumo.application.inventory.registered_requests import InventoryInspectRequest

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_REQUEST = InventoryInspectRequest(
    profile_id=UUID("28282828-2828-4828-8828-282828282828"), actividad_id="A1", year=2025
)
_FAMILY = "application.inventory.service.errors."


@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (
            InventoryActividadConflictError(
                translated_message=f"{_FAMILY}activity_conflict", context={"actividad_id": "A1", "year": "2025"}
            ),
            "activity_conflict",
        ),
        (
            InventoryActividadNotFoundError(
                translated_message=f"{_FAMILY}activity_not_found", context={"actividad_id": "A1", "year": "2025"}
            ),
            "activity_not_found",
        ),
        (
            InventoryServiceInputError(translated_message="errors.refused.refused_profile_inventory_validation"),
            "inventory_validation",
        ),
    ],
)
def test_the_reason_key_is_the_family_key_of_the_reason(error: Exception, reason: str) -> None:
    refusal = _refusal_for_error(request=_REQUEST, error=error)

    assert refusal is not None
    assert refusal.reason == reason
    assert refusal.reason_key == f"{_FAMILY}{reason}"
