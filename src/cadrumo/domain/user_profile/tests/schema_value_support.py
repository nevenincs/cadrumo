"""Schema-only profile values shared by domain profile tests.

These helpers depend only on core and domain declarations.  Capsule creation,
persistence, and application completeness checks belong to outward test seams.
"""

from __future__ import annotations

from collections.abc import Mapping

from ....core.external_constants import PROVENANCE_SOURCE_MANUAL_CLI
from ..schema import NUMERIC_PROFILE_FIELD_TYPES, ProfileFieldDefinition, ProfileFieldType
from ..values import UserProfileFactValue

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


_TAX_AXIS_PLACEHOLDERS: Mapping[str, UserProfileFactValue] = {
    "tax_residence.ccaa": "madrid",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": False,
    "iva.cash_accounting_regime_enrolled": False,
    "iva.voluntary_sii_enrolled": False,
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": False,
    "taxpayer_type.entity_type": "natural_person",
    "taxpayer_type.irpf_income_categories": "actividad_economica",
    "irpf.estimation_regime": "directa_normal",
    # Stated, not defaulted: an unstated large-company condition selects
    # neither Modelo 303 cadence, so readiness refuses the quarterly return.
    "censo.large_company": False,
}
# The domain layer cannot read a persona, and these only fill the schema's required axes for an unrelated test.

REQUIRED_PROFILE_PLACEHOLDERS: Mapping[str, UserProfileFactValue] = {
    "identity.name": "Test Operator",
    "identity.surnames": "Test Operator",
    "activities.description": "economic activity",
    "provenance.source": PROVENANCE_SOURCE_MANUAL_CLI,
    **_TAX_AXIS_PLACEHOLDERS,
}


__all__ = ["REQUIRED_PROFILE_PLACEHOLDERS", "schema_valid_placeholder"]
