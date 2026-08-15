"""Conditional completeness across the taxpayer-type axis.

These properties were proven through the non-interactive ``config profile
create`` surface until that path was retired. The validation itself is
unchanged and still live; only the place it could be observed went away, so
the coverage moved here rather than being dropped with the CLI path.

What is asserted here is deliberately narrow: which facts a taxpayer type
makes required, and which it does not. The sibling completeness modules cover
the IRNR and IVA blocks; the legal-entity form and the attribution entity had
no home outside the retired CLI tests.
"""

from __future__ import annotations

import pytest

from ... import wizard as _wizard  # noqa: F401 - registers compiled profile keys
from .._keys_validation import validate_profile_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_LEGAL_ENTITY_VALUES = {
    "identity.tax_id": "B66012345",
    "identity.legal_name": "Branch Legal SL",
    "tax_residence.jurisdiction_scope": "common_regime",
    "taxpayer_type.entity_type": "legal_entity",
    "activities.description": "asesoria",
}


def test_legal_entity_without_a_legal_form_is_not_filing_grade() -> None:
    """A legal entity must declare its recognised form to be complete.

    The schema covers the field's shape elsewhere -- that its enum spans the
    recognised forms -- which is a different question from whether omitting it
    is refused. This asserts the refusal.
    """
    result = validate_profile_values(_LEGAL_ENTITY_VALUES)

    assert "taxpayer_type.legal_entity_form" in result.missing_required


def test_a_declared_legal_form_satisfies_the_requirement() -> None:
    """Anti-tautology partner: the path is absent once the form is supplied.

    Without this, the assertion above would still pass if the validator
    reported every taxpayer-type path as missing regardless of input.
    """
    result = validate_profile_values(
        {**_LEGAL_ENTITY_VALUES, "taxpayer_type.legal_entity_form": "sl"}
    )

    assert "taxpayer_type.legal_entity_form" not in result.missing_required


def test_attribution_entity_is_never_asked_for_spouse_facts() -> None:
    """An attribution entity has no spouse, and must not be asked to invent one.

    The IRNR and IVA completeness modules exercise the natural-person and
    legal-entity axes; nothing exercised this one, so a regression demanding a
    spouse fact from an attribution entity would have gone unnoticed.
    """
    result = validate_profile_values(
        {
            "identity.tax_id": "E66012345",
            "identity.legal_name": "Comunidad de Bienes",
            "tax_residence.jurisdiction_scope": "common_regime",
            "taxpayer_type.entity_type": "attribution_entity",
            "activities.description": "arrendamiento",
        }
    )

    spouse_paths = [path for path in result.missing_required if path.startswith("spouse.")]
    assert spouse_paths == []
