"""A field holding another row's key declares the section of that row, and the schema refuses an incoherent one."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ....core.classification.policies import SensitivityClass
from ...calculations.registry.tests.published_authority import published_profile_schema
from ..schema import ProfileFieldDefinition, ProfileFieldType, ProfileSchemaDefinition

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _field(key: str, field_type: ProfileFieldType, references_section: str | None = None) -> dict[str, object]:
    return {
        "key": key,
        "type": field_type.value,
        "sensitivity": SensitivityClass.IDENTITY.value,
        "description": f"Synthetic field {key}.",
        "references_section": references_section,
    }


def _schema(*, owner_repeatable: bool, target_repeatable: bool, target: str = "parent") -> dict[str, object]:
    published = published_profile_schema()
    return {
        "id": published.id,
        "version": published.version,
        "title": published.title,
        "snapshot_policy": published.snapshot_policy.value,
        "remove_policy": published.remove_policy.value,
        "sections": (
            {
                "key": "parent",
                "title": "Parent rows",
                "sensitivity": SensitivityClass.IDENTITY.value,
                "repeatable": target_repeatable,
                "fields": (_field("name", ProfileFieldType.STRING),),
            },
            {
                "key": "child",
                "title": "Child rows",
                "sensitivity": SensitivityClass.IDENTITY.value,
                "repeatable": owner_repeatable,
                "fields": (_field("parent_row", ProfileFieldType.INTEGER, target),),
            },
        ),
    }


def test_the_published_schema_declares_the_premises_and_rental_row_references() -> None:
    assert published_profile_schema().row_references() == (
        ("iae_local", "actividad", "activities"),
        ("iae_local_superficie", "local", "iae_local"),
        ("iae_elemento_tributario", "actividad", "activities"),
        ("renta_inmueble", "inmueble_principal", "renta_inmueble"),
        ("renta_arrendamiento", "inmueble", "renta_inmueble"),
    )


def test_a_reference_between_repeatable_sections_is_admitted() -> None:
    schema = ProfileSchemaDefinition.model_validate(_schema(owner_repeatable=True, target_repeatable=True))

    assert schema.row_references() == (("child", "parent_row", "parent"),)
    assert schema.field("parent.name").references_section is None


def test_a_reference_is_held_only_by_an_integer_field() -> None:
    with pytest.raises(ValidationError, match="only on an integer field"):
        ProfileFieldDefinition.model_validate(_field("parent_row", ProfileFieldType.STRING, "parent"))


@pytest.mark.parametrize(
    ("owner_repeatable", "target_repeatable", "target", "refusal"),
    [
        (True, False, "parent", "is not a repeatable section"),
        (True, True, "absent", "is not a repeatable section"),
        (False, True, "parent", "only a repeatable section's row names another row"),
    ],
)
def test_a_reference_outside_repeatable_sections_is_refused(
    owner_repeatable: bool, target_repeatable: bool, target: str, refusal: str
) -> None:
    with pytest.raises(ValidationError, match=refusal):
        ProfileSchemaDefinition.model_validate(
            _schema(owner_repeatable=owner_repeatable, target_repeatable=target_repeatable, target=target)
        )
