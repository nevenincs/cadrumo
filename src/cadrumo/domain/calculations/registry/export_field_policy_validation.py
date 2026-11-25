"""Validate optional policy and wire metadata on declared export fields."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .errors import RegistryValidationError
from .export_value_policy import ExportValuePolicy
from .schema_base import ZERO_PADDED_EXPORT_DATA_TYPES

if TYPE_CHECKING:
    from .schema_exports import ExportFieldDefinition


def validate_export_field_policy_metadata(field: ExportFieldDefinition) -> None:
    """Refuse policy, marker or period metadata incompatible with the field."""
    if field.minimum_year is not None and field.value_policy is not ExportValuePolicy.FOUR_DIGIT_YEAR:
        raise RegistryValidationError("minimum_year requires the four-digit-year value policy")
    _validate_presence_marker(field)
    if (field.scheme_period_part == "period_type") != (field.scheme_period_type is not None):
        raise RegistryValidationError(
            f"export field {field.id!r} must declare a scheme period type exactly on a period-type row",
        )
    if field.absent_fill is not None and field.data_type not in ZERO_PADDED_EXPORT_DATA_TYPES:
        raise RegistryValidationError(f"export field {field.id!r} declares an absent fill on a non-numeric slot")


def _validate_presence_marker(field: ExportFieldDefinition) -> None:
    if field.presence_marker is not None and (
        (field.producer_key is None and field.computed_key is None)
        or field.data_type != "text"
        or field.length != len(field.presence_marker)
        or not field.presence_marker.strip()
    ):
        raise RegistryValidationError(
            f"export field {field.id!r} declares a presence marker outside a text slot of the marker's width "
            "fed by a producer fact or a computed marker",
        )
