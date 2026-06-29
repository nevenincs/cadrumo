"""Tests for canonical user-profile projection helpers."""

from __future__ import annotations

import pytest

from ....domain.deadlines._models import IVARegime
from ....domain.user_profile import UserProfileFact, UserProfileRecord
from ...wizard import _catalogue as _wizard_catalogue  # noqa: F401  (registration side effect)
from .. import (
    facts_to_values,
    projection_for_taxpayer,
    record_to_values,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


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


def test_projection_for_taxpayer_round_trips_iva_regime_through_descriptor() -> None:
    record = UserProfileRecord(
        profile_id="operator",
        display_name="Operator",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
        ),
    )
    profile = projection_for_taxpayer(record)
    assert profile.tax_id == "12345678Z"
    assert profile.iva_regime is IVARegime.GENERAL


def test_projection_for_taxpayer_accepts_a_flat_mapping_directly() -> None:
    profile = projection_for_taxpayer({"tax.id": "X9876543A", "iva.regime": "GENERAL"})
    assert profile.tax_id == "X9876543A"
    assert profile.iva_regime is IVARegime.GENERAL


def test_projection_for_taxpayer_uses_defaults_when_record_is_blank() -> None:
    record = UserProfileRecord(profile_id="operator", display_name="Operator", facts=())
    profile = projection_for_taxpayer(record, tax_id_default="Z0000000Z")
    assert profile.tax_id == "Z0000000Z"
    assert profile.iva_regime is IVARegime.GENERAL


def test_projection_for_taxpayer_carries_section_prefixed_withholding_facts() -> None:
    """A record whose facts live under section-prefixed schema paths
    (irpf.*, withholding.*) must project those values onto the
    TaxpayerProfile.

    These fields' schema model_selectors drop the section prefix
    (``irpf.professional_income_withholding_ge_70pct`` ->
    ``professional_income_withholding_ge_70pct``). The selector-aliased
    projection then loses the value because the bare key has no wizard
    catalogue entry. ``projection_for_taxpayer`` must read the
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
    profile = projection_for_taxpayer(record)
    assert profile.professional_income_withholding_ge_70pct is True
    assert profile.uses_objective_estimation_irpf is True
    assert profile.has_employees is True


def test_record_to_values_emits_bare_key_for_third_party_threshold() -> None:
    """contract regression: obligations.third_party_transactions_above_347_threshold
    must appear under the bare key (without 'obligations.' prefix) in the
    record_to_values output so the calendar's _GATING_FIELDS lookup finds it.

    Before the fix, the schema field had no model_selectors and the fact
    path 'obligations.third_party_transactions_above_347_threshold' was
    emitted verbatim, causing the calendar to treat the field as absent and
    emit a false warning even when the operator had declared the value.
    """
    record = UserProfileRecord(
        profile_id="operator",
        display_name="Operator",
        facts=(
            UserProfileFact(
                path="obligations.third_party_transactions_above_347_threshold",
                value=True,
            ),
        ),
    )
    values = record_to_values(record)
    # Must be keyed without the section prefix — that is what the calendar reads.
    assert "third_party_transactions_above_347_threshold" in values
    assert values["third_party_transactions_above_347_threshold"] == "true"
    # The prefixed key must NOT appear (no dual-key emission).
    assert "obligations.third_party_transactions_above_347_threshold" not in values


def test_crypto_abroad_threshold_projects_to_taxpayer_profile() -> None:
    """Modelo 721's threshold is distinct from Modelo 720's foreign-assets fact."""

    record = UserProfileRecord(
        profile_id="operator",
        display_name="Operator",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="obligations.bienes_extranjero_above_threshold", value=False),
            UserProfileFact(path="obligations.monedas_virtuales_extranjero_above_threshold", value=True),
        ),
    )

    values = record_to_values(record)
    profile = projection_for_taxpayer(record)

    assert values["monedas_virtuales_extranjero_above_threshold"] == "true"
    assert "obligations.monedas_virtuales_extranjero_above_threshold" not in values
    assert profile.bienes_extranjero_above_threshold is False
    assert profile.monedas_virtuales_extranjero_above_threshold is True
