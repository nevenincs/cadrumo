"""A complete, general-regime natural-person profile seeded for work-unit suites."""

from __future__ import annotations

from datetime import datetime

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
)
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test


def ready_profile_facts(*, surnames: str) -> tuple[UserProfileFact, ...]:
    return (
        UserProfileFact(path="identity.tax_id", value="00000000T"),
        UserProfileFact(path="identity.name", value="Test Operator"),
        UserProfileFact(path="identity.surnames", value=surnames),
        UserProfileFact(path="tax_residence.ccaa", value="madrid"),
        UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
        UserProfileFact(path="activities.description", value="economic activity"),
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


def seed_ready_profile(*, bucket_id: str, surnames: str, at: datetime) -> None:
    seed_test_profile_record(
        _create_profile_record_for_test(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=ready_profile_facts(surnames=surnames),
            created_at=at,
            updated_at=at,
            context=_profile_creation_context_for_test(),
        ),
    )
