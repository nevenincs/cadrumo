"""Profile facts shared by tests that need a general-regime natural-person taxpayer.

These are the tax-axis facts that readiness gates ask for after identity and
activity text. Each caller still declares its own identity, activity and
start-date facts, so the values that differ between scenarios stay beside the
test that depends on them.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Final

from ..values import UserProfileFact

GENERAL_REGIME_NATURAL_PERSON_FACTS: Final[tuple[UserProfileFact, ...]] = (
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
)

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
