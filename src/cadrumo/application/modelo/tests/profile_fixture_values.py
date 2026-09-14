"""Application-owned profile values shared by modelo test scenarios.

This module contains only the domain value objects that describe a taxpayer
ready for the modelo readiness gate.  Persistence-backed capsule construction
lives with the storage adapter test support; keeping the value here makes the
application test contract usable without importing that adapter.
"""

from __future__ import annotations

from typing import Final

from cadrumo.domain.user_profile.values import UserProfileFact

MODELO_READY_PROFILE_FACTS: Final[tuple[UserProfileFact, ...]] = (
    UserProfileFact(path="identity.tax_id", value="12345678Z"),
    # A fichero carries the declarant's legal name, composed from these two
    # facts: ``_identity_from_profile_facts`` returns None without them, and
    # export then refuses an anonymous taxpayer.
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="identity.name", value="Ana"),
    UserProfileFact(path="identity.surnames", value="Garcia Lopez"),
    UserProfileFact(path="activities.description", value="Spanish rental income"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
)
"""The minimum taxpayer baseline accepted by the modelo readiness gate.

The tuple is intentionally one declaration: duplicated readiness fixtures can
drift and make a suite pass against a taxpayer shape the gate no longer
accepts.
"""


__all__ = ["MODELO_READY_PROFILE_FACTS"]
