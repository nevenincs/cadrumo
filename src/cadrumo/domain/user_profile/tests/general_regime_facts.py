"""Renta facts shared by tests that need one unmarried taxpayer without dependants."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Final

from ..values import UserProfileFact

RENTA_UNMARRIED_TAXPAYER_FACTS: Final[tuple[UserProfileFact, ...]] = (
    UserProfileFact(path="renta_taxpayer.birth_date", value=date(1980, 3, 15)),
    UserProfileFact(path="renta_taxpayer.marital_status", value="1"),
    UserProfileFact(path="renta_taxpayer.marriage_full_year", value=False),
    UserProfileFact(path="renta_taxpayer.marriage_month_start", value=Decimal("0")),
    UserProfileFact(path="renta_taxpayer.marriage_month_end", value=Decimal("0")),
    UserProfileFact(path="renta_filing.declaration_type", value="1"),
    UserProfileFact(path="renta_family.minor_children_in_unit", value=False),
)
"""The minimum renta facts the profile-sourced 2025 Modelo 100 bindings resolve from: one unmarried taxpayer without dependants."""
