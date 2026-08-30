"""Locale f-string registrations cover every bounded domain enum member."""

import pytest

from cadrumo.domain.contribuyente.renta_codes import FiscalResidency
from cadrumo.domain.deadlines.models import LegalEntityForm

from .. import get_registered_keys

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_fstring_registry_covers_all_legal_entity_form_members() -> None:
    """Every LegalEntityForm member has a registered locale key."""
    keys = get_registered_keys()
    missing = [
        f"wizard.setup.taxpayer-type.legal-entity-form.choices.{member.value.replace('_', '-')}.label"
        for member in LegalEntityForm
        if f"wizard.setup.taxpayer-type.legal-entity-form.choices.{member.value.replace('_', '-')}.label" not in keys
    ]
    assert not missing, (
        f"LegalEntityForm members not covered by the f-string registry: {missing}\n"
        "Add the missing values to _fstring_registry._build_registrations()."
    )


def test_fstring_registry_covers_all_fiscal_residency_members() -> None:
    """Every FiscalResidency member has a registered locale key."""
    keys = get_registered_keys()
    missing = [
        f"wizard.setup.residence.fiscal-residency.choices.{member.value.replace('_', '-')}.label"
        for member in FiscalResidency
        if f"wizard.setup.residence.fiscal-residency.choices.{member.value.replace('_', '-')}.label" not in keys
    ]
    assert not missing, (
        f"FiscalResidency members not covered by the f-string registry: {missing}\n"
        "Add the missing values to _fstring_registry._build_registrations()."
    )
