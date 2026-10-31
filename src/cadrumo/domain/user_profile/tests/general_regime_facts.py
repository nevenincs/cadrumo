"""Profile facts shared by tests that need a general-regime natural-person taxpayer.

These are the tax-axis facts that readiness gates ask for after identity and
activity text. Each caller still declares its own identity, activity and
start-date facts, so the values that differ between scenarios stay beside the
test that depends on them.
"""

from __future__ import annotations

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
