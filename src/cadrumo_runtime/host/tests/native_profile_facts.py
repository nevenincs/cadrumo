"""Profile answers shared by the native runtime tests that register a general-regime natural person."""

from __future__ import annotations


def native_general_iva_facts(*, surnames: str, description: str) -> dict[str, str]:
    """Return the minimal complete answers of a natural person in the general IVA regime."""
    return {
        "taxpayer_type.entity_type": "natural_person",
        "identity.name": "Native",
        "identity.surnames": surnames,
        "activities.description": description,
        "censo.activity_start_date": "2025-01-01",
        "tax_residence.jurisdiction_scope": "common_regime",
        "iva.regime": "GENERAL",
        "iva.m303_regime_composition": "general",
        "iva.redeme_enrolled": "false",
        "iva.cash_accounting_regime_enrolled": "false",
        "iva.voluntary_sii_enrolled": "false",
        "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
    }
