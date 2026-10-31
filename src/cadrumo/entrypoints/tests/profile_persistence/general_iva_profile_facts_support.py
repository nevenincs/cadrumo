"""The complete-profile facts of a general-regime natural person, shared by profile persistence scenarios."""

from __future__ import annotations

from datetime import date

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
