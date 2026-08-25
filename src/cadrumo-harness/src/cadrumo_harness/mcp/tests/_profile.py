"""Canonical real-profile fixtures shared by harness integration tests."""

from __future__ import annotations

from cadrumo.application.user_profile import ProfileRecoveryEnrollment
from cadrumo.domain.user_profile import UserProfileFact

PROFILE_PASSPHRASE = "harness-current-profile-credential"  # noqa: S105 - synthetic integration credential
READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = (
    UserProfileFact(path="identity.tax_id", value="00000000T"),
    UserProfileFact(path="identity.name", value="Harness Operator"),
    UserProfileFact(path="tax_residence.ccaa", value="madrid"),
    UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
    UserProfileFact(path="iva.regime", value="GENERAL"),
    UserProfileFact(path="iva.m303_regime_composition", value="general"),
    UserProfileFact(path="iva.redeme_enrolled", value=False),
    UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
    UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
    UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
    UserProfileFact(path="provenance.source", value="manual_cli"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
    UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
)


def verify_recovery_handover(enrollment: ProfileRecoveryEnrollment) -> str:
    """Return the exact generated phrase as real possession proof for a test profile."""
    return enrollment.recovery_key.mnemonic


__all__ = ["PROFILE_PASSPHRASE", "READY_PROFILE_FACTS", "verify_recovery_handover"]
