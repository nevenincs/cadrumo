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
