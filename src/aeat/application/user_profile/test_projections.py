"""Tests for canonical user-profile projection helpers."""

from __future__ import annotations

import pytest

from ...domain.deadlines._models import IVARegime
from ...domain.user_profile import UserProfileFact, UserProfileRecord
from . import (
    facts_to_values,
    projection_for_autonomo,
    record_to_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_facts_to_values_translates_paths_through_schema_selectors() -> None:
    facts = (
        UserProfileFact(path="identity.tax_id", value="12345678Z"),
        UserProfileFact(path="contact.notes", value=None),
    )
    values = facts_to_values(facts)
    assert values["tax.id"] == "12345678Z"


def test_record_to_values_uses_schema_model_selectors() -> None:
    record = UserProfileRecord(
        profile_id="operator",
        display_name="Operator",
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )
    assert record_to_values(record)["tax.id"] == "12345678Z"


def test_projection_for_autonomo_round_trips_iva_regime_through_descriptor() -> None:
    record = UserProfileRecord(
        profile_id="operator",
        display_name="Operator",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
        ),
    )
    profile = projection_for_autonomo(record)
    assert profile.tax_id == "12345678Z"
    assert profile.iva_regime is IVARegime.GENERAL


def test_projection_for_autonomo_accepts_a_flat_mapping_directly() -> None:
    profile = projection_for_autonomo({"tax.id": "X9876543A", "iva.regime": "GENERAL"})
    assert profile.tax_id == "X9876543A"
    assert profile.iva_regime is IVARegime.GENERAL


def test_projection_for_autonomo_uses_defaults_when_record_is_blank() -> None:
    record = UserProfileRecord(profile_id="operator", display_name="Operator", facts=())
    profile = projection_for_autonomo(record, tax_id_default="Z0000000Z")
    assert profile.tax_id == "Z0000000Z"
    assert profile.iva_regime is IVARegime.GENERAL


def test_projection_for_autonomo_carries_section_prefixed_withholding_facts() -> None:
    """A record whose facts live under section-prefixed schema paths
    (irpf.*, withholding.*) must project those values onto the
    AutonomoProfile.

    These fields' schema model_selectors drop the section prefix
    (``irpf.professional_income_withholding_ge_70pct`` ->
    ``professional_income_withholding_ge_70pct``). The selector-aliased
    projection then loses the value because the bare key has no wizard
    catalogue entry. ``projection_for_autonomo`` must read the
    canonical schema paths so an edited fact reaches the deadline
    engine — this is the read-snapshot contract ``overview explain``
    depends on.
    """

    record = UserProfileRecord(
        profile_id="operator",
        display_name="Operator",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(
                path="irpf.professional_income_withholding_ge_70pct",
                value=True,
            ),
            UserProfileFact(path="irpf.uses_objective_estimation", value=True),
            UserProfileFact(path="withholding.has_employees", value=True),
        ),
    )
    profile = projection_for_autonomo(record)
    assert profile.professional_income_withholding_ge_70pct is True
    assert profile.uses_objective_estimation_irpf is True
    assert profile.has_employees is True
