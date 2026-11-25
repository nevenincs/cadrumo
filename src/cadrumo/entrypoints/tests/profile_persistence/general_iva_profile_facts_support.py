"""The complete-profile facts of a general-regime natural person, shared by profile persistence scenarios."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
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
    return persona_facts_beneath(
        (
            UserProfileFact(path="identity.tax_id", value=tax_id),
            UserProfileFact(path="identity.name", value=name),
            UserProfileFact(path="identity.surnames", value=surnames),
            UserProfileFact(path="activities.description", value=activity),
            UserProfileFact(path="censo.activity_start_date", value=activity_start_date),
        )
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
        UserProfileFact(path="renta_family.descendants_eu_eea_deduction", value=False),
    )
