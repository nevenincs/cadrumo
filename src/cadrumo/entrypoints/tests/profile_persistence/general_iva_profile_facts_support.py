"""The profile facts of a natural person on the general IVA regime with direct IRPF estimation."""

from __future__ import annotations

from datetime import date

from cadrumo.domain.user_profile.values import UserProfileFact


def general_iva_profile_facts(
    *,
    tax_id: str,
    activity_start_date: date | str,
    name: str = "Test",
    surnames: str = "Operator",
    activity: str = "economic activity",
) -> tuple[UserProfileFact, ...]:
    """Return the complete-profile facts shared by the profile persistence scenarios."""
    return (
        UserProfileFact(path="identity.tax_id", value=tax_id),
        UserProfileFact(path="identity.name", value=name),
        UserProfileFact(path="identity.surnames", value=surnames),
        UserProfileFact(path="activities.description", value=activity),
        UserProfileFact(path="tax_residence.ccaa", value="madrid"),
        UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
        UserProfileFact(path="iva.regime", value="GENERAL"),
        UserProfileFact(path="iva.m303_regime_composition", value="general"),
        UserProfileFact(path="iva.redeme_enrolled", value=False),
        UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
        UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
        UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
        UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
        UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
        UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
        UserProfileFact(path="censo.activity_start_date", value=activity_start_date),
    )
