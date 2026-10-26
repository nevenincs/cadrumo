"""Locale f-string registrations cover every bounded domain enum member."""

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.entity_type import legal_entity_form_tokens
from cadrumo.domain.calculations.registry.renta_codes_catalogue import fiscal_residency_choices

from ..fstring_registry import get_registered_keys

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_fstring_registry_covers_all_legal_entity_form_members() -> None:
    """Every LegalEntityForm member has a registered locale key."""
    keys = get_registered_keys()
    with bundled_indexed_authority().operation() as operation:
        values = tuple(member.value for member in legal_entity_form_tokens(authority=operation))
    missing = [
        f"wizard.setup.taxpayer-type.legal-entity-form.choices.{value.replace('_', '-')}.label"
        for value in values
        if f"wizard.setup.taxpayer-type.legal-entity-form.choices.{value.replace('_', '-')}.label" not in keys
    ]
    assert not missing, (
        f"LegalEntityForm members not covered by the f-string registry: {missing}\n"
        "Add the missing values to _fstring_registry._build_registrations()."
    )


def test_fstring_registry_covers_all_fiscal_residency_members() -> None:
    """Every FiscalResidency member has a registered locale key."""
    keys = get_registered_keys()
    with bundled_indexed_authority().operation() as operation:
        values = tuple(member.value for member in fiscal_residency_choices(authority=operation))
    missing = [
        f"wizard.setup.residence.fiscal-residency.choices.{value.replace('_', '-')}.label"
        for value in values
        if f"wizard.setup.residence.fiscal-residency.choices.{value.replace('_', '-')}.label" not in keys
    ]
    assert not missing, (
        f"FiscalResidency members not covered by the f-string registry: {missing}\n"
        "Add the missing values to _fstring_registry._build_registrations()."
    )
