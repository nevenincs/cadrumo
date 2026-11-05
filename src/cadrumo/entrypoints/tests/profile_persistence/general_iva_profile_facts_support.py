"""The complete-profile facts of a general-regime natural person, shared by profile persistence scenarios."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cadrumo.domain.user_profile.values import UserProfileFact

from ....domain.user_profile.tests.general_regime_facts import GENERAL_REGIME_NATURAL_PERSON_FACTS


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
        *GENERAL_REGIME_NATURAL_PERSON_FACTS,
        UserProfileFact(path="censo.activity_start_date", value=activity_start_date),
    )


def renta_single_taxpayer_facts(*, birth_date: date) -> tuple[UserProfileFact, ...]:
    """Return the renta facts of a single taxpayer filing alone, with no dependants."""
    return (
        UserProfileFact(path="renta_taxpayer.birth_date", value=birth_date),
        UserProfileFact(path="renta_taxpayer.sex", value="H"),
        UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
        UserProfileFact(path="renta_taxpayer.marriage_full_year", value=False),
        UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
        UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
        UserProfileFact(path="renta_filing.declaration_type", value="1"),
        UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
        UserProfileFact(path="renta_family.descendientes_count", value=Decimal("0")),
        UserProfileFact(path="renta_family.cotizaciones_ss_madre_2024", value=Decimal("0")),
        UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=False),
    )


def no_household_renta_facts() -> tuple[UserProfileFact, ...]:
    """Return the renta facts derived for a filer with no spouse and no dependants.

    A single persona states its sex, marital status, birth date and declaration type;
    these are the marriage and family quantities the Renta bindings read from a household
    that has no members, so each is a true zero.
    """
    return (
        UserProfileFact(path="renta_taxpayer.marriage_full_year", value=False),
        UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
        UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
        UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
        UserProfileFact(path="renta_family.descendientes_count", value=Decimal("0")),
        UserProfileFact(path="renta_family.cotizaciones_ss_madre_2024", value=Decimal("0")),
        UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=False),
        UserProfileFact(path="renta_family.unidad_familiar_otros_miembros_base", value=Decimal("0")),
        UserProfileFact(path="renta_family.madrid_nacimiento_adopcion_eligible_count", value=Decimal("0")),
    )
