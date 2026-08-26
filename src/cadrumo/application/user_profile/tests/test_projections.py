"""Tests for canonical user-profile projection helpers."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

import cadrumo.application.wizard.catalogue as _wizard_catalogue  # noqa: F401  (registration side effect)
from cadrumo.application.user_profile.projections import (
    facts_to_values,
    projection_for_taxpayer,
    record_to_effective_facts,
    record_to_path_values,
    record_to_values,
)

from ....domain.deadlines import (
    IrpfEstimationRegime,
    IVARegime,
)
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_UUID = "66666666-6666-4666-8666-666666666666"


def test_facts_to_values_translates_paths_through_schema_selectors() -> None:
    facts = (
        UserProfileFact(path="identity.tax_id", value="12345678Z"),
        UserProfileFact(path="contact.notes", value=None),
    )
    values = facts_to_values(facts)
    assert values["tax.id"] == "12345678Z"


def test_record_to_values_uses_schema_model_selectors() -> None:
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="11111111-1111-4111-8111-111111111111",
        facts=(UserProfileFact(path="identity.tax_id", value="12345678Z"),),
    )
    assert record_to_values(record)["tax.id"] == "12345678Z"


def test_projection_for_taxpayer_round_trips_iva_regime_through_descriptor() -> None:
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="11111111-1111-4111-8111-111111111111",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        ),
    )
    profile = projection_for_taxpayer(record)
    assert profile.tax_id == "12345678Z"
    assert profile.iva_regime is IVARegime.GENERAL


def test_projection_for_taxpayer_uses_no_aplica_for_natural_person_without_activity_or_iva_fact() -> None:
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="11111111-1111-4111-8111-111111111111",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="capital_inmobiliario"),
        ),
    )

    profile = projection_for_taxpayer(record)

    assert profile.tax_id == "12345678Z"
    assert profile.iva_regime is IVARegime.NO_APLICA


def test_projection_for_taxpayer_preserves_explicit_iva_regime_for_natural_person_without_activity() -> None:
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="11111111-1111-4111-8111-111111111111",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="capital_inmobiliario"),
            UserProfileFact(path="iva.regime", value="EXENTO"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        ),
    )

    profile = projection_for_taxpayer(record)

    assert profile.tax_id == "12345678Z"
    assert profile.iva_regime is IVARegime.EXENTO


def test_projection_for_taxpayer_accepts_a_flat_mapping_directly() -> None:
    profile = projection_for_taxpayer(
        {
            "tax.id": "X9876543K",
            "iva.regime": "GENERAL",
            "tax_residence.jurisdiction_scope": "common_regime",
            "iva.m303_regime_composition": "general",
            "iva.redeme_enrolled": "false",
            "iva.cash_accounting_regime_enrolled": "false",
            "iva.voluntary_sii_enrolled": "false",
            "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
        },
    )
    assert profile.tax_id == "X9876543K"
    assert profile.iva_regime is IVARegime.GENERAL


def test_projection_for_taxpayer_uses_defaults_when_record_is_blank() -> None:
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE, profile_id="11111111-1111-4111-8111-111111111111", facts=()
    )
    profile = projection_for_taxpayer(record, tax_id_default="Z0000000M")
    assert profile.tax_id == "Z0000000M"
    assert profile.iva_regime is IVARegime.GENERAL


def test_projection_for_taxpayer_carries_section_prefixed_withholding_facts() -> None:
    """A record whose facts live under section-prefixed schema paths
    (irpf.*, withholding.*) must project those values onto the
    TaxpayerProfile.

    These fields' schema model_selectors drop the section prefix
    (``irpf.art109_activity_income_withholding_ge_70pct`` ->
    ``art109_activity_income_withholding_ge_70pct``). The selector-aliased
    projection then loses the value because the bare key has no wizard
    catalogue entry. ``projection_for_taxpayer`` must read the
    canonical schema paths so an edited fact reaches the deadline
    engine — this is the read-snapshot contract ``overview explain``
    depends on.
    """

    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="11111111-1111-4111-8111-111111111111",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(
                path="irpf.art109_activity_income_withholding_ge_70pct",
                value=True,
            ),
            UserProfileFact(path="irpf.estimation_regime", value="objetiva"),
            UserProfileFact(path="withholding.has_employees", value=True),
        ),
    )
    profile = projection_for_taxpayer(record)
    assert profile.art109_activity_income_withholding_ge_70pct is True
    assert profile.irpf_estimation_regime is IrpfEstimationRegime.OBJETIVA
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
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="11111111-1111-4111-8111-111111111111",
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
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="11111111-1111-4111-8111-111111111111",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
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


def test_projection_for_taxpayer_populates_selector_aliased_direct_reads() -> None:
    """Selector-aliased fields must survive the record projection.

    ``taxpayer_profile_from_mapping`` reads the fiscal-address family at its
    declared ``model_selectors`` alias (``address.cadastral_reference``,
    ``address.is_habitual_vivienda``) while the wizard projection resolves
    path keys. The record branch must therefore feed BOTH key spaces; a
    path-only projection silently blanks this family.
    """
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="11111111-1111-4111-8111-111111111111",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="contact.fiscal_address_cadastral_reference", value="9872023VH5797S0001WX"),
            UserProfileFact(path="contact.fiscal_address_is_habitual_vivienda", value=True),
            UserProfileFact(path="taxpayer_type.incn_prior_12_months", value="50000.00"),
        ),
    )
    profile = projection_for_taxpayer(record)
    # Selector-aliased direct reads.
    assert profile.fiscal_address_cadastral_reference == "9872023VH5797S0001WX"
    assert profile.fiscal_address_is_habitual_vivienda is True
    # Path-keyed direct read carried by the same merged mapping.
    assert profile.incn_prior_12_months == Decimal("50000.00")
    # Path-keyed typed projection unaffected by the selector overlay.
    assert profile.tax_id == "12345678Z"


def test_projection_for_taxpayer_is_the_single_state_projection_authority() -> None:
    """A record and its selector-keyed flat projection coerce identically.

    Guards the delegation chain (workflow state projection ->
    ``projection_for_taxpayer`` -> ``taxpayer_profile_from_mapping``): a
    consumer that forks off with a bare selector-keyed mapping must still
    land on the same ``TaxpayerProfile`` for the fields both key spaces
    carry, so a future divergence between the record path and a flat-map
    caller fails here loudly.
    """
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id="11111111-1111-4111-8111-111111111111",
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="withholding.has_employees", value=True),
            UserProfileFact(path="contact.fiscal_address_is_habitual_vivienda", value=True),
        ),
    )
    via_record = projection_for_taxpayer(record)
    via_merged_mapping = projection_for_taxpayer(dict(record_to_path_values(record)) | record_to_values(record))
    assert via_record == via_merged_mapping


def test_a_record_with_no_windows_projects_exactly_as_declared() -> None:
    """The no-op property: window-awareness changes nothing for current data.

    No production writer sets an effective window, so every record in
    existence today has facts carrying ``valid_from = None``. Ordering by
    window is a stable sort over equal keys, which preserves declaration
    order, so the last fact per path is the same one it always was.

    This is the property that makes the change landable without a data
    migration, so it is asserted rather than assumed.
    """
    facts = (
        UserProfileFact(path="identity.tax_id", value="11111111H"),
        UserProfileFact(path="identity.tax_id", value="22222222J"),
        UserProfileFact(path="contact.postcode", value="08032"),
    )
    record = UserProfileRecord(setup_state=ProfileSetupState.COMPLETE, profile_id=_PROFILE_UUID, facts=facts)

    assert record_to_path_values(record)["identity.tax_id"] == "22222222J", (
        "declaration order still decides when no window does"
    )
    assert record_to_effective_facts(record)["identity.tax_id"].value == "22222222J"


def test_the_latest_effective_window_wins_at_one_path() -> None:
    """Two live facts at one path resolve to the later window, not the later line.

    The record model permits this and the schema declares effective-dating
    on most of its fields, so it is a state the projections have to answer
    for. Declaration order here is deliberately the REVERSE of window
    order, so a projection that ignored the window would return the 2019
    value.
    """
    facts = (
        UserProfileFact(path="contact.postcode", value="28001", valid_from=date(2024, 1, 1)),
        UserProfileFact(path="contact.postcode", value="08032", valid_from=date(2019, 1, 1)),
    )
    record = UserProfileRecord(setup_state=ProfileSetupState.COMPLETE, profile_id=_PROFILE_UUID, facts=facts)

    assert record_to_path_values(record)["contact.postcode"] == "28001"
    assert record_to_effective_facts(record)["contact.postcode"].value == "28001"


def test_a_windowed_fact_supersedes_an_unwindowed_one() -> None:
    """An absent window means no stated start, so it orders before every stated one."""
    facts = (
        UserProfileFact(path="contact.postcode", value="28001", valid_from=date(2024, 1, 1)),
        UserProfileFact(path="contact.postcode", value="08032"),
    )
    record = UserProfileRecord(setup_state=ProfileSetupState.COMPLETE, profile_id=_PROFILE_UUID, facts=facts)

    assert record_to_path_values(record)["contact.postcode"] == "28001"


def test_the_two_projections_agree_on_which_fact_is_effective() -> None:
    """The whole point: one concept must not have two resolution rules.

    Before this, one projection resolved by window and the other by list
    order, and they agreed only because nothing set a window.
    """
    facts = (
        UserProfileFact(path="contact.postcode", value="28001", valid_from=date(2024, 1, 1)),
        UserProfileFact(path="contact.postcode", value=None, valid_from=date(2019, 1, 1)),
    )
    record = UserProfileRecord(setup_state=ProfileSetupState.COMPLETE, profile_id=_PROFILE_UUID, facts=facts)

    assert record_to_path_values(record)["contact.postcode"] == "28001"
    assert record_to_effective_facts(record)["contact.postcode"].value == "28001", (
        "the value projection and the effective-fact projection must name the same fact"
    )
