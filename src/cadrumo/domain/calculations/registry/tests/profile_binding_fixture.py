"""A profile-sourced binding for tests that prove a manual-input or previous-filing reader ignores other families."""

from __future__ import annotations

from ..schema import BindingDefinition


def tax_residence_profile_binding() -> BindingDefinition:
    return BindingDefinition.model_validate(
        {
            "id": "renta-profile-tax-residence-ccaa",
            "provider": {
                "kind": "profile",
                "profile_model": "TaxResidenceProfile",
                "field": "ccaa",
                "xsd_attribute": "codigoCADeclaracion",
                "dictionary_field": "ZCCAD",
            },
            "value": {
                "data_type": "enum",
                "channel": "enum",
                "typed_enum": "CCAA",
            },
            "aggregation": {
                "op": "copy",
            },
            "legal_refs": ("orden-hac-277-2026:art-3",),
            "source_refs": ("aeat-dr-100-2025-dictionary",),
        },
    )
