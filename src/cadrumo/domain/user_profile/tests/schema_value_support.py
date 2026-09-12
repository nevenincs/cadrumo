"""Schema-only profile values shared by domain profile tests.

These helpers depend only on core and domain declarations.  Capsule creation,
persistence, and application completeness checks belong to outward test seams.
"""

from __future__ import annotations

from collections.abc import Mapping

from ....core.external_constants import PROVENANCE_SOURCE_MANUAL_CLI
from ...calculations.registry.tax_id_runtime import runtime_nif_check_letter
from ...deadlines.models import IVARegime
from ..schema import NUMERIC_PROFILE_FIELD_TYPES, ProfileFieldDefinition, ProfileFieldType

_PLACEHOLDER_TAX_ID = f"12345678{runtime_nif_check_letter(12345678)}"
_PLACEHOLDER_DATE = "1990-01-01"
_PLACEHOLDER_BOOLEAN = "false"


def schema_valid_placeholder(field: ProfileFieldDefinition) -> str:
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


REQUIRED_PROFILE_PLACEHOLDERS: Mapping[str, str] = {
    "identity.name": "Test Operator",
    "identity.surnames": "Test Operator",
    "tax_residence.ccaa": "madrid",
    "tax_residence.jurisdiction_scope": "common_regime",
    "activities.description": "economic activity",
    "iva.regime": IVARegime.GENERAL,
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
    "provenance.source": PROVENANCE_SOURCE_MANUAL_CLI,
    "taxpayer_type.entity_type": "natural_person",
    "taxpayer_type.irpf_income_categories": "actividad_economica",
    "irpf.estimation_regime": "directa_normal",
}


__all__ = ["REQUIRED_PROFILE_PLACEHOLDERS", "schema_valid_placeholder"]
