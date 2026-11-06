"""A declared profile record whose three-state payer facts are the only variable.

The withholding and intracommunity payer facts gate Modelos 111, 115, 180,
190, 216, 296 and 349, the Art. 109 RIRPF coverage fact gates Modelo 130, and
the capital-income retención fact gates Modelos 117, 123, 126, 128, 187, 188,
193 and 194.
Tests of those gates need a taxpayer who is otherwise fully declared, so a
verdict can only turn on the payer answer. The record is built through the
production creation door under the caller's pinned authority.
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

CAPITAL_PATH = "withholding.pays_capital_income_with_retencion"
"""The rendimientos del capital mobiliario retención fact eight modelos require."""

CAPITAL_GATED_MODELOS = ("117", "123", "126", "128", "187", "188", "193", "194")
"""Every modelo whose applicability rule requires the capital-income fact."""

PAYER_FACT_PATHS = (
    "withholding.has_employees",
    "withholding.pays_professionals_with_retencion",
    "withholding.pays_rent_with_retencion",
    CAPITAL_PATH,
    "iva.does_intracomunitario",
)
"""The payer facts whose declared yes makes their modelos applicable.

The Art. 109 coverage fact is kept out: it is an exclusion, so its yes and no
run the other way and a record cannot answer it together with these five.
"""

PAYER_FACT_GATED_MODELOS = (
    "111",
    "115",
    *CAPITAL_GATED_MODELOS,
    "180",
    "190",
    "216",
    "296",
    "349",
)
"""Every modelo these five payer facts gate through the three-state contract."""

ART109_PATH = "irpf.art109_activity_income_withholding_ge_70pct"
"""The Art. 109 RIRPF coverage fact, which excludes Modelo 130 on a declared yes."""

ART109_GATED_MODELO = "130"
"""The modelo that coverage fact alone gates."""


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
    """Return a declared record whose five payer facts carry ``answer``, or nothing."""
    return _record(operation, paths=PAYER_FACT_PATHS, answer=answer)


def art109_record(operation: PinnedAuthorityOperation, *, answer: bool | None) -> UserProfileRecord:
    """Return the same declared autónomo with the Art. 109 coverage fact answered, or absent."""
    return _record(operation, paths=(ART109_PATH,), answer=answer)


def capital_income_record(operation: PinnedAuthorityOperation, *, answer: bool | None) -> UserProfileRecord:
    """Return the same declared autónomo with the capital-income fact answered, or absent."""
    return _record(operation, paths=(CAPITAL_PATH,), answer=answer)


def _record(
    operation: PinnedAuthorityOperation,
    *,
    paths: tuple[str, ...],
    answer: bool | None,
) -> UserProfileRecord:
    answers = () if answer is None else tuple(UserProfileFact(path=path, value=answer) for path in paths)
    return create_user_profile_record(
        context=operation.profile_create_context(),
        profile_id=PROFILE_ID,
        facts=(*DECLARED_TAXPAYER_FACTS, *answers),
        setup_state=ProfileSetupState.COMPLETE,
    )


__all__ = [
    "ART109_GATED_MODELO",
    "ART109_PATH",
    "CAPITAL_GATED_MODELOS",
    "CAPITAL_PATH",
    "DECLARED_TAXPAYER_FACTS",
    "PAYER_FACT_GATED_MODELOS",
    "PAYER_FACT_PATHS",
    "PROFILE_ID",
    "art109_record",
    "capital_income_record",
    "payer_fact_record",
]
