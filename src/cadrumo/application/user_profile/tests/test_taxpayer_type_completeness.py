"""Conditional completeness across the taxpayer-type axis.

This property was proven through the non-interactive ``config profile create``
surface until that path was retired. The validation itself is unchanged and
still live; only the place it could be observed went away, so the coverage
moved here rather than being dropped with the CLI path.

The sibling completeness modules exercise the natural-person and legal-entity
axes for the IRNR and IVA blocks. Nothing exercised the attribution entity, so
a regression demanding a spouse fact from an entity that cannot have one would
have gone unnoticed.
"""

from __future__ import annotations

import pytest

from cadrumo.application.user_profile.keys_validation import validate_profile_values

from ... import wizard as _wizard  # noqa: F401 - registers compiled profile keys

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SPOUSE_PREFIX = "renta_spouse."


def test_attribution_entity_is_never_asked_for_spouse_facts() -> None:
    """An attribution entity has no spouse and must not be asked to invent one."""
    result = validate_profile_values(
        {
            "identity.tax_id": "E66012345",
            "identity.legal_name": "Comunidad de Bienes",
            "tax_residence.jurisdiction_scope": "common_regime",
            "taxpayer_type.entity_type": "attribution_entity",
            "activities.description": "arrendamiento",
        }
    )

    assert [path for path in result.missing_required if path.startswith(_SPOUSE_PREFIX)] == []


def test_a_joint_declaration_does_demand_a_spouse_fact() -> None:
    """Anti-tautology partner: the filter above can match, so its emptiness means something.

    Without this, the assertion above would pass against any prefix that never
    appears -- which is exactly the defect it had when first written, filtering
    on ``spouse.`` while the schema names these paths ``renta_spouse.``.
    """
    result = validate_profile_values(
        {
            "identity.tax_id": "12345678Z",
            "tax_residence.jurisdiction_scope": "common_regime",
            "taxpayer_type.entity_type": "natural_person",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "renta_filing.declaration_type": "2",
        }
    )

    assert [path for path in result.missing_required if path.startswith(_SPOUSE_PREFIX)] != []
