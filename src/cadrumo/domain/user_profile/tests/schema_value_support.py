"""Schema-only profile values shared by domain profile tests.

These helpers depend only on core and domain declarations.  Capsule creation,
persistence, and application completeness checks belong to outward test seams.
"""

from __future__ import annotations

from collections.abc import Mapping

from ....core.external_constants import PROVENANCE_SOURCE_MANUAL_CLI
from ..schema import NUMERIC_PROFILE_FIELD_TYPES, ProfileFieldDefinition, ProfileFieldType
from ..values import UserProfileFactValue
from .general_regime_facts import GENERAL_REGIME_NATURAL_PERSON_FACTS

# This is a stable, schema-valid test identifier.  Keep test data independent
# of the registry authority so importing schema-only fixtures remains pure.
_PLACEHOLDER_TAX_ID = "12345678Z"
_PLACEHOLDER_DATE = "1990-01-01"
_PLACEHOLDER_BOOLEAN = False


def schema_valid_placeholder(field: ProfileFieldDefinition) -> str | bool:
    """Return a value admitted by ``field`` for an unrelated test axis."""
    if field.enum_values:
        return field.enum_values[0]
    if field.key == "tax_id":
        return _PLACEHOLDER_TAX_ID
    if field.type in NUMERIC_PROFILE_FIELD_TYPES:
        return _numeric_placeholder(field)
    if field.type is ProfileFieldType.DATE:
        return _PLACEHOLDER_DATE
    if field.type is ProfileFieldType.BOOLEAN:
        return _PLACEHOLDER_BOOLEAN
    return "placeholder"


def _numeric_placeholder(field: ProfileFieldDefinition) -> str:
    """Return an in-range numeric filler for ``field``."""
    if field.minimum is not None:
        return str(field.minimum)
    if field.maximum is not None and field.maximum < 1:
        return str(field.maximum)
    return "1"


REQUIRED_PROFILE_PLACEHOLDERS: Mapping[str, UserProfileFactValue] = {
    "identity.name": "Test Operator",
    "identity.surnames": "Test Operator",
    "activities.description": "economic activity",
    "provenance.source": PROVENANCE_SOURCE_MANUAL_CLI,
    **{fact.path: fact.value for fact in GENERAL_REGIME_NATURAL_PERSON_FACTS},
}


__all__ = ["REQUIRED_PROFILE_PLACEHOLDERS", "schema_valid_placeholder"]
