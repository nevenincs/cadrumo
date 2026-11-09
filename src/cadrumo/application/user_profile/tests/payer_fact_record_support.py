"""A declared profile record whose three-state payer facts are the only variable.

The withholding and intracommunity payer facts gate Modelos 111, 115, 180,
190 and 349, the IRNR withholding fact gates Modelos 216 and 296, the Art. 109 RIRPF coverage fact gates Modelo 130, the
capital-income retención fact gates Modelos 117, 123, 126, 128, 187, 188, 193
and 194, the IVA enrolment facts gate Modelos 322, 353 and 369, and the
fiscal-residency category gates Modelos 100, 130, 151, 200, 202, 210 and 840.
Tests of those gates need a taxpayer who is otherwise fully declared, so a
verdict can only turn on the answer under test. The record is built through
the production creation door under the caller's pinned authority.
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
    "withholding.pays_non_resident_income_with_retencion",
    "iva.does_intracomunitario",
)
"""The payer facts whose declared yes makes their modelos applicable.

Withholding on income paid to non-residents without a permanent establishment
is its own fact (TRLIRNR art. 31): it brings Modelos 216 and 296, which the
resident IRPF withholding facts do not.

The Art. 109 coverage fact is kept out: it is an exclusion, so its yes and no
run the other way and a record cannot answer it together with these six.
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
"""Every modelo these six payer facts gate through the three-state contract."""

ART109_PATH = "irpf.art109_activity_income_withholding_ge_70pct"
"""The Art. 109 RIRPF coverage fact, which excludes Modelo 130 on a declared yes."""

ART109_GATED_MODELO = "130"
"""The modelo that coverage fact alone gates."""


RESIDENCY_PATH = "taxpayer_type.fiscal_residency"
"""The residency category that selects the tax, and with it the modelo family."""

RESIDENT_CATEGORY = "resident_irpf"
"""Habitual residence in Spain: the taxpayer tributa por el IRPF (LIRPF art. 9)."""

NON_RESIDENT_CATEGORY = "non_resident_irnr"
"""No habitual residence in Spain: the taxpayer tributa por el IRNR (TRLIRNR art. 2)."""

COUNTRY_OF_RESIDENCE = "FR"
"""The country a non-resident record states, so the profile projects at all."""

RESIDENCY_DECIDED_MODELOS = ("100", "130", "210")
"""The modelos whose verdict this record leaves to the residency axis alone.

Modelos 151, 200, 202 and 840 also name their residencies, but a
natural-person autónomo is refused by an earlier axis -- the entity type, the
special regime or the IAE epigraph -- so residency never decides them here.
:data:`RESIDENCY_UNREACHED_MODELOS` pins that, so the assertions below are
about residency and nothing else.
"""

RESIDENCY_UNREACHED_MODELOS = ("151", "200", "202", "840")
"""Residency-naming modelos an earlier axis refuses for this taxpayer."""

RESIDENT_ONLY_MODELO = "100"
"""The IRPF annual declaration, which only the resident category admits."""

NON_RESIDENT_ONLY_MODELO = "210"
"""The IRNR autoliquidación, which only the non-resident category admits."""

IVA_ENROLMENT_GATED_MODELOS = {
    "322": "iva.group_member_enrolled",
    "353": "iva.group_dominant_entity_enrolled",
    "369": "iva.oss_enrolled",
}
"""Each IVA group / one-stop-shop modelo with the enrolment fact its rule requires."""

LARGE_COMPANY_PATH = "censo.large_company"
"""The volumen de operaciones condition that decides the filing cadence."""

LARGE_COMPANY_CADENCE_MODELOS = ("111", "115", "123", "216", "303")
"""Modelos whose filing schedules select a cadence from the large-company condition."""

_DECLARED_TAXPAYER_FACTS_WITHOUT_RESIDENCY = (
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
"""Everything the autónomo declares except the residency category under test."""

DECLARED_TAXPAYER_FACTS = (
    *_DECLARED_TAXPAYER_FACTS_WITHOUT_RESIDENCY,
    UserProfileFact(path=RESIDENCY_PATH, value=RESIDENT_CATEGORY),
)
"""A fully declared resident autónomo, so only the answer under test is in question.

The residency category is stated rather than left absent: it is the axis that
selects the tax, so an unstated residency would leave every residency-gated
modelo incomplete and hide what the payer-fact gate under test decides.
"""


def residency_record(operation: PinnedAuthorityOperation, *, token: str | None) -> UserProfileRecord:
    """Return the same declared autónomo with the residency category stated, or absent.

    A category the registry declares as needing a country of fiscal residence
    is stated together with one, because the profile refuses to project
    without it (TRLIRNR art. 2). Which category that is comes from the
    registry, not from this fixture.
    """
    from ....domain.calculations.registry.renta_codes_catalogue import fiscal_residency_requires_country

    stated: tuple[UserProfileFact, ...] = ()
    if token is not None:
        stated = (UserProfileFact(path=RESIDENCY_PATH, value=token),)
        if fiscal_residency_requires_country(token, authority=operation):
            stated = (
                *stated,
                UserProfileFact(path="taxpayer_type.country_of_fiscal_residence", value=COUNTRY_OF_RESIDENCE),
            )
    return create_user_profile_record(
        context=operation.profile_create_context(),
        profile_id=PROFILE_ID,
        facts=(*_DECLARED_TAXPAYER_FACTS_WITHOUT_RESIDENCY, *stated),
        setup_state=ProfileSetupState.COMPLETE,
    )


def iva_enrolment_record(
    operation: PinnedAuthorityOperation,
    *,
    answer: bool | None,
) -> UserProfileRecord:
    """Return the declared autónomo with every IVA group / OSS enrolment answered, or absent."""
    return _record(operation, paths=tuple(sorted(IVA_ENROLMENT_GATED_MODELOS.values())), answer=answer)


def large_company_record(operation: PinnedAuthorityOperation, *, answer: bool | None) -> UserProfileRecord:
    """Return the declared autónomo with the large-company condition stated, or absent."""
    return _record(operation, paths=(LARGE_COMPANY_PATH,), answer=answer)


def payer_fact_record(operation: PinnedAuthorityOperation, *, answer: bool | None) -> UserProfileRecord:
    """Return a declared record whose six payer facts carry ``answer``, or nothing."""
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
    "COUNTRY_OF_RESIDENCE",
    "DECLARED_TAXPAYER_FACTS",
    "IVA_ENROLMENT_GATED_MODELOS",
    "LARGE_COMPANY_CADENCE_MODELOS",
    "LARGE_COMPANY_PATH",
    "NON_RESIDENT_CATEGORY",
    "NON_RESIDENT_ONLY_MODELO",
    "PAYER_FACT_GATED_MODELOS",
    "PAYER_FACT_PATHS",
    "PROFILE_ID",
    "RESIDENCY_DECIDED_MODELOS",
    "RESIDENCY_PATH",
    "RESIDENCY_UNREACHED_MODELOS",
    "RESIDENT_CATEGORY",
    "RESIDENT_ONLY_MODELO",
    "art109_record",
    "capital_income_record",
    "iva_enrolment_record",
    "large_company_record",
    "payer_fact_record",
    "residency_record",
]
