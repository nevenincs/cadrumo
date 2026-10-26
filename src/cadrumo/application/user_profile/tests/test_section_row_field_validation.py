"""The canonical row writer's field validation is reusable before private reads."""

from __future__ import annotations

import pytest

from ....domain.calculations.registry.authority import bundled_indexed_authority
from ....domain.user_profile.errors import ProfileSchemaValidationError
from ..section_rows import validate_profile_repeatable_row_fields

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_declared_row_fields_refuse_mistyped_field_with_available_vocabulary() -> None:
    with bundled_indexed_authority().operation() as operation:
        section = operation.profile_schema().section("activities")
        with pytest.raises(ProfileSchemaValidationError) as caught:
            validate_profile_repeatable_row_fields(section, values={"descripcion": "Unknown field"})

    assert caught.value.context is not None
    assert caught.value.context["unknown"] == "descripcion"
    assert "description" in str(caught.value.context["fields"])


def test_row_update_cannot_assign_and_clear_the_same_declared_field() -> None:
    with bundled_indexed_authority().operation() as operation:
        section = operation.profile_schema().section("activities")
        with pytest.raises(ProfileSchemaValidationError) as caught:
            validate_profile_repeatable_row_fields(
                section, values={"description": "Changed"}, clear_fields=("description",)
            )

    assert caught.value.context is not None
    assert caught.value.context["fields"] == "description"
