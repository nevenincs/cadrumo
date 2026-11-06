"""A declared profile record whose four three-state payer facts are the only variable.

The withholding and intracommunity payer facts gate Modelos 111, 115, 180,
190, 216, 296 and 349. Tests of that gate need a taxpayer who is otherwise
fully declared, so a verdict can only turn on the payer answer. The record is
built through the production creation door under the caller's pinned authority.
"""

from __future__ import annotations

from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    create_user_profile_record,
)

PROFILE_ID = "5aa00000-0000-4000-8000-0000000000aa"

PAYER_FACT_GATED_MODELOS = ("111", "115", "180", "190", "216", "296", "349")
"""Every modelo these four payer facts gate through the three-state contract."""

PAYER_FACT_PATHS = (
    "withholding.has_employees",
    "withholding.pays_professionals_with_retencion",
    "withholding.pays_rent_with_retencion",
    "iva.does_intracomunitario",
)

DECLARED_TAXPAYER_FACTS = (
    UserProfileFact(path="identity.tax_id", value="X0001500M"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_simplificada"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
)
"""A fully declared autónomo, so only the payer answer is ever in question."""


def payer_fact_record(operation: PinnedAuthorityOperation, *, answer: bool | None) -> UserProfileRecord:
    """Return a declared record whose four payer facts carry ``answer``, or nothing."""
    answers = () if answer is None else tuple(UserProfileFact(path=path, value=answer) for path in PAYER_FACT_PATHS)
    return create_user_profile_record(
        context=operation.profile_create_context(),
        profile_id=PROFILE_ID,
        facts=(*DECLARED_TAXPAYER_FACTS, *answers),
        setup_state=ProfileSetupState.COMPLETE,
    )


__all__ = [
    "DECLARED_TAXPAYER_FACTS",
    "PAYER_FACT_GATED_MODELOS",
    "PAYER_FACT_PATHS",
    "PROFILE_ID",
    "payer_fact_record",
]
