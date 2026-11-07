"""Shared fixtures for verification substance tests."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from cadrumo.adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.domain.deadlines.models import (
    IVARegime,
    M303RegimeComposition,
    M303TaxTerritory,
    ModeloIVAProfile,
    TaxpayerProfile,
)
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test,
)
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record

Repos = tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    VerificationReportCatalogueRepository,
    BucketEventHistoryRepository,
]

T0 = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
T1 = datetime(2026, 1, 15, 13, 0, 0, tzinfo=UTC)
T2 = datetime(2026, 4, 14, 14, 0, 0, tzinfo=UTC)


CASILLA_01: CasillaId = validated_casilla_id("01")
CASILLA_02: CasillaId = validated_casilla_id("02")
CASILLA_03: CasillaId = validated_casilla_id("03")
CASILLA_05: CasillaId = validated_casilla_id("05")
CASILLA_06: CasillaId = validated_casilla_id("06")
_CASILLA_07: CasillaId = validated_casilla_id("07")
CASILLA_08: CasillaId = validated_casilla_id("08")
CASILLA_09: CasillaId = validated_casilla_id("09")
_CASILLA_10: CasillaId = validated_casilla_id("10")
_CASILLA_11: CasillaId = validated_casilla_id("11")
CASILLA_12: CasillaId = validated_casilla_id("12")
CASILLA_14: CasillaId = validated_casilla_id("14")
CASILLA_15: CasillaId = validated_casilla_id("15")
CASILLA_16: CasillaId = validated_casilla_id("16")
CASILLA_18: CasillaId = validated_casilla_id("18")
ABSENT_REGISTRY_CASILLA: CasillaId = validated_casilla_id("99")
_M200_BIN_OPEN_CASILLA: CasillaId = validated_casilla_id("00670")
_M200_BIN_CLOSING_CASILLA: CasillaId = validated_casilla_id("00671")
_M200_BIN_APPLIED_CASILLA: CasillaId = validated_casilla_id("DP200014:00547")
_M200_BIN_GENERATED_CASILLA: CasillaId = validated_casilla_id("DP200014:00552")

_READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = persona_facts_beneath(
    (
        UserProfileFact(path="identity.tax_id", value="00000000T"),
        UserProfileFact(path="identity.name", value="Test"),
        UserProfileFact(path="identity.surnames", value="Operator"),
        UserProfileFact(path="activities.description", value="economic activity"),
    )
)


def _casilla_values(*entries: tuple[CasillaId, str]) -> dict[CasillaId, Decimal]:
    return {casilla_id: Decimal(value) for casilla_id, value in entries}


def seed_ready_profile(
    *,
    bucket_id: str,
    irpf_estimation_regime: str = "directa_normal",
) -> None:
    facts = tuple(
        UserProfileFact(path=fact.path, value=irpf_estimation_regime) if fact.path == "irpf.estimation_regime" else fact
        for fact in _READY_PROFILE_FACTS
    )
    seed_test_profile_record(
        create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=facts,
            created_at=T0,
            updated_at=T0,
            context=profile_creation_context_for_test(),
        ),
    )


def workflow_profile(
    *, tax_id: str = "X0001500M", iva_regime: str = "GENERAL", activity_start_date: date | None = None
) -> TaxpayerProfile:
    """The plain workflow profile: no employees, rent retention, intracommunity trade or foreign assets."""
    return TaxpayerProfile(
        tax_id=tax_id,
        iva_regime=IVARegime(iva_regime),
        activity_start_date=activity_start_date,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def general_iva_workflow_profile() -> TaxpayerProfile:
    """The general-regime workflow profile with an explicit common-territory general IVA composition."""
    return TaxpayerProfile(
        tax_id="X0001500M",
        iva_regime=IVARegime("GENERAL"),
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
        iva=ModeloIVAProfile(
            tax_territory=M303TaxTerritory.from_registry("common_regime"),
            regime_composition=M303RegimeComposition.from_registry("general"),
            redeme_enrolled=False,
            cash_accounting_regime_enrolled=False,
            voluntary_sii_enrolled=False,
            hydrocarbon_deposit_advance_payment_deduction_entitled=False,
        ),
    )
